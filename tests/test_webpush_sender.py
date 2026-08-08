import json

import pytest

from exsize.models import PushSubscription
from exsize.services.push import PushNotConfigured
from exsize.services.reminder import PushDeliveryFailed, SubscriptionGone
from exsize.services.webpush import WebPushSender


class _FakeResponse:
    def __init__(self, status_code):
        self.status_code = status_code


def _sub(endpoint="https://push.example/abc"):
    return PushSubscription(
        user_id=1, endpoint=endpoint, p256dh="p256dh-key", auth="auth-key"
    )


def _deliver_returning(status_code):
    """A fake deliverer that records its call args and returns a fixed status."""
    seen = {}

    def deliver(*, subscription_info, data, vapid_private_key, vapid_claims):
        seen["subscription_info"] = subscription_info
        seen["data"] = data
        seen["vapid_private_key"] = vapid_private_key
        seen["vapid_claims"] = vapid_claims
        return _FakeResponse(status_code)

    return deliver, seen


# --- success path: 2xx delivers without raising ---


def test_send_succeeds_on_2xx_and_passes_subscription_and_json_payload(monkeypatch):
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "-----BEGIN PRIVATE KEY-----\nfake\n-----END PRIVATE KEY-----\n")
    monkeypatch.setenv("VAPID_SUBJECT", "mailto:admin@exsize.app")
    deliver, seen = _deliver_returning(201)
    sender = WebPushSender(deliver=deliver)

    sender.send(_sub(), {"title": "ExSize", "titles": ["Mleko"]})

    assert seen["subscription_info"]["endpoint"] == "https://push.example/abc"
    assert seen["subscription_info"]["keys"] == {"p256dh": "p256dh-key", "auth": "auth-key"}
    assert json.loads(seen["data"]) == {"title": "ExSize", "titles": ["Mleko"]}
    assert seen["vapid_claims"]["sub"] == "mailto:admin@exsize.app"


# --- 410 Gone -> SubscriptionGone ---


def test_send_raises_subscription_gone_on_410(monkeypatch):
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "fake-key")
    deliver, _ = _deliver_returning(410)
    sender = WebPushSender(deliver=deliver)

    with pytest.raises(SubscriptionGone):
        sender.send(_sub(), {"title": "x"})


def test_send_raises_subscription_gone_on_404(monkeypatch):
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "fake-key")
    deliver, _ = _deliver_returning(404)
    sender = WebPushSender(deliver=deliver)

    with pytest.raises(SubscriptionGone):
        sender.send(_sub(), {"title": "x"})


# --- other HTTP failure -> PushDeliveryFailed ---


def test_send_raises_delivery_failed_on_5xx(monkeypatch):
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "fake-key")
    deliver, _ = _deliver_returning(500)
    sender = WebPushSender(deliver=deliver)

    with pytest.raises(PushDeliveryFailed):
        sender.send(_sub(), {"title": "x"})


# --- deliver itself throws -> PushDeliveryFailed ---


def test_send_raises_delivery_failed_when_deliver_raises(monkeypatch):
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "fake-key")

    def deliver(**kwargs):
        raise ConnectionError("timeout")

    sender = WebPushSender(deliver=deliver)

    with pytest.raises(PushDeliveryFailed):
        sender.send(_sub(), {"title": "x"})


# --- missing private key -> PushNotConfigured, deliver not called ---


def test_send_raises_not_configured_without_private_key(monkeypatch):
    monkeypatch.delenv("VAPID_PRIVATE_KEY", raising=False)
    called = []

    def deliver(**kwargs):
        called.append(True)
        return _FakeResponse(200)

    sender = WebPushSender(deliver=deliver)

    with pytest.raises(PushNotConfigured):
        sender.send(_sub(), {"title": "x"})
    assert called == []  # deliver nie wywołane bez klucza
