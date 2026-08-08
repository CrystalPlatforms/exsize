import os

from exsize.database import get_db
from exsize.models import PushSubscription


def _register_and_login(client, email="user@example.com", password="mypassword", role="parent"):
    client.post("/api/auth/register", json={
        "email": email, "password": password, "role": role,
    })
    resp = client.post("/api/auth/login", json={
        "email": email, "password": password,
    })
    return resp.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _sub(endpoint="https://fcm.googleapis.com/fcm/send/abc"):
    return {
        "endpoint": endpoint,
        "keys": {"p256dh": "p256dh-key", "auth": "auth-key"},
    }


# --- B1: subscribe saves a subscription scoped to the user ---


def test_subscribe_creates_subscription_for_user(client):
    token = _register_and_login(client, email="alice@example.com")
    resp = client.post("/api/push/subscribe", json=_sub(), headers=_auth(token))
    assert resp.status_code == 201
    db = next(client.app.dependency_overrides[get_db]())
    rows = db.query(PushSubscription).all()
    assert len(rows) == 1
    assert rows[0].endpoint == "https://fcm.googleapis.com/fcm/send/abc"
    assert rows[0].p256dh == "p256dh-key"
    assert rows[0].auth == "auth-key"


# --- B2: vapid public key endpoint returns configured key ---


def test_vapid_public_key_returns_configured_key(client, monkeypatch):
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "BK_test_public_key_base64url")
    token = _register_and_login(client, email="bob@example.com")
    resp = client.get("/api/push/vapid-public-key", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["public_key"] == "BK_test_public_key_base64url"


# --- B3: missing VAPID_PUBLIC_KEY -> 503 (push disabled gracefully) ---


def test_vapid_public_key_returns_503_when_not_configured(client, monkeypatch):
    monkeypatch.delenv("VAPID_PUBLIC_KEY", raising=False)
    token = _register_and_login(client, email="cara@example.com")
    resp = client.get("/api/push/vapid-public-key", headers=_auth(token))
    assert resp.status_code == 503


# --- B4: unsubscribe removes the user's subscription ---


def test_unsubscribe_removes_subscription(client):
    token = _register_and_login(client, email="dave@example.com")
    client.post("/api/push/subscribe", json=_sub(), headers=_auth(token))
    resp = client.post(
        "/api/push/unsubscribe",
        json={"endpoint": "https://fcm.googleapis.com/fcm/send/abc"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    db = next(client.app.dependency_overrides[get_db]())
    assert db.query(PushSubscription).count() == 0


# --- B5: subscribe is idempotent on endpoint (upsert, no duplicates) ---


def test_subscribe_is_idempotent_on_endpoint(client):
    token = _register_and_login(client, email="eve@example.com")
    client.post("/api/push/subscribe", json=_sub(), headers=_auth(token))
    # Re-subscribe the same endpoint with rotated keys
    resp = client.post(
        "/api/push/subscribe",
        json=_sub() | {"keys": {"p256dh": "new-p256dh", "auth": "new-auth"}},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    db = next(client.app.dependency_overrides[get_db]())
    rows = db.query(PushSubscription).all()
    assert len(rows) == 1  # no duplicate
    assert rows[0].p256dh == "new-p256dh"
    assert rows[0].auth == "new-auth"


# --- B6: all endpoints require authentication ---


def test_endpoints_require_authentication(client):
    assert client.get("/api/push/vapid-public-key").status_code in (401, 403)
    assert client.post("/api/push/subscribe", json=_sub()).status_code in (401, 403)
    assert client.post(
        "/api/push/unsubscribe", json={"endpoint": "x"}
    ).status_code in (401, 403)


# --- B7: subscriptions are scoped to the user ---


def test_unsubscribe_is_scoped_to_owner(client):
    alice = _register_and_login(client, email="alice7@example.com")
    bob = _register_and_login(client, email="bob7@example.com")
    client.post("/api/push/subscribe", json=_sub(), headers=_auth(alice))
    # Bob cannot remove Alice's subscription (endpoint owned by Alice)
    client.post(
        "/api/push/unsubscribe",
        json={"endpoint": "https://fcm.googleapis.com/fcm/send/abc"},
        headers=_auth(bob),
    )
    db = next(client.app.dependency_overrides[get_db]())
    rows = db.query(PushSubscription).all()
    assert len(rows) == 1  # Alice's subscription survived Bob's unsubscribe attempt
