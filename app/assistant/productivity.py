"""Persistent, local productivity skills for JARVIS.

This module intentionally uses only the Python standard library. Timers,
reminders and notes are user data, so they stay on the local machine and are
never sent to an AI provider.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import json
from pathlib import Path
import tempfile
import threading
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class Reminder:
    id: str
    text: str
    due_at: datetime
    kind: str
    delivered: bool = False


@dataclass(frozen=True)
class Note:
    id: str
    title: str
    body: str
    created_at: datetime
    updated_at: datetime


def _now() -> datetime:
    return datetime.now().astimezone()


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.astimezone()


def _format_due(value: datetime, now: datetime | None = None) -> str:
    current = now or _now()
    local = value.astimezone()
    if local.date() == current.astimezone().date():
        return f"today at {local.strftime('%I:%M %p').lstrip('0')}"
    if (local.date() - current.astimezone().date()).days == 1:
        return f"tomorrow at {local.strftime('%I:%M %p').lstrip('0')}"
    return local.strftime("%A at %I:%M %p").lstrip("0")


class ProductivityStore:
    """Thread-safe local storage and scheduler for reminders and notes."""

    def __init__(self, data_dir: str | Path, *, clock=_now) -> None:
        self.data_dir = Path(data_dir)
        self.path = self.data_dir / "productivity.json"
        self.clock = clock
        self._lock = threading.RLock()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, list[dict[str, Any]]] = self._load()

    def _load(self) -> dict[str, list[dict[str, Any]]]:
        if not self.path.exists():
            return {"reminders": [], "notes": []}
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Unable to read JARVIS productivity data: {self.path}") from exc
        if not isinstance(value, dict) or not isinstance(value.get("reminders", []), list) or not isinstance(value.get("notes", []), list):
            raise ValueError(f"Invalid JARVIS productivity data: {self.path}")
        return {"reminders": value.get("reminders", []), "notes": value.get("notes", [])}

    def _save(self) -> None:
        payload = json.dumps(self._data, ensure_ascii=False, indent=2)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.data_dir, delete=False) as temp:
            temp.write(payload)
            temporary = Path(temp.name)
        temporary.replace(self.path)

    def add_reminder(self, text: str, due_at: datetime, *, kind: str = "reminder") -> Reminder:
        text = " ".join(text.split()).strip()
        if not text:
            raise ValueError("Reminder text cannot be empty.")
        if due_at.tzinfo is None:
            due_at = due_at.astimezone()
        reminder = {
            "id": f"r-{uuid4().hex[:8]}",
            "text": text[:500],
            "due_at": due_at.isoformat(),
            "kind": kind,
            "delivered": False,
        }
        with self._lock:
            self._data["reminders"].append(reminder)
            self._save()
        return self._reminder(reminder)

    def _reminder(self, value: dict[str, Any]) -> Reminder:
        return Reminder(
            id=str(value["id"]),
            text=str(value["text"]),
            due_at=_parse_datetime(str(value["due_at"])),
            kind=str(value.get("kind", "reminder")),
            delivered=bool(value.get("delivered", False)),
        )

    def reminders(self, *, include_delivered: bool = False) -> list[Reminder]:
        with self._lock:
            items = [self._reminder(item) for item in self._data["reminders"]]
        items.sort(key=lambda item: item.due_at)
        return [item for item in items if include_delivered or not item.delivered]

    def due_reminders(self) -> list[Reminder]:
        now = self.clock()
        due: list[Reminder] = []
        with self._lock:
            for item in self._data["reminders"]:
                if not item.get("delivered") and _parse_datetime(str(item["due_at"])) <= now:
                    item["delivered"] = True
                    due.append(self._reminder(item))
            if due:
                self._save()
        return due

    def cancel_reminder(self, query: str) -> Reminder | None:
        normalized = query.strip().casefold()
        with self._lock:
            for index, value in enumerate(self._data["reminders"]):
                reminder = self._reminder(value)
                if reminder.delivered:
                    continue
                if reminder.id.casefold() == normalized or reminder.text.casefold() == normalized:
                    self._data["reminders"].pop(index)
                    self._save()
                    return reminder
        return None

    def add_note(self, body: str, title: str = "") -> Note:
        body = " ".join(body.split()).strip()
        if not body:
            raise ValueError("Note cannot be empty.")
        title = " ".join(title.split()).strip()[:120] or body[:60]
        stamp = self.clock()
        value = {
            "id": f"n-{uuid4().hex[:8]}",
            "title": title,
            "body": body[:4000],
            "created_at": stamp.isoformat(),
            "updated_at": stamp.isoformat(),
        }
        with self._lock:
            self._data["notes"].append(value)
            self._save()
        return self._note(value)

    def _note(self, value: dict[str, Any]) -> Note:
        return Note(
            id=str(value["id"]),
            title=str(value["title"]),
            body=str(value["body"]),
            created_at=_parse_datetime(str(value["created_at"])),
            updated_at=_parse_datetime(str(value["updated_at"])),
        )

    def notes(self) -> list[Note]:
        with self._lock:
            items = [self._note(item) for item in self._data["notes"]]
        return sorted(items, key=lambda item: item.updated_at, reverse=True)

    def find_note(self, query: str) -> Note | None:
        normalized = query.strip().casefold()
        if not normalized:
            return None
        for note in self.notes():
            if note.id.casefold() == normalized or normalized in note.title.casefold():
                return note
        return None

    def delete_note(self, query: str) -> Note | None:
        note = self.find_note(query)
        if note is None:
            return None
        with self._lock:
            self._data["notes"] = [item for item in self._data["notes"] if item["id"] != note.id]
            self._save()
        return note

    def handle(self, request, *, now: datetime | None = None) -> str:
        """Execute a parsed ProductivityRequest and return a speakable reply."""
        current = now or self.clock()
        if request.action in {"set_timer", "set_reminder"}:
            reminder = self.add_reminder(request.text, request.due_at, kind=request.action.removeprefix("set_"))
            prefix = "Timer set" if request.action == "set_timer" else "Reminder set"
            extra = f" to {reminder.text}" if request.text else ""
            return f"{prefix} for {_format_due(reminder.due_at, current)}{extra}. I'll let you know."
        if request.action == "list_reminders":
            items = self.reminders()
            if not items:
                return "You have no pending reminders."
            preview = "; ".join(f"{item.id}: {item.text}, {_format_due(item.due_at, current)}" for item in items[:5])
            more = f" Plus {len(items) - 5} more." if len(items) > 5 else ""
            return f"Your pending reminders are: {preview}.{more}"
        if request.action == "cancel_reminder":
            reminder = self.cancel_reminder(request.query)
            return f"Cancelled the reminder: {reminder.text}." if reminder else "I couldn't find that pending reminder."
        if request.action == "add_note":
            note = self.add_note(request.text, request.title)
            return f"Saved a note called {note.title}."
        if request.action == "list_notes":
            items = self.notes()
            if not items:
                return "You don't have any saved notes."
            preview = "; ".join(f"{item.id}: {item.title}" for item in items[:8])
            more = f" Plus {len(items) - 8} more." if len(items) > 8 else ""
            return f"Your notes are: {preview}.{more}"
        if request.action == "read_note":
            note = self.find_note(request.query)
            return f"{note.title}: {note.body}" if note else "I couldn't find a note with that title."
        if request.action == "delete_note":
            note = self.delete_note(request.query)
            return f"Deleted the note called {note.title}." if note else "I couldn't find a note with that title."
        raise ValueError(f"Unknown productivity action: {request.action}")


def duration_from_request(value: str, now: datetime | None = None) -> datetime | None:
    """Convert a short duration such as ``10 minutes`` into a due timestamp."""
    import re

    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(second|seconds|sec|secs|minute|minutes|min|mins|hour|hours|hr|hrs|day|days)\s*", value, re.IGNORECASE)
    if not match:
        return None
    amount = float(match.group(1))
    unit = match.group(2).casefold()
    if unit.startswith("second"):
        delta = timedelta(seconds=amount)
    elif unit.startswith("min"):
        delta = timedelta(minutes=amount)
    elif unit.startswith("hour") or unit.startswith("hr"):
        delta = timedelta(hours=amount)
    else:
        delta = timedelta(days=amount)
    return (now or _now()) + delta