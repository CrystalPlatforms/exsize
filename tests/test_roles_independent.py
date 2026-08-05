"""Charakterystyka kontraktu ról dla ExSize 2.0 (issue #63).

Zamyka w testach gwarancje "To-Do bez rodziny" + modelu ról:
- każdy (rodzic/dziecko) bez rodziny może w pełni używać To-Do;
- niezależny użytkownik jest poprawnie blokowany z funkcji rodzinnych/nagród;
- rodzic nigdy nie nagradza samego siebie exbucks.

Backend już ten kontrakt spełnia — te testy to siatka bezpieczeństwa chroniąca
przed regresją (kryterium #63: "nie zepsuć istniejącego flow").
"""


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


def _setup_family_with_child(client):
    """Rodzina z jednym rodzicem i jednym dzieckiem. Zwraca (parent_token, child_token, child_id)."""
    parent_token = _register_and_login(client, email="parent@example.com")
    family = client.post("/api/family", headers=_auth(parent_token)).json()

    child_token = _register_and_login(client, email="child@example.com", role="child")
    client.post("/api/family/join", json={"pin": family["pin"]}, headers=_auth(child_token))

    members = client.get("/api/family", headers=_auth(parent_token)).json()["members"]
    child_id = next(m["id"] for m in members if m["role"] == "child")
    return parent_token, child_token, child_id


# --- To-Do działa bez rodziny ---


def test_parent_without_family_creates_todo_list(client):
    token = _register_and_login(client, email="solo@example.com")
    # Nie tworzymy rodziny — użytkownik jest w pełni niezależny.

    resp = client.post("/api/todo/lists", json={"name": "Praca"}, headers=_auth(token))

    assert resp.status_code == 201
    assert resp.json()["name"] == "Praca"
    assert resp.json()["items"] == []


def test_child_without_family_uses_todo(client):
    # Dziecko zarejestrowane, ale jeszcze bez rodziny — To-Do ma działać od razu.
    token = _register_and_login(client, email="kid@example.com", role="child")
    todo_list = client.post("/api/todo/lists", json={"name": "Lekcje"}, headers=_auth(token)).json()

    item = client.post(
        f"/api/todo/lists/{todo_list['id']}/items", json={"title": "Matematyka"}, headers=_auth(token),
    )

    assert item.status_code == 201
    lists = client.get("/api/todo/lists", headers=_auth(token)).json()
    assert [i["title"] for i in lists[0]["items"]] == ["Matematyka"]


# --- Niezależny użytkownik zablokowany z funkcji rodzinnych/nagród ---


def test_independent_parent_blocked_from_family_features(client):
    token = _register_and_login(client, email="solo@example.com")

    # Dashboard wymaga rodziny
    dashboard = client.get("/api/dashboard", headers=_auth(token))
    assert dashboard.status_code == 400

    # Tworzenie zadania wymaga rodziny
    create_task = client.post("/api/tasks", json={
        "name": "x", "description": "x", "exbucks": 1, "assigned_to": 1,
    }, headers=_auth(token))
    assert create_task.status_code == 400

    # Profil gamifikacji jest tylko dla dzieci
    gamif = client.get("/api/gamification/profile", headers=_auth(token))
    assert gamif.status_code == 403

    # Szczegóły rodziny wymagają członkostwa
    family = client.get("/api/family", headers=_auth(token))
    assert family.status_code == 404


# --- Rodzic nigdy nie nagradza samego siebie exbucks ---


def test_parent_balance_stays_zero_after_child_reward(client):
    """Nagrody z zatwierdzonego zadania trafiają do dziecka, nigdy do rodzica."""
    parent_token, child_token, child_id = _setup_family_with_child(client)

    task = client.post("/api/tasks", json={
        "name": "Pushups", "description": "d", "exbucks": 5, "assigned_to": child_id,
    }, headers=_auth(parent_token)).json()
    client.patch(f"/api/tasks/{task['id']}/accept", headers=_auth(child_token))
    client.patch(f"/api/tasks/{task['id']}/complete", headers=_auth(child_token))
    client.patch(f"/api/tasks/{task['id']}/approve", headers=_auth(parent_token))

    # Dziecko zarobiło, rodzic — nie.
    assert client.get("/api/exbucks/balance", headers=_auth(child_token)).json()["balance"] == 5
    assert client.get("/api/exbucks/balance", headers=_auth(parent_token)).json()["balance"] == 0


def test_parent_cannot_assign_penalty_to_self(client):
    """Rodzic podający własne id jako cel kary — brak dopasowania (kara tylko do dzieci)."""
    parent_token, _child_token, _child_id = _setup_family_with_child(client)
    parent_id = client.get("/api/auth/me", headers=_auth(parent_token)).json()["id"]

    resp = client.post("/api/exbucks/penalty", json={
        "child_id": parent_id, "amount": 5, "reason": "próba samonagrody",
    }, headers=_auth(parent_token))

    assert resp.status_code == 404


def test_parent_cannot_be_assigned_task(client):
    """Zadanie można przypisać tylko dziecku z rodziny — nigdy rodzicowi."""
    parent_token, _child_token, _child_id = _setup_family_with_child(client)
    parent_id = client.get("/api/auth/me", headers=_auth(parent_token)).json()["id"]

    resp = client.post("/api/tasks", json={
        "name": "x", "description": "x", "exbucks": 5, "assigned_to": parent_id,
    }, headers=_auth(parent_token))

    assert resp.status_code == 404
