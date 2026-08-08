from datetime import datetime

from exsize.models import PushSubscription, TodoItem, TodoList
from exsize.services.reminder import ReminderService


# --- helpers ---------------------------------------------------------------


def _noop_send(*args, **kwargs):
    return None


def _make_list(db, user_id, name="Lista"):
    tl = TodoList(name=name, user_id=user_id)
    db.add(tl)
    db.commit()
    db.refresh(tl)
    return tl


def _add_item(db, list_id, title, due_at=None, recurrence=None, completed=False):
    item = TodoItem(
        title=title,
        list_id=list_id,
        due_at=due_at,
        recurrence=recurrence,
        completed=completed,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def _make_sub(db, user_id, endpoint):
    sub = PushSubscription(user_id=user_id, endpoint=endpoint, p256dh="p256dh", auth="auth")
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


def _service(db, *, now, send_push=_noop_send):
    return ReminderService(db, now=now, send_push=send_push)


def _recording_send():
    """A send_push spy that records every (subscription, payload) call."""
    calls = []

    def send_push(subscription, payload):
        calls.append((subscription, payload))

    return send_push, calls


# --- Plaster 1: scheduler selects exactly due items (acceptance #4) --------


def test_due_items_returns_uncompleted_items_at_or_before_now(db):
    now = datetime(2026, 8, 8, 12, 0)
    todo_list = _make_list(db, user_id=1)

    past = _add_item(db, todo_list.id, "w przeszlosci", due_at=datetime(2026, 8, 8, 10, 0))
    exact = _add_item(db, todo_list.id, "dokladnie teraz", due_at=now)
    _add_item(db, todo_list.id, "w przyszlosci", due_at=datetime(2026, 8, 8, 18, 0))
    _add_item(db, todo_list.id, "bez terminu")
    _add_item(
        db, todo_list.id, "ukonczone", due_at=datetime(2026, 8, 8, 9, 0), completed=True
    )

    result = _service(db, now=now).due_items()

    assert {item.id for item in result} == {past.id, exact.id}


def test_due_items_orders_by_due_at_ascending(db):
    now = datetime(2026, 8, 8, 12, 0)
    todo_list = _make_list(db, user_id=1)
    later = _add_item(db, todo_list.id, "pozniej", due_at=datetime(2026, 8, 8, 11, 0))
    earlier = _add_item(db, todo_list.id, "wczesniej", due_at=datetime(2026, 8, 8, 9, 0))

    result = _service(db, now=now).due_items()

    assert [item.id for item in result] == [earlier.id, later.id]


# --- Plaster 2: due item + subscription -> send_push called (acceptance #1) -


def test_run_sends_push_for_due_item_when_user_subscribed(db):
    now = datetime(2026, 8, 8, 12, 0)
    todo_list = _make_list(db, user_id=1)
    _add_item(db, todo_list.id, "Mleko", due_at=datetime(2026, 8, 8, 10, 0))
    sub = _make_sub(db, user_id=1, endpoint="https://push.example/abc")

    send_push, calls = _recording_send()
    _service(db, now=now, send_push=send_push).run()

    assert len(calls) == 1
    sent_sub, payload = calls[0]
    assert sent_sub.id == sub.id
    assert payload["title"]  # niepusty
    assert "Mleko" in payload["titles"]


# --- Plaster 3: owner without subscription -> graceful (acceptance #2) ------


def test_run_skips_due_item_when_user_has_no_subscription(db):
    now = datetime(2026, 8, 8, 12, 0)
    todo_list = _make_list(db, user_id=1)
    _add_item(db, todo_list.id, "Mleko", due_at=datetime(2026, 8, 8, 10, 0))
    # brak subskrypcji dla user_id=1

    send_push, calls = _recording_send()
    result = _service(db, now=now, send_push=send_push).run()

    assert calls == []
    assert result["sent"] == 0


# --- Plaster 4: expired subscription -> removed, no crash (acceptance #2) ---


def test_run_removes_subscription_when_send_push_raises_gone(db):
    now = datetime(2026, 8, 8, 12, 0)
    todo_list = _make_list(db, user_id=1)
    _add_item(db, todo_list.id, "Mleko", due_at=datetime(2026, 8, 8, 10, 0))
    sub = _make_sub(db, user_id=1, endpoint="https://push.example/gone")
    from exsize.services.reminder import SubscriptionGone

    def send_push(subscription, payload):
        raise SubscriptionGone("410 Gone")

    result = _service(db, now=now, send_push=send_push).run()

    db.flush()
    leftover = db.query(PushSubscription).filter(PushSubscription.id == sub.id).count()
    assert leftover == 0  # wygasła subskrypcja usunięta
    assert result["removed"] == 1


# --- Plaster 5: transient failure -> keep sub, continue (acceptance #2) ----


def test_run_keeps_subscription_and_continues_on_transient_failure(db):
    now = datetime(2026, 8, 8, 12, 0)
    todo_list = _make_list(db, user_id=1)
    _add_item(db, todo_list.id, "Mleko", due_at=datetime(2026, 8, 8, 10, 0))
    flaky = _make_sub(db, user_id=1, endpoint="https://push.example/flaky")
    ok_sub = _make_sub(db, user_id=1, endpoint="https://push.example/ok")
    from exsize.services.reminder import PushDeliveryFailed

    sent_endpoints = []

    def send_push(subscription, payload):
        if subscription.endpoint == flaky.endpoint:
            raise PushDeliveryFailed("500 timeout")
        sent_endpoints.append(subscription.endpoint)

    result = _service(db, now=now, send_push=send_push).run()

    # kolejna subskrypcja dostala push mimo bledu poprzedniej
    assert sent_endpoints == [ok_sub.endpoint]
    # obie subskrypcje zostaly w bazie (bledy przejsciowy nie usuwa)
    db.flush()
    assert db.query(PushSubscription).count() == 2
    assert result["removed"] == 0
    assert result["sent"] == 1


# --- Plaster 6: digest — one push per subscription, all titles (acceptance #1)


def test_run_sends_one_digest_per_subscription_with_all_due_titles(db):
    now = datetime(2026, 8, 8, 12, 0)
    todo_list = _make_list(db, user_id=1)
    _add_item(db, todo_list.id, "Mleko", due_at=datetime(2026, 8, 8, 9, 0))
    _add_item(db, todo_list.id, "Chleb", due_at=datetime(2026, 8, 8, 10, 0))
    _make_sub(db, user_id=1, endpoint="https://push.example/a")
    _make_sub(db, user_id=1, endpoint="https://push.example/b")

    send_push, calls = _recording_send()
    result = _service(db, now=now, send_push=send_push).run()

    assert len(calls) == 2  # po jednym digeście na subskrypcję
    for _, payload in calls:
        assert payload["count"] == 2
        assert set(payload["titles"]) == {"Mleko", "Chleb"}
    assert result["sent"] == 2


# --- Plaster 7: recurring due item advanced after notify (acceptance #3) ---


def test_run_advances_recurring_due_item_after_notifying(db):
    now = datetime(2026, 8, 8, 12, 0)
    todo_list = _make_list(db, user_id=1)
    item = _add_item(
        db, todo_list.id, "Lekarstwa", due_at=datetime(2026, 8, 8, 9, 0), recurrence="daily"
    )
    _make_sub(db, user_id=1, endpoint="https://push.example/a")

    send_push, calls = _recording_send()
    _service(db, now=now, send_push=send_push).run()

    # przypomniano w tym przebiegu
    assert len(calls) == 1
    assert "Lekarstwa" in calls[0][1]["titles"]
    # stare wystąpienie ukończone (już nie przypomni)
    db.refresh(item)
    assert item.completed is True
    # nowe wystąpienie na jutro, otwarte — przypomni następnym razem
    fresh = (
        db.query(TodoItem)
        .filter(TodoItem.list_id == todo_list.id, TodoItem.completed.is_(False))
        .all()
    )
    assert len(fresh) == 1
    assert fresh[0].title == "Lekarstwa"
    assert fresh[0].due_at == datetime(2026, 8, 9, 9, 0)
    assert fresh[0].recurrence == "daily"
