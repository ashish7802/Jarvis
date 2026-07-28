from __future__ import annotations

import asyncio
from typing import Any
from loguru import logger

from backend.config.settings import get_settings
from backend.voice.wake_detector import WakeDetector
from backend.voice.wake_listener import WakeListener
from backend.voice.wake_events import WakeEvent
from backend.voice.schemas import WakeStatus


class WakeService:
    """High-level service coordinating WakeDetector and WakeListener."""

    def __init__(
        self,
        *,
        detector: WakeDetector | None = None,
        listener: WakeListener | None = None,
        engine: str = "openwakeword",
        model: str = "hey_jarvis",
        threshold: float = 0.5,
    ) -> None:
        if detector is None:
            settings = get_settings()
            self.detector = WakeDetector(
                engine=settings.wake_engine,
                model=settings.wake_model,
                threshold=settings.wake_threshold,
                device=settings.mic_device,
            )
        else:
            self.detector = detector
        self.listener = listener or WakeListener(detector=self.detector)

    async def start(self) -> WakeEvent | None:
        """Start listening and return the detected WakeEvent if triggered."""
        await self.listener.start()
        return await self.listener.listen()

    async def stop(self) -> None:
        """Stop wake listener."""
        await self.listener.stop()

    async def pause(self) -> None:
        """Pause wake listener."""
        await self.listener.pause()

    async def resume(self) -> None:
        """Resume wake listener."""
        await self.listener.resume()

    def get_status(self) -> WakeStatus:
        """Get current status of wake listener."""
        state = "paused" if self.listener.is_paused() else ("running" if self.listener.is_running() else "stopped")
        return WakeStatus(
            state=state,
            engine=self.detector.engine,
            model=self.detector.model,
            threshold=self.detector.threshold,
        )

    async def test_detection(self) -> WakeEvent | None:
        """Smoke test wake detector with silent audio payload."""
        try:
            score = await self.detector.predict(b"\x00" * 2560)
            return WakeEvent(
                confidence=score,
                wake_word=self.detector.model,
                engine=self.detector.engine,
                device=self.detector.device,
            )
        except Exception as exc:
            logger.warning("Wake detection test error: %s", exc)
            return None
