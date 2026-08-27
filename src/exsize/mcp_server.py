"""MCP server for ExSize (issue #66: server + auth + To-Do tools, issue #67: chores + read-only gamification/family).

Streamable HTTP endpoint mounted at ``/mcp`` inside the FastAPI app (single
Render service, no extra hosting). Authentication reuses the existing API-token
infrastructure: ``Authorization: Bearer exs_...`` verified against bcrypt
hashes in ``api_tokens`` — the same tokens the Cryplo API accepts. Every MCP
request must carry a valid token, including ``tools/list``; otherwise the
request is rejected with 401 before any tool runs.

Tools are thin adapters: To-Do tools call ``TodoService`` directly; chores,
gamification and family tools call the existing router functions, so every
business rule (role checks, status transitions, payouts) lives in exactly one
place. The MCP caller acts as the owner of the verified token, with that
user's role and permissions.
"""

from contextlib import contextmanager
from datetime import datetime
from typing import Literal

import anyio
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.auth import TokenVerifier
from fastmcp.server.dependencies import get_access_token
from mcp.server.auth.provider import AccessToken
from sqlalchemy.orm import Session

from exsize.database import SessionLocal
from exsize.deps import resolve_api_token_user
from exsize.models import User
from exsize.routers.avatar import AvatarItemResponse, get_shop
from exsize.routers.family import get_family
from exsize.routers.gamification import get_profile
from exsize.routers.tasks import (
    TaskCreateRequest,
    TaskResponse,
    accept_task,
    approve_task,
    complete_task,
    create_task,
    list_tasks,
    reject_task,
)
from exsize.services.todo import TodoNotFound, TodoService


class ExsizeTokenVerifier(TokenVerifier):
    """Verifies ExSize API tokens (exs_...) so MCP requests are authenticated.

    bcrypt verification is offloaded to a worker thread — it would otherwise
    block the event loop for the whole server.
    """

    async def verify_token(self, token: str) -> AccessToken | None:
        db = SessionLocal()
        try:
            user = await anyio.to_thread.run_sync(
                lambda: resolve_api_token_user(db, token)
            )
            if user is None:
                return None
            return AccessToken(token=token, client_id=str(user.id), scopes=["mcp"])
        finally:
            db.close()


mcp = FastMCP(
    "ExSize",
    instructions=(
        "Family chore & reward manager. Tools act as the owner of the API token: "
        "a parent can manage chores and approve; a child can accept and complete "
        "their own chores. To-Do lists are personal to the token owner."
    ),
    auth=ExsizeTokenVerifier(),
)


@contextmanager
def _caller():
    """Resolve the MCP caller (token owner) with a fresh DB session."""
    access = get_access_token()
    if access is None or not str(access.client_id).isdigit():
        raise ToolError("Not authenticated")
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == int(access.client_id)).first()
        if user is None:
            raise ToolError("User not found")
        yield user, db
    finally:
        db.close()


def _run_router_call(call) -> dict:
    """Run a router-function call, translating HTTPException into a tool error."""
    from fastapi import HTTPException

    try:
        return call()
    except HTTPException as exc:
        raise ToolError(str(exc.detail))


def _item_dict(item) -> dict:
    return {
        "id": item.id,
        "title": item.title,
        "completed": item.completed,
        "due_at": item.due_at.isoformat() if item.due_at else None,
        "recurrence": item.recurrence,
    }


# --- To-Do tools (issue #66) ---


@mcp.tool
def todo_lists() -> list[dict]:
    """List the token owner's To-Do lists with all their items."""
    with _caller() as (user, db):
        service = TodoService(db, user.id)
        return [
            {
                "id": todo_list.id,
                "name": todo_list.name,
                "items": [_item_dict(i) for i in service.list_items(todo_list.id)],
            }
            for todo_list in service.list_lists()
        ]


