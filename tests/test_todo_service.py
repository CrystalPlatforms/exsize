import pytest

from exsize.models import TodoList
from exsize.services.todo import TodoService, TodoNotFound


def _service(db, user_id=1):
    return TodoService(db, user_id)


# --- Lists: create ---


def test_create_list_returns_owned_list(db):
    service = _service(db, user_id=1)

    todo_list = service.create_list("Zakupy")

    assert todo_list.id is not None
    assert todo_list.name == "Zakupy"
    assert todo_list.user_id == 1


def test_create_list_persists_to_database(db):
    service = _service(db, user_id=1)

    service.create_list("Zakupy")
    db.flush()

    stored = db.query(TodoList).one()
    assert stored.name == "Zakupy"
    assert stored.user_id == 1


# --- Lists: list ---


def test_list_lists_returns_only_owners_lists(db):
    other = _service(db, user_id=2)
    other.create_list("Cudze zakupy")
    other.create_list("Cudza praca")

    service = _service(db, user_id=1)
    service.create_list("Zakupy")

    lists = service.list_lists()

    assert len(lists) == 1
    assert lists[0].name == "Zakupy"
    assert all(tl.user_id == 1 for tl in lists)


# --- Items: add + list ---


def test_add_item_creates_uncompleted_item_in_list(db):
    service = _service(db, user_id=1)
    todo_list = service.create_list("Zakupy")

    item = service.add_item(todo_list.id, "Mleko")

    assert item.id is not None
    assert item.title == "Mleko"
    assert item.list_id == todo_list.id
    assert item.completed is False


def test_list_items_returns_items_of_a_list(db):
    service = _service(db, user_id=1)
    todo_list = service.create_list("Zakupy")
    service.add_item(todo_list.id, "Mleko")
    service.add_item(todo_list.id, "Chleb")

    items = service.list_items(todo_list.id)

    assert [i.title for i in items] == ["Mleko", "Chleb"]


def test_add_item_to_other_users_list_raises(db):
    other = _service(db, user_id=2)
    foreign_list = other.create_list("Cudze")

    service = _service(db, user_id=1)

    with pytest.raises(TodoNotFound):
        service.add_item(foreign_list.id, "Włamywacz")


# --- Items: complete (toggle) ---


def test_complete_item_marks_done(db):
    service = _service(db, user_id=1)
    todo_list = service.create_list("Zakupy")
    item = service.add_item(todo_list.id, "Mleko")

    completed = service.complete_item(item.id)

    assert completed.completed is True


def test_complete_item_toggles_back_to_uncompleted(db):
    service = _service(db, user_id=1)
    todo_list = service.create_list("Zakupy")
    item = service.add_item(todo_list.id, "Mleko")

    service.complete_item(item.id)
    toggled = service.complete_item(item.id)

    assert toggled.completed is False


def test_complete_other_users_item_raises(db):
    other = _service(db, user_id=2)
    other_list = other.create_list("Cudze")
    foreign_item = other.add_item(other_list.id, "Nie moje")

    service = _service(db, user_id=1)

    with pytest.raises(TodoNotFound):
        service.complete_item(foreign_item.id)


# --- Items: edit + delete ---


def test_edit_item_changes_title(db):
    service = _service(db, user_id=1)
    todo_list = service.create_list("Zakupy")
    item = service.add_item(todo_list.id, "Mleko")

    edited = service.edit_item(item.id, "Mleko 2%")

    assert edited.title == "Mleko 2%"
    assert edited.id == item.id


def test_edit_other_users_item_raises(db):
    other = _service(db, user_id=2)
    other_list = other.create_list("Cudze")
    foreign_item = other.add_item(other_list.id, "Nie moje")

    service = _service(db, user_id=1)
    with pytest.raises(TodoNotFound):
        service.edit_item(foreign_item.id, "Hack")


def test_delete_item_removes_it(db):
    service = _service(db, user_id=1)
    todo_list = service.create_list("Zakupy")
    item = service.add_item(todo_list.id, "Mleko")

    service.delete_item(item.id)

    assert service.list_items(todo_list.id) == []


def test_delete_other_users_item_raises(db):
    other = _service(db, user_id=2)
    other_list = other.create_list("Cudze")
    foreign_item = other.add_item(other_list.id, "Nie moje")

    service = _service(db, user_id=1)
    with pytest.raises(TodoNotFound):
        service.delete_item(foreign_item.id)


# --- Lists: rename + delete ---


def test_rename_list_changes_name(db):
    service = _service(db, user_id=1)
    todo_list = service.create_list("Zakupy")

    renamed = service.rename_list(todo_list.id, "Codzienne zakupy")

    assert renamed.name == "Codzienne zakupy"
    assert renamed.id == todo_list.id


def test_rename_other_users_list_raises(db):
    other = _service(db, user_id=2)
    foreign_list = other.create_list("Cudze")

    service = _service(db, user_id=1)
    with pytest.raises(TodoNotFound):
        service.rename_list(foreign_list.id, "Hack")


def test_delete_list_removes_it_and_its_items(db):
    service = _service(db, user_id=1)
    todo_list = service.create_list("Zakupy")
    service.add_item(todo_list.id, "Mleko")
    service.add_item(todo_list.id, "Chleb")

    service.delete_list(todo_list.id)

    assert service.list_lists() == []
    leftover = db.query(TodoList).filter(TodoList.id == todo_list.id).count()
    assert leftover == 0


def test_delete_other_users_list_raises(db):
    other = _service(db, user_id=2)
    foreign_list = other.create_list("Cudze")

    service = _service(db, user_id=1)
    with pytest.raises(TodoNotFound):
        service.delete_list(foreign_list.id)





