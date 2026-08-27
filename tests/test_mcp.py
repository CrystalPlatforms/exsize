"""End-to-end and unit tests for the MCP server (issues #66, #67 and #76).

Every e2e test talks to the real MCP interface — JSON-RPC 2.0 over HTTP POST /mcp —
authenticated with a Bearer API token minted through the app's REST API. The
MCP caller acts as the token owner with that user's role.

Assumptions encoded here:
- Token: existing exs_... API token (POST /api/cryplo/tokens), non-revoked.
- To-Do via MCP is the token owner's personal To-Do (no family involved).
- Read-only tools never change balances, XP or chore state.
- Issue #76: a Google caller's identity arrives as AccessToken.claims["email"];
  the numeric Google sub in client_id is NEVER used to pick a user. exs_ tokens
  keep scopes={"mcp"} with a numeric client_id (the owner's user id).
- Issue #76: a first-time Google email auto-creates an account with role=child,
  language=pl, no family and an unusable random password; repeat logins reuse it.
- Issue #76: the Google OAuth flow itself (consent screen, redirect to Google)
  needs a browser — here only the offline parts are tested: the auth factory,
  the exs_ fallback on the hybrid provider and the protocol guard.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from exsize.app import app
from exsize.database import Base, get_db

TEST_DATABASE_URL = "sqlite:///test.db"
MCP_ACCEPT = {"Accept": "application/json, text/event-stream"}


@pytest.fixture()
def client():
    """Like conftest's client, but context-managed so the app lifespan runs —
    the MCP session manager only starts under lifespan."""
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    TestingSession = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


# --- Helpers: REST setup + raw MCP protocol ---


def _register(client, email, role):
    resp = client.post("/api/auth/register", json={
        "email": email, "password": "Haslo123!", "role": role, "language": "pl",
    })
    assert resp.status_code == 201, resp.text


def _login(client, email):
    resp = client.post("/api/auth/login", json={"email": email, "password": "Haslo123!"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _api_token(client, jwt):
    resp = client.post("/api/cryplo/tokens", headers={"Authorization": f"Bearer {jwt}"})
    assert resp.status_code == 201, resp.text
    return resp.json()["token"]


def _family_with_child(client, parent_email="mama@test.pl", child_email="syn@test.pl"):
    """Register parent+child, put them in one family; return (jwts, tokens, child_id)."""
    _register(client, parent_email, "parent")
    _register(client, child_email, "child")
    parent_jwt = _login(client, parent_email)
    child_jwt = _login(client, child_email)
    pin = client.post("/api/family", headers={"Authorization": f"Bearer {parent_jwt}"}).json()["pin"]
    join = client.post("/api/family/join", json={"pin": pin}, headers={"Authorization": f"Bearer {child_jwt}"})
    assert join.status_code == 200, join.text
    members = client.get("/api/family", headers={"Authorization": f"Bearer {parent_jwt}"}).json()["members"]
    child_id = next(m["id"] for m in members if m["role"] == "child")
    return parent_jwt, child_jwt, _api_token(client, parent_jwt), _api_token(client, child_jwt), child_id


def _mcp(client, method, token=None, params=None):
    headers = dict(MCP_ACCEPT)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
        headers=headers,
    )


def _tool(client, token, name, arguments):
    """Call a tool through MCP and return its structured result."""
    resp = _mcp(client, "tools/call", token, {"name": name, "arguments": arguments})
    assert resp.status_code == 200, resp.text
    result = resp.json()["result"]
    assert not result.get("isError"), result
    structured = result.get("structuredContent", {})
    return structured.get("result", structured)


def _tool_error(client, token, name, arguments):
    """Call a tool that is expected to fail; return the error text shown to the AI."""
    resp = _mcp(client, "tools/call", token, {"name": name, "arguments": arguments})
    assert resp.status_code == 200, resp.text
    result = resp.json()["result"]
    assert result.get("isError"), result
    return result["content"][0]["text"]


def _balance(client, jwt):
    return client.get("/api/exbucks/balance", headers={"Authorization": f"Bearer {jwt}"}).json()["balance"]


# --- Auth (issue #66: requests without a valid token are rejected) ---


def test_mcp_rejects_requests_without_token(client):
    resp = _mcp(client, "tools/list")
    assert resp.status_code == 401


def test_mcp_rejects_invalid_token(client):
    resp = _mcp(client, "tools/list", token="exs_not-a-real-token")
    assert resp.status_code == 401


def test_mcp_rejects_revoked_token(client):
    _register(client, "user@test.pl", "child")
    jwt = _login(client, "user@test.pl")
    token = _api_token(client, jwt)
    revoke = client.patch("/api/cryplo/tokens/1/revoke", headers={"Authorization": f"Bearer {jwt}"})
    assert revoke.status_code == 200

    resp = _mcp(client, "tools/list", token=token)
    assert resp.status_code == 401


def test_mcp_lists_tools_for_valid_token_holder(client):
    _register(client, "user@test.pl", "child")
    token = _api_token(client, _login(client, "user@test.pl"))

    resp = _mcp(client, "tools/list", token=token)
    assert resp.status_code == 200
    names = {t["name"] for t in resp.json()["result"]["tools"]}
    assert {
        "todo_lists", "todo_add_item", "todo_complete_item",
        "chores_list", "chore_create", "chore_set_status",
        "gamification_profile", "shop_items", "family_info",
    } <= names


# --- To-Do (issue #66) ---


def test_todo_item_created_by_mcp_appears_in_the_web_app(client):
    """Natural request e2e: 'add milk to the Shopping list' via MCP, visible via REST."""
    _register(client, "user@test.pl", "child")
    jwt = _login(client, "user@test.pl")
    token = _api_token(client, jwt)

    created = _tool(client, token, "todo_add_item",
                    {"title": "mleko", "list_name": "Zakupy"})
    assert created["title"] == "mleko"
    assert created["completed"] is False

    web_lists = client.get("/api/todo/lists", headers={"Authorization": f"Bearer {jwt}"}).json()
    assert [lst["name"] for lst in web_lists] == ["Zakupy"]
    assert [i["title"] for i in web_lists[0]["items"]] == ["mleko"]


def test_todo_roundtrip_list_add_and_complete_via_mcp(client):
    _register(client, "user@test.pl", "child")
    jwt = _login(client, "user@test.pl")
    token = _api_token(client, jwt)

    item = _tool(client, token, "todo_add_item", {"title": "wynieść śmieci", "list_name": "Dom"})
    lists = _tool(client, token, "todo_lists", {})
    assert len(lists) == 1
    assert lists[0]["name"] == "Dom"
    assert [i["id"] for i in lists[0]["items"]] == [item["id"]]

    completed = _tool(client, token, "todo_complete_item", {"item_id": item["id"]})
    assert completed["completed"] is True

    web_lists = client.get("/api/todo/lists", headers={"Authorization": f"Bearer {jwt}"}).json()
    assert web_lists[0]["items"][0]["completed"] is True


def test_todo_add_item_requires_list_reference(client):
    _register(client, "user@test.pl", "child")
    token = _api_token(client, _login(client, "user@test.pl"))

    error = _tool_error(client, token, "todo_add_item", {"title": "bez listy"})
    assert "list_name" in error


# --- Chores (issue #67) ---


def test_chore_lifecycle_assign_accept_complete_approve_pays_out(client):
    parent_jwt, child_jwt, parent_token, child_token, child_id = _family_with_child(client)

    chore = _tool(client, parent_token, "chore_create", {
        "name": "Umyj podłogę", "description": "Salon", "exbucks": 10, "assigned_to": child_id,
    })
    assert chore["status"] == "assigned"
    assert chore["assigned_to_name"] == "syn@test.pl"

    assert _tool(client, child_token, "chore_set_status", {"chore_id": chore["id"], "action": "accept"})["status"] == "accepted"
    assert _tool(client, child_token, "chore_set_status", {"chore_id": chore["id"], "action": "complete"})["status"] == "completed"
    assert _tool(client, parent_token, "chore_set_status", {"chore_id": chore["id"], "action": "approve"})["status"] == "approved"

    profile = _tool(client, child_token, "gamification_profile", {})
    assert profile["exbucks_balance"] == 10
    assert profile["xp"] == 10
    assert _balance(client, child_jwt) == 10


def test_chore_role_and_state_rules_are_enforced(client):
    parent_jwt, child_jwt, parent_token, child_token, child_id = _family_with_child(client)

    assert "Only parents" in _tool_error(client, child_token, "chore_create", {
        "name": "X", "description": "X", "exbucks": 1, "assigned_to": child_id,
    })

    chore = _tool(client, parent_token, "chore_create", {
        "name": "X", "description": "X", "exbucks": 1, "assigned_to": child_id,
    })
    assert "not in completed state" in _tool_error(
        client, parent_token, "chore_set_status", {"chore_id": chore["id"], "action": "approve"},
    )


def test_chores_list_answers_what_chores_does_my_child_have(client):
    """Parent asks about the child's chores; each chore carries the assignee's name."""
    parent_jwt, child_jwt, parent_token, child_token, child_id = _family_with_child(client)
    _tool(client, parent_token, "chore_create", {
        "name": "Podlej kwiaty", "description": "", "exbucks": 5, "assigned_to": child_id,
    })

    chores = _tool(client, parent_token, "chores_list", {})
    assert len(chores) == 1
    assert chores[0]["name"] == "Podlej kwiaty"
    assert chores[0]["assigned_to_name"] == "syn@test.pl"


# --- Gamification / shop / family reads (issue #67) ---


def test_gamification_profile_readable_for_child_refused_for_parent(client):
    parent_jwt, child_jwt, parent_token, child_token, child_id = _family_with_child(client)

    profile = _tool(client, child_token, "gamification_profile", {})
    assert profile["level"] == 1
    assert profile["exbucks_balance"] == 0

    assert "Only children" in _tool_error(client, parent_token, "gamification_profile", {})


def test_shop_items_lists_available_items(client):
    _register(client, "user@test.pl", "child")
    token = _api_token(client, _login(client, "user@test.pl"))

    items = _tool(client, token, "shop_items", {})
    assert len(items) > 0
    assert {"id", "type", "value", "label", "price"} <= set(items[0])


def test_family_info_lists_members_with_roles(client):
    parent_jwt, child_jwt, parent_token, child_token, child_id = _family_with_child(client)

    family = _tool(client, parent_token, "family_info", {})
    roles = {m["role"] for m in family["members"]}
    assert roles == {"parent", "child"}
    assert child_id in {m["id"] for m in family["members"]}


def test_readonly_tools_leave_data_unchanged(client):
    """Read-only scopes must not modify what they should not (issue #67 AC)."""
    parent_jwt, child_jwt, parent_token, child_token, child_id = _family_with_child(client)
    _tool(client, parent_token, "chore_create", {
        "name": "Stała", "description": "", "exbucks": 5, "assigned_to": child_id,
    })
    balance_before = _balance(client, child_jwt)

    _tool(client, parent_token, "chores_list", {})
    _tool(client, child_token, "chores_list", {})
    _tool(client, child_token, "gamification_profile", {})
    _tool(client, child_token, "shop_items", {})
    _tool(client, parent_token, "family_info", {})

    assert _balance(client, child_jwt) == balance_before
    profile = _tool(client, child_token, "gamification_profile", {})
    assert profile["xp"] == 0
    chores = _tool(client, parent_token, "chores_list", {})
    assert [c["status"] for c in chores] == ["assigned"]


# --- Issue #76: hybrid Google OAuth + exs_ tokens ---

import asyncio

import pytest
from fastmcp.exceptions import ToolError
from mcp.server.auth.provider import AccessToken

from exsize.database import SessionLocal
from exsize.mcp_server import (
    ExsizeGoogleProvider,
    ExsizeTokenVerifier,
    _caller,
    build_auth,
)
from exsize.models import ApiToken, User
from exsize.security import hash_password

# Real Google subs are 21-digit numbers — that is exactly why a numeric
# client_id alone must never resolve the caller; only claims["email"] does.
GOOGLE_SUB = "107639749558012345678"
GOOGLE_SCOPES = ["openid", "https://www.googleapis.com/auth/userinfo.email"]


def _google_access(email=None):
    claims = {"sub": GOOGLE_SUB, "email": email}
    return AccessToken(
        token="google-access-token",
        client_id=GOOGLE_SUB,
        scopes=GOOGLE_SCOPES,
        claims=claims,
    )


def _exs_access(user_id):
    return AccessToken(token="exs_test", client_id=str(user_id), scopes=["mcp"], claims=None)


def _seed_user(email, role="child", language="pl"):
    db = SessionLocal()
    try:
        user = User(email=email, password_hash=hash_password("Haslo123!"), role=role, language=language)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id
    finally:
        db.close()


@pytest.fixture()
def tables():
    """Tables on the global SessionLocal database — for unit tests that call
    MCP internals directly instead of going through the FastAPI TestClient."""
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_caller_acts_as_the_account_matching_the_google_email(tables, monkeypatch):
    existing_id = _seed_user("mama@test.pl", role="parent")
    monkeypatch.setattr("exsize.mcp_server.get_access_token", lambda: _google_access("mama@test.pl"))

    with _caller() as (user, db):
        assert user.id == existing_id
        assert user.email == "mama@test.pl"
        assert user.role == "parent"
        db.close()


def test_first_google_email_auto_creates_child_account_and_repeats_reuse_it(tables, monkeypatch):
    monkeypatch.setattr("exsize.mcp_server.get_access_token", lambda: _google_access("nowa@test.pl"))

    with _caller() as (user, db):
        assert user.email == "nowa@test.pl"
        assert user.role == "child"
        assert user.language == "pl"
        assert user.family_id is None
        first_id = user.id
        db.close()

    monkeypatch.setattr(
        "exsize.mcp_server.get_access_token", lambda: _google_access("NOWA@test.pl")
    )
    with _caller() as (user, db):
        assert user.id == first_id, "second login must reuse the auto-created account"
        db.close()


def test_numeric_google_sub_is_never_treated_as_user_id(tables, monkeypatch):
    """A token without an email claim must not resolve a user by its digits."""
    _seed_user("mama@test.pl")
    monkeypatch.setattr(
        "exsize.mcp_server.get_access_token",
        lambda: AccessToken(token="t", client_id=GOOGLE_SUB, scopes=GOOGLE_SCOPES, claims={"sub": GOOGLE_SUB}),
    )
    with pytest.raises(ToolError):
        with _caller():
            pass


def test_caller_still_resolves_exs_token_owner(tables, monkeypatch):
    user_id = _seed_user("syn@test.pl")
    monkeypatch.setattr("exsize.mcp_server.get_access_token", lambda: _exs_access(user_id))

    with _caller() as (user, db):
        assert user.id == user_id
        db.close()


# --- Auth factory by environment (issue #76) ---


def test_build_auth_defaults_to_api_tokens_only(monkeypatch):
    for key in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "MCP_AUTH_IN_MEMORY"):
        monkeypatch.delenv(key, raising=False)
    assert isinstance(build_auth(), ExsizeTokenVerifier)