@mcp.tool
def todo_add_item(
    title: str,
    list_name: str | None = None,
    list_id: int | None = None,
    due_at: datetime | None = None,
    recurrence: Literal["daily", "weekly"] | None = None,
) -> dict:
    """Add an item to the token owner's To-Do.

    Target list: pass `list_id`, or `list_name` (case-insensitive; a list with
    that name is created if it does not exist yet — e.g. "add milk to the
    Shopping list"). `due_at` is an ISO datetime; `recurrence` repeats the item.
    """
    with _caller() as (user, db):
        service = TodoService(db, user.id)

        def _resolve_list_id() -> int:
            if list_id is not None:
                return list_id
            name = (list_name or "").strip()
            if not name:
                raise ToolError("Pass either list_name or list_id")
            for todo_list in service.list_lists():
                if todo_list.name.lower() == name.lower():
                    return todo_list.id
            created = service.create_list(name)
            return created.id

        try:
            resolved_list_id = _resolve_list_id()
            item = service.add_item(
                resolved_list_id, title, due_at=due_at, recurrence=recurrence
            )
        except TodoNotFound:
            raise ToolError(f"List not found (id={list_id})")
        return _item_dict(item)


@mcp.tool
def todo_complete_item(item_id: int) -> dict:
    """Toggle an item's completion (checking it off; recurring items spawn their next occurrence)."""
    with _caller() as (user, db):
        try:
            item = TodoService(db, user.id).complete_item(item_id)
        except TodoNotFound:
            raise ToolError(f"Item not found (id={item_id})")
        return _item_dict(item)


# --- Chores, gamification (read), family (read) tools (issue #67) ---


def _display_names(db: Session, family_id: int | None) -> dict[int, str]:
    if family_id is None:
        return {}
    members = db.query(User).filter(User.family_id == family_id).all()
    return {m.id: (m.nickname or m.email) for m in members}


def _task_payload(db: Session, user: User, task) -> dict:
    """Router functions return raw ORM Tasks (response_model conversion only happens
    over HTTP) — normalize through TaskResponse here."""
    data = TaskResponse.model_validate(task).model_dump(mode="json")
    data["assigned_to_name"] = _display_names(db, user.family_id).get(task.assigned_to)
    return data


@mcp.tool
def chores_list() -> list[dict]:
    """List the family's chores — parents see all, children see their own — with each assignee's name."""
    with _caller() as (user, db):
        tasks = _run_router_call(lambda: list_tasks(user=user, db=db))
        return [_task_payload(db, user, t) for t in tasks]


@mcp.tool
def chore_create(name: str, description: str, exbucks: int, assigned_to: int, day_of_week: str | None = None) -> dict:
    """Create and assign a chore (parents only). `assigned_to` is the child's user id — see family_info for ids."""
    with _caller() as (user, db):
        task = _run_router_call(lambda: create_task(
            TaskCreateRequest(
                name=name, description=description, exbucks=exbucks,
                assigned_to=assigned_to, day_of_week=day_of_week,
            ),
            user=user, db=db,
        ))
        return _task_payload(db, user, task)


@mcp.tool
def chore_set_status(chore_id: int, action: Literal["accept", "reject", "complete", "approve"]) -> dict:
    """Update a chore's status. Role rules apply: the assigned child can accept, complete or reject
    their own chore; a parent can approve (pays out ExBucks and XP to the child) or reject."""
    with _caller() as (user, db):
        handlers = {
            "accept": lambda: accept_task(chore_id, user=user, db=db),
            "reject": lambda: reject_task(chore_id, user=user, db=db),
            "complete": lambda: complete_task(chore_id, body=None, user=user, db=db),
            "approve": lambda: approve_task(chore_id, user=user, db=db),
        }
        task = _run_router_call(handlers[action])
        return _task_payload(db, user, task)


@mcp.tool
def gamification_profile() -> dict:
    """Read the caller's gamification profile: ExBucks balance, XP, level and level name, progress, streak. Children only."""
    with _caller() as (user, db):
        profile = _run_router_call(lambda: get_profile(user=user, db=db))
        data = profile.model_dump(mode="json")
        data["exbucks_balance"] = user.exbucks_balance
        return data


@mcp.tool
def shop_items() -> list[dict]:
    """List avatar items available in the shop with prices (read-only)."""
    with _caller() as (user, db):
        items = _run_router_call(lambda: get_shop(user=user, db=db))
        return [AvatarItemResponse.model_validate(i).model_dump(mode="json") for i in items]


@mcp.tool
def family_info() -> dict:
    """Read the caller's family: members with ids, emails, nicknames and roles (parent/child)."""
    with _caller() as (user, db):
        detail = _run_router_call(lambda: get_family(user=user, db=db))
        names = _display_names(db, user.family_id)
        data = detail.model_dump(mode="json")
        for member in data["members"]:
            member["nickname"] = names.get(member["id"])
        return data


mcp_asgi_app = mcp.http_app(path="/mcp", stateless_http=True, json_response=True)
