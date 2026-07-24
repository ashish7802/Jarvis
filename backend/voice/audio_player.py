from __future__ import annotations

import asyncio
import io
import wave
from typing import Any

from loguru import logger

try:
    import sounddevice as sounddevice
except Exception:  # pragma: no cover
    sounddevice = None

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None


class AudioPlayer:
    """Non-blocking audio player for playing synthesized speech over system speakers."""

    def __init__(self, device: str | None = None) -> None:
        self.device = device

    async def play(self, audio_bytes: bytes) -> bool:
        """Play WAV or raw PCM audio bytes asynchronously without blocking the event loop."""
        if not audio_bytes:
            logger.warning("Audio player received empty audio payload")
            return False

        return await asyncio.to_thread(self._play_sync, audio_bytes)

    def _play_sync(self, audio_bytes: bytes) -> bool:
        if sounddevice is None or np is None:
            logger.warning("sounddevice or numpy not available for playback")
            return False

        try:
            # Parse WAV file header
            with wave.open(io.BytesIO(audio_bytes), "rb") as wav_file:
                sample_rate = wav_file.getframerate()
                channels = wav_file.getnchannels()
                sample_width = wav_file.getsampwidth()
                frames = wav_file.readframes(wav_file.getnframes())

                if sample_width == 2:
                    dtype = np.int16
                elif sample_width == 4:
                    dtype = np.int32
                elif sample_width == 1:
                    dtype = np.uint8
                else:
                    dtype = np.int16

                audio_data = np.frombuffer(frames, dtype=dtype)
                if channels > 1:
                    audio_data = audio_data.reshape(-1, channels)

                sounddevice.play(audio_data, samplerate=sample_rate, device=self.device)
                sounddevice.wait()
                return True
        except Exception:
            # If wave parsing fails, attempt raw PCM 16kHz mono int16 fallback
            try:
                audio_data = np.frombuffer(audio_bytes, dtype=np.int16)
                sounddevice.play(audio_data, samplerate=16000, device=self.device)
                sounddevice.wait()
                return True
            except Exception as exc:
                logger.error("Audio playback failed: %s", exc)
                return False


__all__ = ["AudioPlayer"]
