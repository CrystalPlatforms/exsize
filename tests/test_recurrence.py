from datetime import datetime

from exsize.services.recurrence import next_due


def test_next_due_daily_advances_one_day():
    due = datetime(2026, 8, 5, 9, 0)

    assert next_due(due, "daily") == datetime(2026, 8, 6, 9, 0)


def test_next_due_weekly_advances_seven_days():
    due = datetime(2026, 8, 5, 9, 0)

    assert next_due(due, "weekly") == datetime(2026, 8, 12, 9, 0)


def test_next_due_returns_none_when_no_due_date():
    assert next_due(None, "daily") is None


def test_next_due_returns_none_when_not_recurring():
    due = datetime(2026, 8, 5, 9, 0)

    assert next_due(due, None) is None
