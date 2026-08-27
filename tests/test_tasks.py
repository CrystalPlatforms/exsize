def _register_and_login(client, email="parent@example.com", password="mypassword", role="parent"):
    client.post("/api/auth/register", json={
        "email": email, "password": password, "role": role,
    })
    resp = client.post("/api/auth/login", json={
        "email": email, "password": password,
    })
    return resp.json()["access_token"]


def _setup_family_with_child(client):
    """Create a family with one parent and one child. Returns (parent_token, child_token, child_id)."""
    parent_token = _register_and_login(client, email="parent@example.com")
    family = client.post("/api/family", headers={"Authorization": f"Bearer {parent_token}"}).json()

    child_token = _register_and_login(client, email="child@example.com", role="child")
    client.post("/api/family/join", json={"pin": family["pin"]}, headers={
        "Authorization": f"Bearer {child_token}",
    })

    members = client.get("/api/family", headers={"Authorization": f"Bearer {parent_token}"}).json()["members"]
    child_id = next(m["id"] for m in members if m["role"] == "child")
    return parent_token, child_token, child_id


def test_parent_creates_task(client):
    parent_token, child_token, child_id = _setup_family_with_child(client)

    response = client.post("/api/tasks", json={
        "name": "Do 10 pushups",
        "description": "Complete 10 pushups with proper form",
        "exbucks": 5,
        "assigned_to": child_id,
    }, headers={"Authorization": f"Bearer {parent_token}"})

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Do 10 pushups"
    assert data["description"] == "Complete 10 pushups with proper form"
    assert data["exbucks"] == 5
    assert data["assigned_to"] == child_id
    assert data["status"] == "assigned"


def test_child_sees_assigned_tasks(client):
    parent_token, child_token, child_id = _setup_family_with_child(client)

    client.post("/api/tasks", json={
        "name": "Do 10 pushups",
        "description": "Complete 10 pushups",
        "exbucks": 5,
        "assigned_to": child_id,
    }, headers={"Authorization": f"Bearer {parent_token}"})

    response = client.get("/api/tasks", headers={"Authorization": f"Bearer {child_token}"})
    assert response.status_code == 200
    tasks = response.json()
    assert len(tasks) == 1
    assert tasks[0]["name"] == "Do 10 pushups"
    assert tasks[0]["status"] == "assigned"


def test_child_completes_task(client):
    parent_token, child_token, child_id = _setup_family_with_child(client)

    task = client.post("/api/tasks", json={
        "name": "Do 10 pushups",
        "description": "Complete 10 pushups",
        "exbucks": 5,
        "assigned_to": child_id,
    }, headers={"Authorization": f"Bearer {parent_token}"}).json()

    client.patch(f"/api/tasks/{task['id']}/accept", headers={
        "Authorization": f"Bearer {child_token}",
    })

    response = client.patch(f"/api/tasks/{task['id']}/complete", headers={
        "Authorization": f"Bearer {child_token}",
    })
    assert response.status_code == 200
    assert response.json()["status"] == "completed"


def test_parent_sees_pending_approvals(client):
    parent_token, child_token, child_id = _setup_family_with_child(client)

    task = client.post("/api/tasks", json={
        "name": "Do 10 pushups",
        "description": "Complete 10 pushups",
        "exbucks": 5,
        "assigned_to": child_id,
    }, headers={"Authorization": f"Bearer {parent_token}"}).json()

    # Child accepts and completes the task
    client.patch(f"/api/tasks/{task['id']}/accept", headers={
        "Authorization": f"Bearer {child_token}",
    })
    client.patch(f"/api/tasks/{task['id']}/complete", headers={
        "Authorization": f"Bearer {child_token}",
    })

    # Parent sees all family tasks, including completed ones
    response = client.get("/api/tasks", headers={"Authorization": f"Bearer {parent_token}"})
    assert response.status_code == 200
    tasks = response.json()
    assert len(tasks) == 1
    assert tasks[0]["status"] == "completed"


