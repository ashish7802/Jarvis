from datetime import datetime, timezone

from app.assistant.commands import parse_productivity_request
from app.assistant.productivity import ProductivityStore


def test_parser_recognizes_timer_and_reminder():
    now = datetime(2026, 9, 26, 10, 0, tzinfo=timezone.utc)
    timer = parse_productivity_request("set a timer for 5 minutes to stretch", now)
    assert timer.action == "set_timer"
    assert timer.text == "stretch"
    assert (timer.due_at - now).total_seconds() == 300

    reminder = parse_productivity_request("remind me tomorrow at 9 am to call mom", now)
    assert reminder.action == "set_reminder"
    assert reminder.due_at.hour == 9
    assert reminder.due_at.day == 27


def test_notes_and_reminders_persist_and_due_items_deliver_once(tmp_path):
    current = [datetime(2026, 9, 26, 10, 0, tzinfo=timezone.utc)]
    store = ProductivityStore(tmp_path, clock=lambda: current[0])
    reminder = store.add_reminder("check the oven", current[0])
    note = store.add_note("buy oat milk")
    assert store.find_note(note.title).body == "buy oat milk"
    assert store.due_reminders()[0].id == reminder.id
    assert store.due_reminders() == []

    reloaded = ProductivityStore(tmp_path, clock=lambda: current[0])
    assert reloaded.notes()[0].body == "buy oat milk"
    assert reloaded.reminders() == []


def test_store_handles_voice_friendly_actions(tmp_path):
    store = ProductivityStore(tmp_path)
    request = parse_productivity_request("take a note: ship the Jarvis update")
    assert "Saved a note" in store.handle(request)
    assert "ship the Jarvis update" in store.handle(parse_productivity_request("read my note ship"))
    assert "notes are" in store.handle(parse_productivity_request("show notes")).lower()