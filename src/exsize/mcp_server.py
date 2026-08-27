"""MCP server for ExSize (issue #66: server + auth + To-Do tools, issue #67: chores +
read-only gamification/family, issue #76: Google OAuth for the Claude connector).

Streamable HTTP endpoint mounted at ``/mcp`` inside the FastAPI app (single
Render service, no extra hosting). Authentication depends on the environment:

- Default: ``Authorization: Bearer exs_...`` verified against bcrypt hashes in
  ``api_tokens`` — the same tokens the Cryplo API accepts.
- With ``GOOGLE_CLIENT_ID`` + ``GOOGLE_CLIENT_SECRET`` (+ public ``MCP_BASE_URL``):
  a real Google OAuth flow through fastmcp's ``GoogleProvider`` (OAuth proxy with
  consent screen), and ``exs_...`` tokens still work as a fallback via the same
  hybrid provider — curl/tests/Cryplo keep working unchanged.
- With ``MCP_AUTH_IN_MEMORY=1``: fastmcp's in-memory OAuth provider (offline tests).

Every MCP request must be authenticated, including ``tools/list``; otherwise the
request is rejected with 401 before any tool runs. Google callers act as the
matching ExSize account (matched by email; a first-time email gets an
auto-created child account). Tools are thin adapters: To-Do tools call
``TodoService`` directly; chores, gamification and family tools call the
existing router functions, so every business rule lives in exactly one place.
"""

import os
import secrets
from contextlib import contextmanager
from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit

import anyio
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.auth import TokenVerifier
from fastmcp.server.auth.providers.google import GoogleProvider
from fastmcp.server.auth.providers.in_memory import InMemoryOAuthProvider
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
from exsize.security import hash_password
from exsize.services.todo import TodoNotFound, TodoService


async def _api_token_access(token: str) -> AccessToken | None:
    """Resolve a raw exs_ token into an MCP AccessToken owned by its user.

    Shared by the plain-token verifier and the Google-provider fallback; bcrypt
    verification is offloaded to a worker thread so it cannot block the loop.
    """
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


class ExsizeTokenVerifier(TokenVerifier):
    """Verifies ExSize API tokens (exs_...) so MCP requests are authenticated."""

    async def verify_token(self, token: str) -> AccessToken | None:
        return await _api_token_access(token)


class ExsizeGoogleProvider(GoogleProvider):
    """Google OAuth (consent screen included) with an exs_-token fallback.

    ``load_access_token`` is the hook fastmcp's OAuth proxy actually consults
    for every protected request (it verifies the proxy-signed JWT and swaps it
    for the validated upstream Google identity). When that fails — i.e. the
    request carried no Google token at all — we fall back to API tokens so
    existing clients keep working on the same endpoint.
    """

    async def load_access_token(self, token: str) -> AccessToken | None:
        validated = await super().load_access_token(token)
        if validated is not None:
            return validated
        return await _api_token_access(token)


def build_auth():
    """Pick the MCP authentication backend from the environment.

    - MCP_AUTH_IN_MEMORY=1                  -> offline OAuth provider (tests)
    - GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET -> hybrid Google OAuth + exs_ tokens
    - otherwise                             -> exs_ tokens only (current behavior)
    """
    if os.environ.get("MCP_AUTH_IN_MEMORY") == "1":
        # The MCP SDK only accepts HTTPS issuer URLs, hence the https default.
        return InMemoryOAuthProvider(base_url=os.environ.get("MCP_BASE_URL", "https://testserver"))

    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    if client_id and client_secret:
        base_url = os.environ.get("MCP_BASE_URL")
        if not base_url:
            raise RuntimeError(
                "GOOGLE_CLIENT_ID is set but MCP_BASE_URL is missing — set it to the "
                "public site origin, e.g. https://exsize-prod.onrender.com"
            )
        # fastmcp appends the mount path (/mcp) itself: a base_url that already
        # contains it doubles the well-known suffix (/mcp/mcp) and mis-points
        # the OAuth endpoints, so normalize to the bare origin. The Google
        # callback keeps its registered /mcp/auth/callback URI via redirect_path.
        parsed = urlsplit(base_url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        return ExsizeGoogleProvider(
            client_id=client_id,
            client_secret=client_secret,
            base_url=origin,
            redirect_path="/mcp/auth/callback",
            required_scopes=["openid", "email"],
        )
    return ExsizeTokenVerifier()


def _resolve_google_caller(db: Session, email: str) -> User:
    """Map a verified Google email onto an ExSize account.

    An existing account wins (register in the web app with the same email BEFORE
    the first Google login to adopt it); unknown emails get an auto-created
    child account with language pl and a random unusable password (web login
    stays impossible until a reset is built)."""
    user = db.query(User).filter(User.email == email.lower()).first()
    if user is None:
        user = User(
            email=email.lower(),
            password_hash=hash_password(secrets.token_urlsafe(32)),
            role="child",
            language="pl",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


mcp = FastMCP(
    "ExSize",
    instructions=(
        "Family chore & reward manager. Tools act as the authenticated caller: "
        "a parent can manage chores and approve; a child can accept and complete "
        "their own chores. To-Do lists are personal to the caller."
    ),
    auth=build_auth(),
)


@contextmanager
def _caller():
    """Resolve the MCP caller with a fresh DB session.

    Google-path access tokens carry an ``email`` claim and win over anything
    else (their numeric ``sub`` must never be mistaken for a user id);
    exs_ tokens carry scopes={"mcp"} and a numeric client_id pointing at the
    token owner.
    """
    access = get_access_token()
    if access is None:
        raise ToolError("Not authenticated")
    email = (access.claims or {}).get("email")

    db = SessionLocal()
    try:
        if email:
            user = _resolve_google_caller(db, str(email))
        elif "mcp" in set(access.scopes or []) and str(access.client_id).isdigit():
            user = db.query(User).filter(User.id == int(access.client_id)).first()
        else:
            raise ToolError("Not authenticated")
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
