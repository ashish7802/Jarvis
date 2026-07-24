from __future__ import annotations

import asyncio
import time
from typing import Any

from loguru import logger

from backend.voice.exceptions import MicrophoneError, VoiceError

try:
    import numpy as np
except Exception:  # pragma: no cover - optional dependency
    np = None

try:
    import sounddevice as sounddevice
except Exception:  # pragma: no cover - optional dependency
    sounddevice = None

try:
    import openwakeword
except Exception:  # pragma: no cover - optional dependency
    openwakeword = None


class WakeDetector:
    """Abstract-style wake detector wrapper that isolates wake word detection logic."""

    def __init__(self, *, engine: str | None = None, model: str | None = None, threshold: float = 0.5, device: str | None = None) -> None:
        self.engine = engine or "openwakeword"
        self.model = model or "hey_jarvis"
        self.threshold = threshold
        self.device = device
        self._model: Any = None
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return
        if openwakeword is None or sounddevice is None or np is None:
            raise MicrophoneError("wake word runtime dependencies are missing")
        self._model = openwakeword.OpenWakeWordModel(model_name=self.model)
        self._initialized = True
        logger.info("engine initialized", extra={"engine": self.engine, "model": self.model})

    async def predict(self, audio_chunk: bytes) -> float:
        if not self._initialized:
            await self.initialize()
        if self._model is None:
            raise VoiceError("model was not initialized")
        payload = np.frombuffer(audio_chunk, dtype=np.int16)
        result = self._model.predict(payload)
        score = float(result.get("score", 0.0)) if isinstance(result, dict) else 0.0
        logger.info("wake detected", extra={"confidence": score})
        return score

    async def close(self) -> None:
        self._initialized = False
        self._model = None
