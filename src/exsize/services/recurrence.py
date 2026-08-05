"""Pure recurrence-rule expansion for To-Do items (ExSize 2.0, issue #62).

Stateless function turning a current due date + rule into the next due date.
Kept separate from the persistence layer so the calendar math is trivially
testable and the rule set can grow without touching TodoService.
"""

from datetime import datetime, timedelta


def next_due(current_due: datetime | None, recurrence: str | None) -> datetime | None:
    """Next occurrence's due date for a recurring item, or None if it cannot advance."""
    if current_due is None or recurrence is None:
        return None
    if recurrence == "daily":
        return current_due + timedelta(days=1)
    if recurrence == "weekly":
        return current_due + timedelta(days=7)
    return None
