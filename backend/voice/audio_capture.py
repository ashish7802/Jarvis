from __future__ import annotations

import asyncio
import time
from typing import Any

from loguru import logger

from backend.config.settings import get_settings
from backend.voice.exceptions import MicrophoneError

try:
    import sounddevice as sounddevice
except Exception:  # pragma: no cover - optional dependency
    sounddevice = None


class AudioRecorder:
    """Capture microphone audio asynchronously with int16 PCM format."""

    def __init__(self, *, sample_rate: int | None = None, channels: int | None = None, chunk_size: int | None = None, record_duration: float | None = None, device: str | None = None) -> None:
        settings = get_settings()
        self.sample_rate = sample_rate or int(getattr(settings, "audio_sample_rate", 16000))
        self.channels = channels or int(getattr(settings, "audio_channels", 1))
        self.chunk_size = chunk_size or 1280
        self.record_duration = record_duration or 4.0
        self.device = device

    async def record_audio(self) -> bytes:
        if sounddevice is None:
            raise MicrophoneError("sounddevice is not available")

        logger.info("Recording started", extra={"sample_rate": self.sample_rate, "channels": self.channels})
        start = time.perf_counter()
        frames: list[bytes] = []
        try:
            with sounddevice.InputStream(samplerate=self.sample_rate, channels=self.channels, blocksize=self.chunk_size, dtype="int16", device=self.device) as stream:
                while time.perf_counter() - start < self.record_duration:
                    chunk, _ = await asyncio.to_thread(self._read_chunk, stream)
                    if chunk:
                        frames.append(chunk)
                    await asyncio.sleep(0.001)
        except Exception as exc:
            logger.exception("Recording failed")
            raise MicrophoneError(str(exc)) from exc

        logger.info("Recording stopped", extra={"duration": round(time.perf_counter() - start, 3)})
        return b"".join(frames)

    def _read_chunk(self, stream: Any) -> tuple[bytes, int]:
        if stream is not None and hasattr(stream, "read"):
            payload = stream.read(self.chunk_size)
            if isinstance(payload, tuple):
                payload = payload[0]
            if hasattr(payload, "tobytes"):
                return payload.tobytes(), 1
            if isinstance(payload, (bytes, bytearray)):
                return bytes(payload), 1
            if isinstance(payload, list):
                return b"".join(payload), 1
            return b"", 0
        if sounddevice is None:
            return b"", 0
        recorder = getattr(sounddevice, "rec", None)
        if recorder is None:
            return b"", 0
        res = recorder(self.chunk_size, samplerate=self.sample_rate, channels=self.channels, dtype="int16", blocking=False)
        if hasattr(res, "tobytes"):
            return res.tobytes(), 1
        return b"", 0
