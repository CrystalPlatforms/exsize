"""Deep module for push subscriptions (ExSize 2.0, issue #64, faza 5).

Narrow public interface hiding ownership scoping, persistence, and VAPID
configuration. Phase 5 only registers/unregisters subscriptions — sending
notifications is phase 6 (issue #65).
"""

import os

from sqlalchemy.orm import Session

from exsize.models import PushSubscription


class PushNotConfigured(Exception):
    """Raised when VAPID keys are not configured (push disabled)."""


class PushService:
    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id

    def subscribe(self, endpoint: str, p256dh: str, auth: str) -> PushSubscription:
        """Register a push subscription for the user (idempotent on endpoint).

        A browser generates one unique endpoint per subscription, so the same
        endpoint re-subscribes (updates keys) instead of creating duplicates.
        """
        existing = (
            self.db.query(PushSubscription)
            .filter(PushSubscription.endpoint == endpoint)
            .first()
        )
        if existing is not None:
            existing.user_id = self.user_id
            existing.p256dh = p256dh
            existing.auth = auth
            self.db.commit()
            self.db.refresh(existing)
            return existing
        sub = PushSubscription(
            user_id=self.user_id,
            endpoint=endpoint,
            p256dh=p256dh,
            auth=auth,
        )
        self.db.add(sub)
        self.db.commit()
        self.db.refresh(sub)
        return sub

    def unsubscribe(self, endpoint: str) -> bool:
        """Remove the user's subscription with this endpoint. Returns True if removed."""
        sub = (
            self.db.query(PushSubscription)
            .filter(
                PushSubscription.endpoint == endpoint,
                PushSubscription.user_id == self.user_id,
            )
            .first()
        )
        if sub is None:
            return False
        self.db.delete(sub)
        self.db.commit()
        return True

    def public_key(self) -> str:
        """The VAPID public key (base64url) to hand to the browser's applicationServerKey."""
        key = os.environ.get("VAPID_PUBLIC_KEY")
        if not key:
            raise PushNotConfigured("VAPID_PUBLIC_KEY is not set")
        return key