def test_parent_approves_task(client):
    parent_token, child_token, child_id = _setup_family_with_child(client)

    task = client.post("/api/tasks", json={
        "name": "Do 10 pushups",
        "description": "Complete 10 pushups",
        "exbucks": 5,
        "assigned_to": child_id,
    }, headers={"Authorization": f"Bearer {parent_token}"}).json()

    client.patch(f"/api/tasks/{task['id']}/accept", headers={
        "Authorization": f"Bearer {child_token}",
    })
    client.patch(f"/api/tasks/{task['id']}/complete", headers={
        "Authorization": f"Bearer {child_token}",
    })

    response = client.patch(f"/api/tasks/{task['id']}/approve", headers={
        "Authorization": f"Bearer {parent_token}",
    })
    assert response.status_code == 200
    assert response.json()["status"] == "approved"


def test_parent_rejects_task(client):
    parent_token, child_token, child_id = _setup_family_with_child(client)

    task = client.post("/api/tasks", json={
        "name": "Do 10 pushups",
        "description": "Complete 10 pushups",
        "exbucks": 5,
        "assigned_to": child_id,
    }, headers={"Authorization": f"Bearer {parent_token}"}).json()

    client.patch(f"/api/tasks/{task['id']}/accept", headers={
        "Authorization": f"Bearer {child_token}",
    })
    client.patch(f"/api/tasks/{task['id']}/complete", headers={
        "Authorization": f"Bearer {child_token}",
    })

    response = client.patch(f"/api/tasks/{task['id']}/reject", headers={
        "Authorization": f"Bearer {parent_token}",
    })
    assert response.status_code == 200
    assert response.json()["status"] == "assigned"


def test_child_cannot_create_task(client):
    parent_token, child_token, child_id = _setup_family_with_child(client)

    response = client.post("/api/tasks", json={
        "name": "Do 10 pushups",
        "description": "Complete 10 pushups",
        "exbucks": 5,
        "assigned_to": child_id,
    }, headers={"Authorization": f"Bearer {child_token}"})
    assert response.status_code == 403


def test_child_cannot_approve_task(client):
    parent_token, child_token, child_id = _setup_family_with_child(client)

    task = client.post("/api/tasks", json={
        "name": "Do 10 pushups",
        "description": "Complete 10 pushups",
        "exbucks": 5,
        "assigned_to": child_id,
    }, headers={"Authorization": f"Bearer {parent_token}"}).json()

    client.patch(f"/api/tasks/{task['id']}/accept", headers={
        "Authorization": f"Bearer {child_token}",
    })
    client.patch(f"/api/tasks/{task['id']}/complete", headers={
        "Authorization": f"Bearer {child_token}",
    })

    response = client.patch(f"/api/tasks/{task['id']}/approve", headers={
        "Authorization": f"Bearer {child_token}",
    })
    assert response.status_code == 403


def test_child_cannot_reject_completed_task(client):
    parent_token, child_token, child_id = _setup_family_with_child(client)

    task = client.post("/api/tasks", json={
        "name": "Do 10 pushups",
        "description": "Complete 10 pushups",
        "exbucks": 5,
        "assigned_to": child_id,
    }, headers={"Authorization": f"Bearer {parent_token}"}).json()

    client.patch(f"/api/tasks/{task['id']}/accept", headers={
        "Authorization": f"Bearer {child_token}",
    })
    client.patch(f"/api/tasks/{task['id']}/complete", headers={
        "Authorization": f"Bearer {child_token}",
    })

    response = client.patch(f"/api/tasks/{task['id']}/reject", headers={
        "Authorization": f"Bearer {child_token}",
    })
    assert response.status_code == 409


def test_parent_cannot_complete_task(client):
    parent_token, child_token, child_id = _setup_family_with_child(client)

    task = client.post("/api/tasks", json={
        "name": "Do 10 pushups",
        "description": "Complete 10 pushups",
        "exbucks": 5,
        "assigned_to": child_id,
    }, headers={"Authorization": f"Bearer {parent_token}"}).json()

    response = client.patch(f"/api/tasks/{task['id']}/complete", headers={
        "Authorization": f"Bearer {parent_token}",
    })
    assert response.status_code == 403


