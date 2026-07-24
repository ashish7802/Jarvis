from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


class VoiceCache:
    """A lightweight in-memory cache for synthesized speech."""

    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}

    def _key(self, text: str, *, voice: str | None = None, rate: str | None = None, volume: str | None = None, pitch: str | None = None, file_format: str = "wav") -> str:
        payload = "|".join([text, voice or "", rate or "", volume or "", pitch or "", file_format])
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def get(self, text: str, *, voice: str | None = None, rate: str | None = None, volume: str | None = None, pitch: str | None = None, file_format: str = "wav") -> bytes | None:
        return self._store.get(self._key(text, voice=voice, rate=rate, volume=volume, pitch=pitch, file_format=file_format))

    def set(self, text: str, audio_bytes: bytes, *, voice: str | None = None, rate: str | None = None, volume: str | None = None, pitch: str | None = None, file_format: str = "wav") -> None:
        self._store[self._key(text, voice=voice, rate=rate, volume=volume, pitch=pitch, file_format=file_format)] = audio_bytes

    def clear(self) -> None:
        self._store.clear()
