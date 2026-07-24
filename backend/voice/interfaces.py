from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from backend.voice.schemas import TranscriptionResponse


class BaseTranscriber(ABC):
    @abstractmethod
    async def transcribe_audio(self, audio_bytes: bytes, *, language: str | None = None, **kwargs: Any) -> TranscriptionResponse:
        """Transcribe raw audio bytes."""

    @abstractmethod
    async def transcribe_file(self, audio_path: str, *, language: str | None = None, **kwargs: Any) -> TranscriptionResponse:
        """Transcribe an audio file."""

    @abstractmethod
    async def transcribe_stream(self, audio_stream: Any, *, language: str | None = None, **kwargs: Any) -> TranscriptionResponse:
        """Transcribe a stream of audio data."""