def test_parent_creates_task_with_day_of_week(client):
    parent_token, child_token, child_id = _setup_family_with_child(client)

    response = client.post("/api/tasks", json={
        "name": "Morning run",
        "description": "Run 1km before school",
        "exbucks": 10,
        "assigned_to": child_id,
        "day_of_week": "mon",
    }, headers={"Authorization": f"Bearer {parent_token}"})

    assert response.status_code == 201
    data = response.json()
    assert data["day_of_week"] == "mon"


def test_child_sees_day_of_week_in_task_list(client):
    parent_token, child_token, child_id = _setup_family_with_child(client)

    client.post("/api/tasks", json={
        "name": "Morning run",
        "description": "Run 1km",
        "exbucks": 10,
        "assigned_to": child_id,
        "day_of_week": "wed",
    }, headers={"Authorization": f"Bearer {parent_token}"})

    client.post("/api/tasks", json={
        "name": "Pushups",
        "description": "Do 20 pushups",
        "exbucks": 5,
        "assigned_to": child_id,
    }, headers={"Authorization": f"Bearer {parent_token}"})

    response = client.get("/api/tasks", headers={"Authorization": f"Bearer {child_token}"})
    assert response.status_code == 200
    tasks = response.json()
    assert len(tasks) == 2
    days = {t["name"]: t["day_of_week"] for t in tasks}
    assert days["Morning run"] == "wed"
    assert days["Pushups"] is None


def test_parent_edits_task(client):
    parent_token, child_token, child_id = _setup_family_with_child(client)

    task = client.post("/api/tasks", json={
        "name": "Morning run",
        "description": "Run 1km",
        "exbucks": 10,
        "assigned_to": child_id,
        "day_of_week": "mon",
    }, headers={"Authorization": f"Bearer {parent_token}"}).json()

    response = client.put(f"/api/tasks/{task['id']}", json={
        "name": "Evening run",
        "description": "Run 2km after dinner",
        "exbucks": 15,
        "assigned_to": child_id,
        "day_of_week": "fri",
    }, headers={"Authorization": f"Bearer {parent_token}"})

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Evening run"
    assert data["description"] == "Run 2km after dinner"
    assert data["exbucks"] == 15
    assert data["day_of_week"] == "fri"


def test_parent_cannot_edit_completed_task(client):
    parent_token, child_token, child_id = _setup_family_with_child(client)

    task = client.post("/api/tasks", json={
        "name": "Morning run",
        "description": "Run 1km",
        "exbucks": 10,
        "assigned_to": child_id,
    }, headers={"Authorization": f"Bearer {parent_token}"}).json()

    # Child accepts then completes the task
    client.patch(f"/api/tasks/{task['id']}/accept", headers={
        "Authorization": f"Bearer {child_token}",
    })
    client.patch(f"/api/tasks/{task['id']}/complete", headers={
        "Authorization": f"Bearer {child_token}",
    })

    response = client.put(f"/api/tasks/{task['id']}", json={
        "name": "Changed name",
        "description": "Changed",
        "exbucks": 1,
        "assigned_to": child_id,
    }, headers={"Authorization": f"Bearer {parent_token}"})

    assert response.status_code == 409


def test_parent_deletes_task(client):
    parent_token, child_token, child_id = _setup_family_with_child(client)

    task = client.post("/api/tasks", json={
        "name": "Morning run",
        "description": "Run 1km",
        "exbucks": 10,
        "assigned_to": child_id,
    }, headers={"Authorization": f"Bearer {parent_token}"}).json()

    response = client.delete(f"/api/tasks/{task['id']}", headers={
        "Authorization": f"Bearer {parent_token}",
    })
    assert response.status_code == 204

    # Task no longer appears in the list
    tasks = client.get("/api/tasks", headers={"Authorization": f"Bearer {parent_token}"}).json()
    assert len(tasks) == 0


