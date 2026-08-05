"""Thin HTTP adapter over TodoService (ExSize 2.0, issue #60).

The service owns the logic; this layer only maps HTTP <-> service calls and
translates TodoNotFound into 404. Lists and items belong to the authenticated
user — no family required.
"""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from exsize.database import get_db
from exsize.deps import get_current_user
from exsize.models import User
from exsize.services.todo import TodoNotFound, TodoService

router = APIRouter(prefix="/api/todo", tags=["todo"])


def _service(user: User, db: Session) -> TodoService:
    return TodoService(db, user.id)


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


def _to_list_response(service: TodoService, todo_list) -> TodoListResponse:
    return TodoListResponse(
        id=todo_list.id,
        name=todo_list.name,
        items=[TodoItemResponse.model_validate(i) for i in service.list_items(todo_list.id)],
    )


# --- Response models ---


class TodoItemResponse(BaseModel):
    id: int
    title: str
    completed: bool
    due_at: datetime | None = None
    recurrence: str | None = None

    model_config = {"from_attributes": True}


class TodoListResponse(BaseModel):
    id: int
    name: str
    items: list[TodoItemResponse] = []

    model_config = {"from_attributes": True}


# --- List endpoints ---


class ListWriteRequest(BaseModel):
    name: str


@router.post("/lists", response_model=TodoListResponse, status_code=status.HTTP_201_CREATED)
def create_list(body: ListWriteRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    service = _service(user, db)
    todo_list = service.create_list(body.name)
    return _to_list_response(service, todo_list)


@router.get("/lists", response_model=list[TodoListResponse])
def list_lists(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    service = _service(user, db)
    return [_to_list_response(service, tl) for tl in service.list_lists()]


@router.put("/lists/{list_id}", response_model=TodoListResponse)
def rename_list(list_id: int, body: ListWriteRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        service = _service(user, db)
        todo_list = service.rename_list(list_id, body.name)
        return _to_list_response(service, todo_list)
    except TodoNotFound:
        raise _not_found()


@router.delete("/lists/{list_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_list(list_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        _service(user, db).delete_list(list_id)
    except TodoNotFound:
        raise _not_found()


# --- Item endpoints ---


class ItemWriteRequest(BaseModel):
    title: str
    due_at: datetime | None = None
    recurrence: Literal["daily", "weekly"] | None = None


@router.post("/lists/{list_id}/items", response_model=TodoItemResponse, status_code=status.HTTP_201_CREATED)
def add_item(list_id: int, body: ItemWriteRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        return _service(user, db).add_item(list_id, body.title, due_at=body.due_at, recurrence=body.recurrence)
    except TodoNotFound:
        raise _not_found()


@router.patch("/items/{item_id}/complete", response_model=TodoItemResponse)
def complete_item(item_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        return _service(user, db).complete_item(item_id)
    except TodoNotFound:
        raise _not_found()


@router.put("/items/{item_id}", response_model=TodoItemResponse)
def edit_item(item_id: int, body: ItemWriteRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        return _service(user, db).edit_item(item_id, body.title)
    except TodoNotFound:
        raise _not_found()


class DueRequest(BaseModel):
    due_at: datetime | None = None


@router.patch("/items/{item_id}/due", response_model=TodoItemResponse)
def set_item_due(item_id: int, body: DueRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        return _service(user, db).set_due_at(item_id, body.due_at)
    except TodoNotFound:
        raise _not_found()


class RecurrenceRequest(BaseModel):
    recurrence: Literal["daily", "weekly"] | None = None


@router.patch("/items/{item_id}/recurrence", response_model=TodoItemResponse)
def set_item_recurrence(item_id: int, body: RecurrenceRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        return _service(user, db).set_recurrence(item_id, body.recurrence)
    except TodoNotFound:
        raise _not_found()


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        _service(user, db).delete_item(item_id)
    except TodoNotFound:
        raise _not_found()


@router.get("/due", response_model=list[TodoItemResponse])
def list_due(
    before: datetime | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Uncompleted items due at or before `before` (defaults to now)."""
    moment = before if before is not None else datetime.now()
    return _service(user, db).list_due_before(moment)
