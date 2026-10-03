"""Windows-account-protected persistent conversation memory."""
import ctypes
import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from ctypes import wintypes
from pathlib import Path


class _DataBlob(ctypes.Structure):
    _fields_ = (
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    )


def _crypt(data: bytes, protect: bool) -> bytes:
    if os.name != "nt":
        raise RuntimeError("Persistent conversation memory requires Windows account protection.")
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    source_buffer = ctypes.create_string_buffer(data)
    source = _DataBlob(
        len(data),
        ctypes.cast(source_buffer, ctypes.POINTER(ctypes.c_ubyte)),
    )
    destination = _DataBlob()
    function = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    function.argtypes = [
        ctypes.POINTER(_DataBlob),
        wintypes.LPCWSTR if protect else ctypes.POINTER(wintypes.LPWSTR),
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    function.restype = wintypes.BOOL
    ok = function(
        ctypes.byref(source),
        "JARVIS conversation memory" if protect else None,
        None,
        None,
        None,
        0x1,
        ctypes.byref(destination),
    )
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(destination.pbData, destination.cbData)
    finally:
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree.restype = ctypes.c_void_p
        kernel32.LocalFree(destination.pbData)


class ConversationMemory:
    """Stores encrypted turn records; only the current Windows user can decrypt them."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=DELETE")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS turns ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, payload BLOB NOT NULL)"
            )

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.execute("PRAGMA secure_delete=ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def add_turn(self, user: str, assistant: str) -> None:
        payload = json.dumps(
            {"user": user, "assistant": assistant},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        encrypted = _crypt(payload, protect=True)
        with self._lock, self._connect() as connection:
            connection.execute("INSERT INTO turns(payload) VALUES (?)", (encrypted,))

    def recent_turns(self, limit: int = 20) -> list[tuple[str, str]]:
        if limit < 1:
            return []
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM turns ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        turns = []
        for (payload,) in reversed(rows):
            turn = json.loads(_crypt(payload, protect=False).decode("utf-8"))
            turns.append((turn["user"], turn["assistant"]))
        return turns

    def count(self) -> int:
        with self._lock, self._connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM turns").fetchone()[0])

    def clear(self) -> None:
        with self._lock:
            with self._connect() as connection:
                connection.execute("DELETE FROM turns")
            with self._connect() as connection:
                connection.execute("VACUUM")
