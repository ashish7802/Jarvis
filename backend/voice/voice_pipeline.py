from __future__ import annotations

import asyncio
import time
from typing import Any

from loguru import logger


class VoicePipeline:
    """Coordinate wake word, STT, LLM, and TTS into a single request-response voice interaction."""

    def __init__(self, *, wake_service: Any | None = None, recorder: Any | None = None, transcriber: Any | None = None, llm_service: Any | None = None, tts_service: Any | None = None) -> None:
        self._wake_service = wake_service
        self._recorder = recorder
        self._transcriber = transcriber
        self._llm_service = llm_service
        self._tts_service = tts_service
        self._running = False

    async def start(self) -> dict[str, Any]:
        self._running = True
        logger.info("voice pipeline started")
        return {"status": "running"}

    async def stop(self) -> dict[str, Any]:
        self._running = False
        logger.info("voice pipeline stopped")
        return {"status": "stopped"}

    async def run_once(self) -> dict[str, Any]:
        start_time = time.perf_counter()
        logger.info("Waiting for wake word...")
        if self._wake_service is not None:
            await self._wake_service.start()
        logger.info("Wake word detected")
        logger.info("Recording...")
        audio_bytes = b""
        if self._recorder is not None:
            audio_bytes = await self._recorder.record_audio()
        logger.info("Recognizing speech...")
        recognized = None
        if self._transcriber is not None:
            recognized = await self._transcriber.transcribe_audio(audio_bytes)
        recognized_text = getattr(recognized, "text", "") if recognized is not None else ""
        logger.info("Recognized: %s", recognized_text)
        logger.info("Thinking...")
        llm_response = ""
        if self._llm_service is not None:
            llm_response = await self._llm_service.generate_completion(recognized_text or "hello")
        logger.info("Groq response: %s", llm_response)
        logger.info("Speaking...")
        if self._tts_service is not None:
            await self._tts_service.speak(llm_response)
        logger.info("Done.")
        return {
            "recognized_text": recognized_text,
            "llm_response": llm_response,
            "execution_time": round(time.perf_counter() - start_time, 3),
        }

    def status(self) -> dict[str, Any]:
        return {"running": self._running, "state": "running" if self._running else "idle"}
