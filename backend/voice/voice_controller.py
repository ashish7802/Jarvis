from __future__ import annotations

from typing import Any


class VoiceController:
    """Thin controller exposing lifecycle methods for the voice pipeline."""

    def __init__(self, *, pipeline: Any | None = None) -> None:
        self._pipeline = pipeline

    async def start(self) -> dict[str, Any]:
        if self._pipeline is None:
            return {"status": "running"}
        return await self._pipeline.start()

    async def stop(self) -> dict[str, Any]:
        if self._pipeline is None:
            return {"status": "stopped"}
        return await self._pipeline.stop()

    async def run_once(self) -> dict[str, Any]:
        if self._pipeline is None:
            return {"result": "ok"}
        return await self._pipeline.run_once()

    def status(self) -> dict[str, Any]:
        if self._pipeline is None:
            return {"state": "idle"}
        return self._pipeline.status()
