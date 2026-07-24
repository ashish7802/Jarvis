from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


from collections import OrderedDict


class VoiceCache:
    """A lightweight in-memory LRU cache for synthesized speech."""

    def __init__(self, max_size: int = 100) -> None:
        self.max_size = max_size
        self._store: OrderedDict[str, bytes] = OrderedDict()

    def _key(self, text: str, *, voice: str | None = None, rate: str | None = None, volume: str | None = None, pitch: str | None = None, file_format: str = "wav") -> str:
        payload = "|".join([text, voice or "", rate or "", volume or "", pitch or "", file_format])
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def get(self, text: str, *, voice: str | None = None, rate: str | None = None, volume: str | None = None, pitch: str | None = None, file_format: str = "wav") -> bytes | None:
        key = self._key(text, voice=voice, rate=rate, volume=volume, pitch=pitch, file_format=file_format)
        if key in self._store:
            self._store.move_to_end(key)
            return self._store[key]
        return None

    def set(self, text: str, audio_bytes: bytes, *, voice: str | None = None, rate: str | None = None, volume: str | None = None, pitch: str | None = None, file_format: str = "wav") -> None:
        key = self._key(text, voice=voice, rate=rate, volume=volume, pitch=pitch, file_format=file_format)
        self._store[key] = audio_bytes
        self._store.move_to_end(key)
        if len(self._store) > self.max_size:
            self._store.popitem(last=False)

    def clear(self) -> None:
        self._store.clear()
