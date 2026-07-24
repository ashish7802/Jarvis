from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from loguru import logger

from backend.config.settings import get_settings
from backend.voice.exceptions import VoiceError
from backend.voice.wake_detector import WakeDetector
from backend.voice.wake_events import WakeEvent
from backend.voice.wake_listener import WakeListener
from backend.voice.wake_models import WakeStatus


class WakeService:
    """Application-facing service for isolated wake word detection."""

    def __init__(self, detector: WakeDetector | None = None, listener: WakeListener | None = None) -> None:
        settings = get_settings()
        self.detector = detector or WakeDetector(engine=settings.wake_engine, model=settings.wake_model, threshold=settings.wake_threshold, device=settings.mic_device)
        self.listener = listener or WakeListener(self.detector, timeout=settings.wake_timeout, cooldown=settings.wake_cooldown)
        self._status = {"running": False, "paused": False, "engine": self.detector.engine, "wake_word": self.detector.model, "threshold": self.detector.threshold, "timeout": self.listener.timeout, "cooldown": self.listener.cooldown, "device": self.detector.device, "last_event": None}

    async def start(self) -> WakeEvent | None:
        await self.detector.initialize()
        await self.listener.start()
        self._status["running"] = True
        self._status["paused"] = False
        return await self.listener.listen()

    async def stop(self) -> None:
        await self.listener.stop()
        self._status["running"] = False
        self._status["paused"] = False

    async def pause(self) -> None:
        await self.listener.pause()
        self._status["paused"] = True

    async def resume(self) -> None:
        await self.listener.resume()
        self._status["paused"] = False

    def is_running(self) -> bool:
        return self.listener.is_running()

    def get_status(self) -> WakeStatus:
        self._status["running"] = self.listener.is_running()
        self._status["paused"] = self.listener.is_paused()
        return WakeStatus(**self._status)

    async def test_detection(self) -> WakeEvent | None:
        return await self.start()
