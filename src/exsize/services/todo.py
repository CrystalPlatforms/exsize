"""Deep module for the To-Do feature (ExSize 2.0, issue #60).

Narrow public interface hiding ownership scoping and persistence logic.
All operations are scoped to the user passed at construction time; rows
belonging to other users are treated as not found.
"""

from datetime import datetime

from sqlalchemy.orm import Session

from exsize.models import TodoItem, TodoList


class TodoNotFound(Exception):
    """Raised when a list/item does not exist for the owning user."""


class TodoService:
    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id

    # --- Lists ---

    def create_list(self, name: str) -> TodoList:
        todo_list = TodoList(name=name, user_id=self.user_id)
        self.db.add(todo_list)
        self.db.commit()
        self.db.refresh(todo_list)
        return todo_list

    def list_lists(self) -> list[TodoList]:
        return (
            self.db.query(TodoList)
            .filter(TodoList.user_id == self.user_id)
            .order_by(TodoList.id)
            .all()
        )

    def rename_list(self, list_id: int, name: str) -> TodoList:
        todo_list = self._get_owned_list(list_id)
        todo_list.name = name
        self.db.commit()
        self.db.refresh(todo_list)
        return todo_list

    def delete_list(self, list_id: int) -> None:
        todo_list = self._get_owned_list(list_id)
        self.db.query(TodoItem).filter(TodoItem.list_id == list_id).delete()
        self.db.delete(todo_list)
        self.db.commit()

    def _get_owned_list(self, list_id: int) -> TodoList:
        todo_list = (
            self.db.query(TodoList)
            .filter(TodoList.id == list_id, TodoList.user_id == self.user_id)
            .first()
        )
        if not todo_list:
            raise TodoNotFound("List not found")
        return todo_list

    # --- Items ---

    def add_item(self, list_id: int, title: str, due_at: datetime | None = None) -> TodoItem:
        todo_list = self._get_owned_list(list_id)
        item = TodoItem(title=title, list_id=todo_list.id, due_at=due_at)
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def list_items(self, list_id: int) -> list[TodoItem]:
        self._get_owned_list(list_id)
        return (
            self.db.query(TodoItem)
            .filter(TodoItem.list_id == list_id)
            .order_by(TodoItem.id)
            .all()
        )

    def list_due_before(self, moment: datetime) -> list[TodoItem]:
        """Uncompleted items owned by the user whose due_at is at or before `moment`.

        Sorted by due_at ascending (most urgent first). Items without a due date
        or belonging to other users are never returned.
        """
        return (
            self.db.query(TodoItem)
            .join(TodoList, TodoItem.list_id == TodoList.id)
            .filter(TodoList.user_id == self.user_id)
            .filter(TodoItem.completed.is_(False))
            .filter(TodoItem.due_at.isnot(None))
            .filter(TodoItem.due_at <= moment)
            .order_by(TodoItem.due_at)
            .all()
        )

    def _get_owned_item(self, item_id: int) -> TodoItem:
        item = (
            self.db.query(TodoItem)
            .join(TodoList, TodoItem.list_id == TodoList.id)
            .filter(TodoItem.id == item_id, TodoList.user_id == self.user_id)
            .first()
        )
        if not item:
            raise TodoNotFound("Item not found")
        return item

    def complete_item(self, item_id: int) -> TodoItem:
        item = self._get_owned_item(item_id)
        item.completed = not item.completed
        self.db.commit()
        self.db.refresh(item)
        return item

    def edit_item(self, item_id: int, title: str) -> TodoItem:
        item = self._get_owned_item(item_id)
        item.title = title
        self.db.commit()
        self.db.refresh(item)
        return item

    def set_due_at(self, item_id: int, due_at: datetime | None) -> TodoItem:
        item = self._get_owned_item(item_id)
        item.due_at = due_at
        self.db.commit()
        self.db.refresh(item)
        return item

    def delete_item(self, item_id: int) -> None:
        item = self._get_owned_item(item_id)
        self.db.delete(item)
        self.db.commit()
