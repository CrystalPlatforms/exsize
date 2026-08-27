def test_register_with_email_and_password(client):
    response = client.post("/api/auth/register", json={
        "email": "parent@example.com",
        "password": "securepass123",
        "role": "parent",
        "language": "en",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "parent@example.com"
    assert data["role"] == "parent"
    assert data["language"] == "en"
    assert "id" in data
    assert "password" not in data


def test_register_as_child(client):
    response = client.post("/api/auth/register", json={
        "email": "kid@example.com",
        "password": "childpass123",
        "role": "child",
        "language": "pl",
    })
    assert response.status_code == 201
    assert response.json()["role"] == "child"


def test_register_admin_role_is_rejected(client):
    response = client.post("/api/auth/register", json={
        "email": "admin@example.com",
        "password": "adminpass",
        "role": "admin",
    })
    assert response.status_code == 422


def test_admin_login_with_wrong_secret_shows_invalid_credentials(client):
    resp = client.post("/api/auth/admin-login", json={
        "admin_secret": "wrong-secret",
    })
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid credentials"


def test_admin_login_without_admin_account_shows_invalid_credentials(client):
    resp = client.post("/api/auth/admin-login", json={
        "admin_secret": "test-admin-secret",
    })
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid credentials"


def test_register_rejects_invalid_role(client):
    response = client.post("/api/auth/register", json={
        "email": "bad@example.com",
        "password": "pass123",
        "role": "superuser",
        "language": "en",
    })
    assert response.status_code == 422


def test_login_returns_token(client):
    client.post("/api/auth/register", json={
        "email": "user@example.com",
        "password": "mypassword",
        "role": "parent",
    })
    response = client.post("/api/auth/login", json={
        "email": "user@example.com",
        "password": "mypassword",
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client):
    client.post("/api/auth/register", json={
        "email": "user@example.com",
        "password": "mypassword",
        "role": "parent",
    })
    response = client.post("/api/auth/login", json={
        "email": "user@example.com",
        "password": "wrongpassword",
    })
    assert response.status_code == 401


def test_login_nonexistent_user(client):
    response = client.post("/api/auth/login", json={
        "email": "nobody@example.com",
        "password": "whatever",
    })
    assert response.status_code == 401


def _register_and_login(client, email="user@example.com", password="mypassword", role="parent"):
    client.post("/api/auth/register", json={
        "email": email, "password": password, "role": role,
    })
    resp = client.post("/api/auth/login", json={
        "email": email, "password": password,
    })
    return resp.json()["access_token"]


def test_dashboard_requires_family(client):
    token = _register_and_login(client)
    response = client.get("/api/dashboard", headers={
        "Authorization": f"Bearer {token}",
    })
    assert response.status_code == 400


def test_dashboard_rejected_without_token(client):
    response = client.get("/api/dashboard")
    assert response.status_code == 403 or response.status_code == 401


def test_dashboard_rejected_with_invalid_token(client):
    response = client.get("/api/dashboard", headers={
        "Authorization": "Bearer invalid-garbage-token",
    })
    assert response.status_code == 401


def test_get_settings(client):
    token = _register_and_login(client)
    response = client.get("/api/settings", headers={
        "Authorization": f"Bearer {token}",
    })
    assert response.status_code == 200
    assert response.json()["language"] == "en"


def test_update_language_preference(client):
    token = _register_and_login(client)
    response = client.patch("/api/settings", json={"language": "pl"}, headers={
        "Authorization": f"Bearer {token}",
    })
    assert response.status_code == 200
    assert response.json()["language"] == "pl"


def test_language_persists_across_sessions(client):
    # Register, login, change language to PL
    token1 = _register_and_login(client)
    client.patch("/api/settings", json={"language": "pl"}, headers={
        "Authorization": f"Bearer {token1}",
    })

    # Login again (new session) and verify language is still PL
    resp = client.post("/api/auth/login", json={
        "email": "user@example.com",
        "password": "mypassword",
    })
    token2 = resp.json()["access_token"]
    response = client.get("/api/settings", headers={
        "Authorization": f"Bearer {token2}",
    })
    assert response.status_code == 200
    assert response.json()["language"] == "pl"


def test_me_returns_current_user(client):
    token = _register_and_login(client)
    response = client.get("/api/auth/me", headers={
        "Authorization": f"Bearer {token}",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "user@example.com"
    assert data["role"] == "parent"
    assert data["language"] == "en"


# --- Phone number setting (issue #68: schema prep; PII — db only) ---


def test_get_settings_shows_empty_phone_number_by_default(client):
    token = _register_and_login(client)
    response = client.get("/api/settings", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["phone_number"] is None


def test_phone_number_is_saved_and_persisted(client):
    token = _register_and_login(client)
    patched = client.patch("/api/settings", json={
        "language": "en", "phone_number": "+48 600 700 800",
    }, headers={"Authorization": f"Bearer {token}"})
    assert patched.status_code == 200
    assert patched.json()["phone_number"] == "+48 600 700 800"

    reread = client.get("/api/settings", headers={"Authorization": f"Bearer {token}"})
    assert reread.json()["phone_number"] == "+48 600 700 800"


def test_phone_number_stays_untouched_when_key_is_omitted(client):
    token = _register_and_login(client)
    client.patch("/api/settings", json={
        "language": "en", "phone_number": "+48 600 700 800",
    }, headers={"Authorization": f"Bearer {token}"})

    untouched = client.patch("/api/settings", json={"language": "pl"}, headers={
        "Authorization": f"Bearer {token}",
    })
    assert untouched.status_code == 200
    assert untouched.json()["language"] == "pl"
    assert untouched.json()["phone_number"] == "+48 600 700 800"


def test_phone_number_can_be_cleared_with_null(client):
    token = _register_and_login(client)
    client.patch("/api/settings", json={
        "language": "en", "phone_number": "+48 600 700 800",
    }, headers={"Authorization": f"Bearer {token}"})

    cleared = client.patch("/api/settings", json={"language": "en", "phone_number": None}, headers={
        "Authorization": f"Bearer {token}",
    })
    assert cleared.status_code == 200
    assert cleared.json()["phone_number"] is None
