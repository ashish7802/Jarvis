from __future__ import annotations

import asyncio
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from loguru import logger

from backend.config.settings import get_settings
from backend.voice.exceptions import SpeechError
from backend.voice.schemas import SpeechResponse, VoiceInfo
from backend.voice.voice_cache import VoiceCache

try:
    import edge_tts
except Exception:  # pragma: no cover - optional dependency
    edge_tts = None


class TextToSpeechService:
    """Asynchronous text-to-speech service backed by Edge TTS."""

    def __init__(self, *, edge_tts_module: Any | None = None, cache: VoiceCache | None = None) -> None:
        self._edge_tts = edge_tts_module or edge_tts
        self._cache = cache or VoiceCache()
        self._settings = get_settings()

    async def speak(self, text: str, *, voice: str | None = None, rate: str | None = None, volume: str | None = None, pitch: str | None = None, file_format: str = "wav") -> SpeechResponse:
        if not text or not text.strip():
            raise SpeechError("empty text")
        if file_format.lower() not in {"wav", "mp3"}:
            raise SpeechError("invalid configuration")

        selected_voice = voice or self._settings.edge_tts_voice
        if not selected_voice:
            raise SpeechError("invalid configuration")
        logger.info("voice selected", extra={"voice": selected_voice})

        cache_key = (text.strip(), selected_voice, rate or self._settings.edge_tts_rate, volume or self._settings.edge_tts_volume, pitch or self._settings.edge_tts_pitch, file_format)
        cached_bytes = self._cache.get(text.strip(), voice=selected_voice, rate=rate or self._settings.edge_tts_rate, volume=volume or self._settings.edge_tts_volume, pitch=pitch or self._settings.edge_tts_pitch, file_format=file_format)
        if cached_bytes is not None:
            logger.info("cache hit", extra={"voice": selected_voice})
            return SpeechResponse(audio_bytes=cached_bytes, content_type=self._content_type(file_format), voice=selected_voice, file_format=file_format, cached=True)

        logger.info("synthesis started", extra={"voice": selected_voice, "file_format": file_format})
        start = time.perf_counter()
        try:
            if self._edge_tts is None:
                raise SpeechError("edge-tts is not installed")
            communicate = self._edge_tts.Communicate(text.strip(), voice=selected_voice, rate=rate or self._settings.edge_tts_rate, volume=volume or self._settings.edge_tts_volume, pitch=pitch or self._settings.edge_tts_pitch)
            audio_bytes = await asyncio.wait_for(self._collect_audio(communicate), timeout=30)
            if not audio_bytes:
                raise SpeechError("empty audio output")
            self._cache.set(text.strip(), audio_bytes, voice=selected_voice, rate=rate or self._settings.edge_tts_rate, volume=volume or self._settings.edge_tts_volume, pitch=pitch or self._settings.edge_tts_pitch, file_format=file_format)
            processing_time = round(time.perf_counter() - start, 3)
            logger.info("synthesis completed", extra={"voice": selected_voice, "processing_time": processing_time})
            logger.info("cache miss", extra={"voice": selected_voice})
            return SpeechResponse(audio_bytes=audio_bytes, content_type=self._content_type(file_format), voice=selected_voice, file_format=file_format, cached=False, metadata={"processing_time": processing_time})
        except asyncio.TimeoutError as exc:
            logger.exception("synthesis timed out")
            raise SpeechError("timeout") from exc
        except SpeechError:
            raise
        except Exception as exc:
            logger.exception("synthesis failed")
            raise SpeechError(str(exc)) from exc

    async def synthesize(self, text: str, *, voice: str | None = None, rate: str | None = None, volume: str | None = None, pitch: str | None = None, file_format: str = "wav") -> SpeechResponse:
        return await self.speak(text, voice=voice, rate=rate, volume=volume, pitch=pitch, file_format=file_format)

    async def save_to_file(self, text: str, output_path: str, *, voice: str | None = None, rate: str | None = None, volume: str | None = None, pitch: str | None = None, file_format: str = "wav") -> SpeechResponse:
        response = await self.speak(text, voice=voice, rate=rate, volume=volume, pitch=pitch, file_format=file_format)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as handle:
            handle.write(response.audio_bytes)
        response.metadata["output_path"] = output_path
        return response

    async def stream(self, text: str, *, voice: str | None = None, rate: str | None = None, volume: str | None = None, pitch: str | None = None, file_format: str = "wav") -> bytes:
        response = await self.speak(text, voice=voice, rate=rate, volume=volume, pitch=pitch, file_format=file_format)
        return response.audio_bytes

    def list_voices(self) -> list[VoiceInfo]:
        return [VoiceInfo(name=name, locale=name.split("-", 2)[0] + "-" + name.split("-", 2)[1], gender="neutral") for name in self._default_voices()]

    def _content_type(self, file_format: str) -> str:
        if file_format.lower() == "mp3":
            return "audio/mpeg"
        return "audio/wav"

    async def _collect_audio(self, communicate: Any) -> bytes:
        chunks: list[bytes] = []
        async for chunk in communicate.stream():
            if isinstance(chunk, bytes):
                chunks.append(chunk)
            elif isinstance(chunk, dict) and chunk.get("type") == "audio":
                data = chunk.get("data")
                if isinstance(data, (bytes, bytearray)):
                    chunks.append(bytes(data))
        return b"".join(chunks)

    def _default_voices(self) -> list[str]:
        return [
            "en-US-AriaNeural",
            "en-US-GuyNeural",
            "en-IN-NeerjaNeural",
            "hi-IN-SwaraNeural",
        ]