def test_child_cannot_edit_task(client):
    parent_token, child_token, child_id = _setup_family_with_child(client)

    task = client.post("/api/tasks", json={
        "name": "Morning run",
        "description": "Run 1km",
        "exbucks": 10,
        "assigned_to": child_id,
    }, headers={"Authorization": f"Bearer {parent_token}"}).json()

    response = client.put(f"/api/tasks/{task['id']}", json={
        "name": "Nap time",
        "description": "Sleep all day",
        "exbucks": 100,
        "assigned_to": child_id,
    }, headers={"Authorization": f"Bearer {child_token}"})
    assert response.status_code == 403


def test_child_cannot_delete_task(client):
    parent_token, child_token, child_id = _setup_family_with_child(client)

    task = client.post("/api/tasks", json={
        "name": "Morning run",
        "description": "Run 1km",
        "exbucks": 10,
        "assigned_to": child_id,
    }, headers={"Authorization": f"Bearer {parent_token}"}).json()

    response = client.delete(f"/api/tasks/{task['id']}", headers={
        "Authorization": f"Bearer {child_token}",
    })
    assert response.status_code == 403


def test_child_accepts_assigned_task(client):
    parent_token, child_token, child_id = _setup_family_with_child(client)

    task = client.post("/api/tasks", json={
        "name": "Morning run",
        "description": "Run 1km",
        "exbucks": 10,
        "assigned_to": child_id,
    }, headers={"Authorization": f"Bearer {parent_token}"}).json()

    response = client.patch(f"/api/tasks/{task['id']}/accept", headers={
        "Authorization": f"Bearer {child_token}",
    })
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"


def test_child_rejects_assigned_task(client):
    parent_token, child_token, child_id = _setup_family_with_child(client)

    task = client.post("/api/tasks", json={
        "name": "Morning run",
        "description": "Run 1km",
        "exbucks": 10,
        "assigned_to": child_id,
    }, headers={"Authorization": f"Bearer {parent_token}"}).json()

    response = client.patch(f"/api/tasks/{task['id']}/reject", headers={
        "Authorization": f"Bearer {child_token}",
    })
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


def test_full_task_lifecycle_accept_complete_approve(client):
    parent_token, child_token, child_id = _setup_family_with_child(client)

    task = client.post("/api/tasks", json={
        "name": "Do 10 pushups",
        "description": "Complete 10 pushups",
        "exbucks": 5,
        "assigned_to": child_id,
        "day_of_week": "tue",
    }, headers={"Authorization": f"Bearer {parent_token}"}).json()
    assert task["status"] == "assigned"

    # Child accepts
    resp = client.patch(f"/api/tasks/{task['id']}/accept", headers={
        "Authorization": f"Bearer {child_token}",
    })
    assert resp.json()["status"] == "accepted"

    # Child completes
    resp = client.patch(f"/api/tasks/{task['id']}/complete", headers={
        "Authorization": f"Bearer {child_token}",
    })
    assert resp.json()["status"] == "completed"

    # Parent approves
    resp = client.patch(f"/api/tasks/{task['id']}/approve", headers={
        "Authorization": f"Bearer {parent_token}",
    })
    assert resp.json()["status"] == "approved"

    # Child earned ExBucks
    balance = client.get("/api/exbucks/balance", headers={
        "Authorization": f"Bearer {child_token}",
    }).json()
    assert balance["balance"] == 5


