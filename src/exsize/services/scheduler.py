"""Periodic reminder trigger (ExSize 2.0, issue #65, faza 6).

Thin glue over :class:`ReminderService` + :class:`WebPushSender`: every
``REMINDER_INTERVAL_SECONDS`` it runs one reminder pass in a background task.

The scheduler is opt-in (``REMINDER_SCHEDULER_ENABLED``) so tests and dev runs
don't fire background pushes unintentionally; production sets the flag.
This module is infra (timing), so it is exercised manually rather than unit-tested.
"""

import asyncio
import logging
import os
from datetime import datetime

from exsize.database import SessionLocal
from exsize.services.reminder import ReminderService
from exsize.services.webpush import WebPushSender

logger = logging.getLogger("exsize.reminders")

DEFAULT_INTERVAL_SECONDS = 300.0


def run_reminders_once() -> dict:
    """One reminder pass with a fresh session, the real sender, and now=local now."""
    if not os.environ.get("VAPID_PRIVATE_KEY"):
        logger.debug("reminder run skipped: VAPID_PRIVATE_KEY not configured")
        return {"sent": 0, "removed": 0, "skipped": True}

    sender = WebPushSender()
    db = SessionLocal()
    try:
        result = ReminderService(db, now=datetime.now(), send_push=sender.send).run()
    finally:
        db.close()
    logger.info("reminder run: sent=%s removed=%s", result.get("sent"), result.get("removed"))
    return result


async def reminder_loop(interval: float) -> None:
    while True:
        try:
            run_reminders_once()
        except Exception:  # noqa: BLE001 - pętla tła nie może ubić aplikacji
            logger.exception("reminder loop iteration failed")
        await asyncio.sleep(interval)


def start_reminder_scheduler() -> asyncio.Task | None:
    """Start the background reminder loop. Returns the task, or None if disabled."""
    if os.environ.get("REMINDER_SCHEDULER_ENABLED", "").lower() not in ("1", "true", "yes"):
        return None
    try:
        interval = float(os.environ.get("REMINDER_INTERVAL_SECONDS", DEFAULT_INTERVAL_SECONDS))
    except ValueError:
        interval = DEFAULT_INTERVAL_SECONDS
    try:
        return asyncio.create_task(reminder_loop(interval))
    except RuntimeError:
        # brak działającej pętli zdarzeń
        return None
