from __future__ import annotations

import asyncio
import os
import time
from typing import Any

from loguru import logger

from backend.config.settings import get_settings
from backend.voice.audio_utils import ensure_wav_bytes, read_audio_file
from backend.voice.exceptions import ModelLoadError, TranscriptionError
from backend.voice.interfaces import BaseTranscriber
from backend.voice.schemas import TranscriptionResponse

try:
    from faster_whisper import WhisperModel
except Exception:  # pragma: no cover - optional dependency
    WhisperModel = None

try:
    import numpy as np
except Exception:  # pragma: no cover - optional dependency
    np = None

_WHISPER_MODEL_CLASS = WhisperModel


class FasterWhisperTranscriber(BaseTranscriber):
    """Production-ready Faster-Whisper transcription wrapper."""

    def __init__(self, *, model_name: str | None = None, device: str | None = None, compute_type: str | None = None) -> None:
        settings = get_settings()
        self.model_name = model_name or getattr(settings, "whisper_model", "base")
        self.device = device or getattr(settings, "whisper_device", "cpu")
        self.compute_type = compute_type or getattr(settings, "whisper_compute_type", "int8")
        self._model: Any = None

    def load_model(self) -> Any:
        if _WHISPER_MODEL_CLASS is None:
            raise ModelLoadError("faster-whisper is not installed")
        logger.info("Loading Faster-Whisper model", extra={"model": self.model_name, "device": self.device, "compute_type": self.compute_type})
        try:
            self._model = _WHISPER_MODEL_CLASS(self.model_name, device=self.device, compute_type=self.compute_type)
        except Exception as exc:
            raise ModelLoadError(str(exc)) from exc
        return self._model

    async def transcribe_audio(self, audio_bytes: bytes, *, language: str | None = None, **kwargs: Any) -> TranscriptionResponse:
        if not audio_bytes:
            raise TranscriptionError("Empty recording")
        start = time.perf_counter()
        payload = ensure_wav_bytes(audio_bytes)
        try:
            model = self._model or self.load_model()
            segments, info = await asyncio.to_thread(model.transcribe, payload, language=language, beam_size=5)
        except ModelLoadError:
            raise
        except Exception as exc:
            raise TranscriptionError(str(exc)) from exc
        text = " ".join(segment.text.strip() for segment in segments if getattr(segment, "text", None))
        processing_time = round(time.perf_counter() - start, 3)
        logger.info("Transcription completed", extra={"processing_time": processing_time, "language": info.language})
        return TranscriptionResponse(text=text, language=info.language, confidence=float(info.confidence or 0.0), processing_time=processing_time)

    async def transcribe_file(self, audio_path: str, *, language: str | None = None, **kwargs: Any) -> TranscriptionResponse:
        payload = read_audio_file(audio_path)
        return await self.transcribe_audio(payload, language=language, **kwargs)

    async def transcribe_stream(self, audio_stream: Any, *, language: str | None = None, **kwargs: Any) -> TranscriptionResponse:
        payload = audio_stream.read() if hasattr(audio_stream, "read") else b""
        return await self.transcribe_audio(payload, language=language, **kwargs)


class TranscriptionService:
    """Thin service for transcription requests."""

    def __init__(self, transcriber: BaseTranscriber | None = None) -> None:
        self._transcriber = transcriber or FasterWhisperTranscriber()

    async def transcribe_file(self, audio_path: str, *, language: str | None = None, **kwargs: Any) -> TranscriptionResponse:
        return await self._transcriber.transcribe_file(audio_path, language=language, **kwargs)

    async def transcribe_audio(self, audio_bytes: bytes, *, language: str | None = None, **kwargs: Any) -> TranscriptionResponse:
        return await self._transcriber.transcribe_audio(audio_bytes, language=language, **kwargs)

    async def transcribe_stream(self, audio_stream: Any, *, language: str | None = None, **kwargs: Any) -> TranscriptionResponse:
        return await self._transcriber.transcribe_stream(audio_stream, language=language, **kwargs)