def test_build_auth_hybrid_when_google_keys_present(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-id.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "GOCSPX-test")
    monkeypatch.setenv("MCP_BASE_URL", "https://exsize-prod.onrender.com/mcp")
    provider = build_auth()
    assert isinstance(provider, ExsizeGoogleProvider)
    assert str(provider.base_url) == "https://exsize-prod.onrender.com/mcp"


def test_build_auth_refuses_google_keys_without_public_base_url(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-id.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "GOCSPX-test")
    monkeypatch.delenv("MCP_BASE_URL", raising=False)
    with pytest.raises(RuntimeError):
        build_auth()


def test_build_auth_in_memory_mode_for_offline_tests(monkeypatch):
    from fastmcp.server.auth.providers.in_memory import InMemoryOAuthProvider

    monkeypatch.setenv("MCP_AUTH_IN_MEMORY", "1")
    assert isinstance(build_auth(), InMemoryOAuthProvider)


# --- Hybrid provider: exs_ fallback below the Google OAuth flow (issue #76) ---


def _hybrid_provider():
    return ExsizeGoogleProvider(
        client_id="test-id.apps.googleusercontent.com",
        client_secret="GOCSPX-test",
        base_url="https://testserver/mcp",
        required_scopes=["openid", "email"],
    )


def test_google_provider_falls_back_to_exs_tokens(tables):
    user_id = _seed_user("curl@test.pl")
    db = SessionLocal()
    try:
        db.add(ApiToken(token_hash=hash_password("exs_smoke"), user_id=user_id))
        db.commit()
    finally:
        db.close()

    access = asyncio.run(_hybrid_provider().load_access_token("exs_smoke"))
    assert access is not None
    assert access.client_id == str(user_id)
    assert access.scopes == ["mcp"]


def test_google_provider_rejects_unknown_credentials(tables):
    assert asyncio.run(_hybrid_provider().load_access_token("exs_not-real")) is None


# --- In-memory OAuth mode: same protocol guard, offline (issue #76) ---


def test_in_memory_oauth_mode_still_guards_the_protocol(monkeypatch):
    monkeypatch.setenv("MCP_AUTH_IN_MEMORY", "1")
    from fastmcp import FastMCP

    server = FastMCP("ExSize-Test", auth=build_auth())
    asgi = server.http_app(path="/mcp", stateless_http=True, json_response=True)
    with TestClient(asgi) as oauth_client:
        resp = oauth_client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            headers=MCP_ACCEPT,
        )
    assert resp.status_code == 401
