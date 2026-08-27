"""End-to-end tests for the MCP server (issues #66 and #67).

Every test talks to the real MCP interface — JSON-RPC 2.0 over HTTP POST /mcp —
authenticated with a Bearer API token minted through the app's REST API. The
MCP caller acts as the token owner with that user's role.

Assumptions encoded here:
- Token: existing exs_... API token (POST /api/cryplo/tokens), non-revoked.
- To-Do via MCP is the token owner's personal To-Do (no family involved).
- Read-only tools never change balances, XP or chore state.
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
