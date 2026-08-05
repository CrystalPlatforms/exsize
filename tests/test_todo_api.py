def _register_and_login(client, email="user@example.com", password="mypassword", role="parent"):
    client.post("/api/auth/register", json={
        "email": email, "password": password, "role": role,
    })
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# --- Tracer bullet: create list + add items + survive refresh ---


def test_create_list_returns_201(client):
    token = _register_and_login(client, email="alice@example.com")

    resp = client.post("/api/todo/lists", json={"name": "Zakupy"}, headers=_auth(token))

    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Zakupy"
    assert data["items"] == []


def test_add_item_and_survive_refresh(client):
    token = _register_and_login(client, email="alice@example.com")
    todo_list = client.post("/api/todo/lists", json={"name": "Zakupy"}, headers=_auth(token)).json()

    client.post(f"/api/todo/lists/{todo_list['id']}/items", json={"title": "Mleko"}, headers=_auth(token))
    client.post(f"/api/todo/lists/{todo_list['id']}/items", json={"title": "Chleb"}, headers=_auth(token))

    # "Refresh" — a fresh GET shows the persisted items
    resp = client.get("/api/todo/lists", headers=_auth(token))

    assert resp.status_code == 200
    lists = resp.json()
    assert len(lists) == 1
    items = lists[0]["items"]
    assert [i["title"] for i in items] == ["Mleko", "Chleb"]
    assert all(i["completed"] is False for i in items)


# --- Complete (check off) ---


