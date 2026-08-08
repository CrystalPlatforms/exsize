"""Thin HTTP adapter over PushService (ExSize 2.0, issue #64, faza 5).

Maps HTTP <-> service calls. Subscriptions belong to the authenticated user.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from exsize.database import get_db
from exsize.deps import get_current_user
from exsize.models import User
from exsize.services.push import PushNotConfigured, PushService

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
