from __future__ import annotations

import asyncio
from typing import Any
from loguru import logger

from backend.voice.voice_pipeline import VoicePipeline


class VoiceController:
    """Lifecycle manager coordinating VoicePipeline execution and states."""

    def __init__(self, pipeline: VoicePipeline | None = None) -> None:
        self.pipeline = pipeline or VoicePipeline()
        self._paused = False

    async def start(self) -> dict[str, Any]:
        """Start the voice pipeline."""
        self._paused = False
        res = await self.pipeline.start()
        logger.info("VoiceController started")
        return res

    async def stop(self) -> dict[str, Any]:
        """Stop the voice pipeline."""
        self._paused = False
        res = await self.pipeline.stop()
        logger.info("VoiceController stopped")
        return res

    async def pause(self) -> dict[str, Any]:
        """Pause processing in voice pipeline."""
        self._paused = True
        logger.info("VoiceController paused")
        return {"status": "paused"}

    async def resume(self) -> dict[str, Any]:
        """Resume processing in voice pipeline."""
        self._paused = False
        logger.info("VoiceController resumed")
        return {"status": "running"}

    async def run_once(self) -> dict[str, Any]:
        """Run a single interaction cycle if active and not paused."""
        if self._paused:
            return {"wake_detected": False, "status": "paused"}
        return await self.pipeline.run_once()

    def status(self) -> dict[str, Any]:
        """Return current VoiceController and VoicePipeline status."""
        pipe_status = self.pipeline.status()
        state = "paused" if self._paused else pipe_status.get("state", "idle")
        return {
            "running": pipe_status.get("running", False) and not self._paused,
            "paused": self._paused,
            "state": state,
        }

    def is_running(self) -> bool:
        return self.pipeline._running and not self._paused

    def is_paused(self) -> bool:
        return self._paused