def test_complete_item_persists_after_refresh(client):
    token = _register_and_login(client, email="alice@example.com")
    todo_list = client.post("/api/todo/lists", json={"name": "Zakupy"}, headers=_auth(token)).json()
    item = client.post(
        f"/api/todo/lists/{todo_list['id']}/items", json={"title": "Mleko"}, headers=_auth(token),
    ).json()

    resp = client.patch(f"/api/todo/items/{item['id']}/complete", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["completed"] is True

    # "Refresh" — completed state persists
    lists = client.get("/api/todo/lists", headers=_auth(token)).json()
    assert lists[0]["items"][0]["completed"] is True


def test_complete_item_toggles_off(client):
    token = _register_and_login(client, email="alice@example.com")
    todo_list = client.post("/api/todo/lists", json={"name": "Zakupy"}, headers=_auth(token)).json()
    item = client.post(
        f"/api/todo/lists/{todo_list['id']}/items", json={"title": "Mleko"}, headers=_auth(token),
    ).json()

    client.patch(f"/api/todo/items/{item['id']}/complete", headers=_auth(token))
    toggled = client.patch(f"/api/todo/items/{item['id']}/complete", headers=_auth(token))

    assert toggled.status_code == 200
    assert toggled.json()["completed"] is False


# --- Edit + delete items ---


def test_edit_item(client):
    token = _register_and_login(client, email="alice@example.com")
    todo_list = client.post("/api/todo/lists", json={"name": "Zakupy"}, headers=_auth(token)).json()
    item = client.post(
        f"/api/todo/lists/{todo_list['id']}/items", json={"title": "Mleko"}, headers=_auth(token),
    ).json()

    resp = client.put(f"/api/todo/items/{item['id']}", json={"title": "Mleko 2%"}, headers=_auth(token))

    assert resp.status_code == 200
    assert resp.json()["title"] == "Mleko 2%"


def test_delete_item(client):
    token = _register_and_login(client, email="alice@example.com")
    todo_list = client.post("/api/todo/lists", json={"name": "Zakupy"}, headers=_auth(token)).json()
    item = client.post(
        f"/api/todo/lists/{todo_list['id']}/items", json={"title": "Mleko"}, headers=_auth(token),
    ).json()

    resp = client.delete(f"/api/todo/items/{item['id']}", headers=_auth(token))
    assert resp.status_code == 204

    lists = client.get("/api/todo/lists", headers=_auth(token)).json()
    assert lists[0]["items"] == []


# --- Due date (issue #61) ---


def test_add_item_with_due_at_returns_it(client):
    token = _register_and_login(client, email="alice@example.com")
    todo_list = client.post("/api/todo/lists", json={"name": "Zakupy"}, headers=_auth(token)).json()

    due_iso = "2026-08-05T18:00:00"
    resp = client.post(
        f"/api/todo/lists/{todo_list['id']}/items",
        json={"title": "Mleko", "due_at": due_iso},
        headers=_auth(token),
    )

    assert resp.status_code == 201
    assert resp.json()["due_at"] == due_iso


def test_add_item_without_due_at_returns_null(client):
    token = _register_and_login(client, email="alice@example.com")
    todo_list = client.post("/api/todo/lists", json={"name": "Zakupy"}, headers=_auth(token)).json()

    resp = client.post(
        f"/api/todo/lists/{todo_list['id']}/items",
        json={"title": "Mleko"},
        headers=_auth(token),
    )

    assert resp.status_code == 201
    assert resp.json()["due_at"] is None


def test_set_due_at_endpoint_sets_due_on_item(client):
    token = _register_and_login(client, email="alice@example.com")
    todo_list = client.post("/api/todo/lists", json={"name": "Zakupy"}, headers=_auth(token)).json()
    item = client.post(
        f"/api/todo/lists/{todo_list['id']}/items", json={"title": "Mleko"}, headers=_auth(token),
    ).json()

    due_iso = "2026-08-06T09:30:00"
    resp = client.patch(
        f"/api/todo/items/{item['id']}/due",
        json={"due_at": due_iso},
        headers=_auth(token),
    )

    assert resp.status_code == 200
    assert resp.json()["due_at"] == due_iso

    # Persists across refresh
    lists = client.get("/api/todo/lists", headers=_auth(token)).json()
    assert lists[0]["items"][0]["due_at"] == due_iso


def test_set_due_at_endpoint_clears_due_with_null(client):
    token = _register_and_login(client, email="alice@example.com")
    todo_list = client.post("/api/todo/lists", json={"name": "Zakupy"}, headers=_auth(token)).json()
    item = client.post(
        f"/api/todo/lists/{todo_list['id']}/items",
        json={"title": "Mleko", "due_at": "2026-08-05T18:00:00"},
        headers=_auth(token),
    ).json()

    resp = client.patch(
        f"/api/todo/items/{item['id']}/due",
        json={"due_at": None},
        headers=_auth(token),
    )

    assert resp.status_code == 200
    assert resp.json()["due_at"] is None


def test_due_endpoint_returns_uncompleted_items_due_before_moment(client):
    token = _register_and_login(client, email="alice@example.com")
    todo_list = client.post("/api/todo/lists", json={"name": "Zakupy"}, headers=_auth(token)).json()

    def add(title, due_at):
        return client.post(
            f"/api/todo/lists/{todo_list['id']}/items",
            json={"title": title, "due_at": due_at},
            headers=_auth(token),
        ).json()

    overdue = add("przeterminowane", "2026-08-04T09:00:00")
    future = add("w przyszlosci", "2026-08-10T09:00:00")
    done_overdue = add("odhaczone", "2026-08-04T08:00:00")
    client.patch(f"/api/todo/items/{done_overdue['id']}/complete", headers=_auth(token))

    resp = client.get("/api/todo/due?before=2026-08-05T12:00:00", headers=_auth(token))

    assert resp.status_code == 200
    ids = [item["id"] for item in resp.json()]
    assert ids == [overdue["id"]]


def test_due_endpoint_excludes_other_users_items(client):
    alice = _register_and_login(client, email="alice@example.com")
    bob = _register_and_login(client, email="bob@example.com")
    alice_list = client.post("/api/todo/lists", json={"name": "Alice"}, headers=_auth(alice)).json()
    client.post(
        f"/api/todo/lists/{alice_list['id']}/items",
        json={"title": "alice due", "due_at": "2000-01-01T00:00:00"},
        headers=_auth(alice),
    )

    resp = client.get("/api/todo/due", headers=_auth(bob))

    assert resp.status_code == 200
    assert resp.json() == []


# --- Rename + delete lists ---


def test_rename_list(client):
    token = _register_and_login(client, email="alice@example.com")
    todo_list = client.post("/api/todo/lists", json={"name": "Zakupy"}, headers=_auth(token)).json()

    resp = client.put(f"/api/todo/lists/{todo_list['id']}", json={"name": "Codzienne"}, headers=_auth(token))

    assert resp.status_code == 200
    assert resp.json()["name"] == "Codzienne"


def test_delete_list(client):
    token = _register_and_login(client, email="alice@example.com")
    todo_list = client.post("/api/todo/lists", json={"name": "Zakupy"}, headers=_auth(token)).json()
    client.post(
        f"/api/todo/lists/{todo_list['id']}/items", json={"title": "Mleko"}, headers=_auth(token),
    )

    resp = client.delete(f"/api/todo/lists/{todo_list['id']}", headers=_auth(token))
    assert resp.status_code == 204

    lists = client.get("/api/todo/lists", headers=_auth(token)).json()
    assert lists == []


# --- Ownership isolation between users ---


def test_user_cannot_see_other_users_lists(client):
    alice = _register_and_login(client, email="alice@example.com")
    bob = _register_and_login(client, email="bob@example.com")
    client.post("/api/todo/lists", json={"name": "Alice's list"}, headers=_auth(alice))

    bob_lists = client.get("/api/todo/lists", headers=_auth(bob)).json()

    assert bob_lists == []


def test_user_cannot_complete_other_users_item(client):
    alice = _register_and_login(client, email="alice@example.com")
    bob = _register_and_login(client, email="bob@example.com")
    alice_list = client.post("/api/todo/lists", json={"name": "Alice's list"}, headers=_auth(alice)).json()
    alice_item = client.post(
        f"/api/todo/lists/{alice_list['id']}/items", json={"title": "Mleko"}, headers=_auth(alice),
    ).json()

    resp = client.patch(f"/api/todo/items/{alice_item['id']}/complete", headers=_auth(bob))

    assert resp.status_code == 404


def test_requires_authentication(client):
    resp = client.get("/api/todo/lists")
    assert resp.status_code == 401
