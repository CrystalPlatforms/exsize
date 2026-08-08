"""Reminder scheduler for To-Do push notifications (ExSize 2.0, issue #65, faza 6).

Deep module turning "which items are due" + "who subscribed" into outgoing push
notifications. The delivery itself is an injected boundary (``send_push``) and the
clock is injected (``now``), so the orchestration is fully testable without crypto.
"""

from datetime import datetime

from sqlalchemy.orm import Session

from exsize.models import PushSubscription, TodoItem, TodoList
from exsize.services.todo import TodoService


class SubscriptionGone(Exception):
    """Raised by send_push when the subscription expired (HTTP 404/410)."""


class PushDeliveryFailed(Exception):
    """Raised by send_push on a transient/other delivery failure."""


class ReminderService:
    def __init__(self, db: Session, *, now: datetime, send_push):
        self.db = db
        self.now = now
        self.send_push = send_push

    def due_items(self) -> list[TodoItem]:
        """Uncompleted To-Do items whose due_at is at or before ``now``.

        Across all users (the scheduler is global), sorted by due_at ascending so
        the most urgent items come first. Items without a due date or already
        completed are never returned.
        """
        return [item for item, _ in self._due_rows()]

    def _due_rows(self) -> list[tuple[TodoItem, int]]:
        """Single query: due items joined to their owner, sorted by due_at.

        One source of truth for "what is due" — :meth:`due_items` projects the
        items and :meth:`_due_items_by_user` groups them, both without re-querying.
        """
        return (
            self.db.query(TodoItem, TodoList.user_id)
            .join(TodoList, TodoItem.list_id == TodoList.id)
            .filter(TodoItem.completed.is_(False))
            .filter(TodoItem.due_at.isnot(None))
            .filter(TodoItem.due_at <= self.now)
            .order_by(TodoItem.due_at)
            .all()
        )

    def run(self):
        """Notify every subscribed user about their due items (digest per user).

        Returns a dict summary ``{"sent": N, "removed": N}`` of pushes attempted
        and dead subscriptions removed. Unsubscribed users are skipped silently.
        """
        sent = 0
        removed = 0
        for user_id, items in self._due_items_by_user().items():
            subs = self._subscriptions_for(user_id)
            if not subs:
                continue
            payload = self._digest_payload(items)
            for sub in subs:
                try:
                    self.send_push(sub, payload)
                except SubscriptionGone:
                    self.db.delete(sub)
                    self.db.commit()
                    removed += 1
                    continue
                except PushDeliveryFailed:
                    # błąd przejściowy — subskrypcja zostaje, spróbujemy ponownie następnym razem
                    continue
                sent += 1
            # cykliczne elementy przypominają ponownie dla każdego nowego wystąpienia:
            # po powiadomieniu przewijamy harmonogram (stare -> ukończone, nowe wystąpienie).
            TodoService(self.db, user_id).advance_overdue_recurrences(self.now)
        return {"sent": sent, "removed": removed}

    def _due_items_by_user(self) -> dict[int, list[TodoItem]]:
        by_user: dict[int, list[TodoItem]] = {}
        for item, user_id in self._due_rows():
            by_user.setdefault(user_id, []).append(item)
        return by_user

    def _subscriptions_for(self, user_id: int) -> list[PushSubscription]:
        return (
            self.db.query(PushSubscription)
            .filter(PushSubscription.user_id == user_id)
            .all()
        )

    @staticmethod
    def _digest_payload(items: list[TodoItem]) -> dict:
        titles = [item.title for item in items]
        return {
            "title": "ExSize",
            "body": f"Masz {len(titles)} element(ów) do zrobienia",
            "count": len(titles),
            "titles": titles,
        }