def test_task_list_includes_avatar_fields(client):
    parent_token, child_token, child_id = _setup_family_with_child(client)

    # Seed avatars so child gets defaults on join
    from exsize.database import get_db
    db = next(client.app.dependency_overrides[get_db]())
    from exsize.app import _seed_avatar_items
    _seed_avatar_items(db)

    # Re-join to trigger avatar assignment (child already joined, so assign manually)
    from exsize.models import AvatarItem, User, UserInventory
    free_icon = db.query(AvatarItem).filter(AvatarItem.type == "icon", AvatarItem.price == 0, AvatarItem.is_default == True).first()
    free_bg = db.query(AvatarItem).filter(AvatarItem.type == "background", AvatarItem.price == 0, AvatarItem.is_default == True).first()
    child = db.query(User).filter(User.id == child_id).first()
    if not db.query(UserInventory).filter(UserInventory.user_id == child_id).first():
        db.add(UserInventory(user_id=child_id, avatar_item_id=free_icon.id))
        db.add(UserInventory(user_id=child_id, avatar_item_id=free_bg.id))
    child.equipped_icon_id = free_icon.id
    child.equipped_background_id = free_bg.id
    db.commit()

    client.post("/api/tasks", json={
        "name": "Do 10 pushups",
        "description": "Complete 10 pushups",
        "exbucks": 5,
        "assigned_to": child_id,
    }, headers={"Authorization": f"Bearer {parent_token}"})

    response = client.get("/api/tasks", headers={"Authorization": f"Bearer {child_token}"})
    assert response.status_code == 200
    tasks = response.json()
    assert len(tasks) == 1
    assert tasks[0]["avatar_icon"] == "👤"
    assert tasks[0]["avatar_background"] == "#F48FB1"


def test_cannot_act_on_task_outside_family(client):
    # Family 1
    parent1_token, child1_token, child1_id = _setup_family_with_child(client)

    task = client.post("/api/tasks", json={
        "name": "Do 10 pushups",
        "description": "Complete 10 pushups",
        "exbucks": 5,
        "assigned_to": child1_id,
    }, headers={"Authorization": f"Bearer {parent1_token}"}).json()

    # Family 2
    parent2_token = _register_and_login(client, email="parent2@example.com")
    client.post("/api/family", headers={"Authorization": f"Bearer {parent2_token}"})

    # Parent from family 2 cannot approve family 1's task
    response = client.patch(f"/api/tasks/{task['id']}/approve", headers={
        "Authorization": f"Bearer {parent2_token}",
    })
    assert response.status_code == 404


# --- Due date (issue #68: schema prep) ---


def test_task_created_with_due_date_returns_it(client):
    parent_token, child_token, child_id = _setup_family_with_child(client)

    response = client.post("/api/tasks", json={
        "name": "Wynieś śmieci",
        "description": "Wieczorem",
        "exbucks": 5,
        "assigned_to": child_id,
        "due_date": "2026-09-01",
    }, headers={"Authorization": f"Bearer {parent_token}"})

    assert response.status_code == 201
    assert response.json()["due_date"] == "2026-09-01"

    listing = client.get("/api/tasks", headers={"Authorization": f"Bearer {child_token}"}).json()
    assert listing[0]["due_date"] == "2026-09-01"


def test_task_created_without_due_date_keeps_it_empty(client):
    parent_token, child_token, child_id = _setup_family_with_child(client)

    task = client.post("/api/tasks", json={
        "name": "Do 10 pushups", "description": "", "exbucks": 5, "assigned_to": child_id,
    }, headers={"Authorization": f"Bearer {parent_token}"}).json()

    assert task["due_date"] is None


def test_task_due_date_can_be_changed_by_edit(client):
    parent_token, child_token, child_id = _setup_family_with_child(client)

    task = client.post("/api/tasks", json={
        "name": "Wynieś śmieci", "description": "", "exbucks": 5, "assigned_to": child_id,
        "due_date": "2026-09-01",
    }, headers={"Authorization": f"Bearer {parent_token}"}).json()

    edited = client.put(f"/api/tasks/{task['id']}", json={
        "name": "Wynieś śmieci", "description": "", "exbucks": 5, "assigned_to": child_id,
        "due_date": "2026-09-08",
    }, headers={"Authorization": f"Bearer {parent_token}"})

    assert edited.status_code == 200
    assert edited.json()["due_date"] == "2026-09-08"
