"""Web Push delivery boundary (ExSize 2.0, issue #65, faza 6).

Thin deep module hiding the Web Push crypto + HTTP behind one method.
The actual RFC 8291/8292 work (payload encryption, VAPID JWT) is delegated to
``pywebpush``; this module owns the *contract* the rest of the app relies on:

* success → no exception
* subscription expired (404/410) → :class:`SubscriptionGone`
* any other failure → :class:`PushDeliveryFailed`
* VAPID not configured → :class:`PushNotConfigured`

The deliverer is injectable so the contract is tested without real crypto.
"""

import json
import os

from exsize.models import PushSubscription
from exsize.services.push import PushNotConfigured
from exsize.services.reminder import PushDeliveryFailed, SubscriptionGone


class _StatusResponse:
    """Minimal response-like object exposing only what :meth:`send` inspects."""

    def __init__(self, status_code):
        self.status_code = status_code


def _pywebpush_deliver(*, subscription_info, data, vapid_private_key, vapid_claims):
    """Default deliverer: real Web Push via pywebpush, normalised to a status code."""
    from pywebpush import WebPushException, webpush

    try:
        response = webpush(
            subscription_info=subscription_info,
            data=data,
            vapid_private_key=vapid_private_key,
            vapid_claims=vapid_claims,
        )
        return _StatusResponse(response.status_code)
    except WebPushException as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status is not None:
            return _StatusResponse(status)  # błąd HTTP -> mapujemy w send()
        raise  # błąd nie-HTTP (np. krypto/timeout) -> PushDeliveryFailed w send()


class WebPushSender:
    def __init__(self, *, deliver=None):
        self._deliver = deliver or _pywebpush_deliver

    def send(self, subscription: PushSubscription, payload: dict) -> None:
        """Deliver ``payload`` (JSON) to ``subscription``'s endpoint.

        Raises :class:`PushNotConfigured` if VAPID is unset,
        :class:`SubscriptionGone` for 404/410, :class:`PushDeliveryFailed` otherwise.
        """
        private_key = os.environ.get("VAPID_PRIVATE_KEY")
        if not private_key:
            raise PushNotConfigured("VAPID_PRIVATE_KEY is not set")

        subscription_info = {
            "endpoint": subscription.endpoint,
            "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
        }
        claims = {"sub": os.environ.get("VAPID_SUBJECT", "mailto:admin@exsize.app")}

        try:
            response = self._deliver(
                subscription_info=subscription_info,
                data=json.dumps(payload),
                vapid_private_key=private_key,
                vapid_claims=claims,
            )
        except Exception as exc:  # noqa: BLE001 - cała granica to nasz kontrakt
            raise PushDeliveryFailed(str(exc)) from exc

        status = getattr(response, "status_code", None)
        if status in (404, 410):
            raise SubscriptionGone(f"subscription endpoint returned {status}")
        if status is None or not (200 <= status < 300):
            raise PushDeliveryFailed(f"endpoint returned {status}")
