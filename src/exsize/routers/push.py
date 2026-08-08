"""Thin HTTP adapter over PushService (ExSize 2.0, issue #64, faza 5).

Maps HTTP <-> service calls. Subscriptions belong to the authenticated user.
"""

import hmac
import os

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from exsize.database import get_db
from exsize.deps import get_current_user, get_optional_user
from exsize.models import User
from exsize.services.push import PushNotConfigured, PushService
from exsize.services.scheduler import run_reminders_once

router = APIRouter(prefix="/api/push", tags=["push"])


def _service(user: User, db: Session) -> PushService:
    return PushService(db, user.id)


class SubscriptionKeys(BaseModel):
    p256dh: str
    auth: str


class SubscribeRequest(BaseModel):
    endpoint: str
    keys: SubscriptionKeys


class PublicKeyResponse(BaseModel):
    public_key: str


class UnsubscribeRequest(BaseModel):
    endpoint: str


@router.get("/vapid-public-key", response_model=PublicKeyResponse)
def vapid_public_key(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        key = _service(user, db).public_key()
    except PushNotConfigured:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Push not configured")
    return PublicKeyResponse(public_key=key)


@router.post("/subscribe", status_code=status.HTTP_201_CREATED)
def subscribe(body: SubscribeRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _service(user, db).subscribe(body.endpoint, body.keys.p256dh, body.keys.auth)
    return {"detail": "subscribed"}


@router.post("/unsubscribe")
def unsubscribe(body: UnsubscribeRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _service(user, db).unsubscribe(body.endpoint)
    return {"detail": "unsubscribed"}


@router.post("/run-reminders")
def run_reminders(
    user: User | None = Depends(get_optional_user),
    reminder_token: str | None = Header(default=None, alias="X-Reminder-Token"),
):
    """Trigger one reminder sweep immediately.

    Also serves as the periodic trigger on hosts where a background task is
    unreliable (e.g. Render free tier cold starts): an external cron can POST
    here with an ``X-Reminder-Token`` header matching ``REMINDER_TRIGGER_TOKEN``.
    A logged-in user's Bearer token also works. Benign — only notifies
    subscribed owners about their own due items.
    """
    secret = os.environ.get("REMINDER_TRIGGER_TOKEN")
    token_ok = bool(secret) and hmac.compare_digest(reminder_token or "", secret)
    if user is None and not token_ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return run_reminders_once()
