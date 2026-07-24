from __future__ import annotations

import asyncio
import time
from typing import Any

from loguru import logger


from backend.services.llm_service import LLMService
from backend.voice.audio_capture import AudioRecorder
from backend.voice.audio_player import AudioPlayer
from backend.voice.speech_to_text import FasterWhisperTranscriber
from backend.voice.text_to_speech import TextToSpeechService
from backend.voice.wake_service import WakeService


class VoicePipeline:
    """Coordinate wake word, STT, LLM, TTS, and Audio Player into a single voice interaction."""

    def __init__(
        self,
        *,
        wake_service: Any | None = None,
        recorder: Any | None = None,
        transcriber: Any | None = None,
        llm_service: Any | None = None,
        tts_service: Any | None = None,
        player: Any | None = None,
    ) -> None:
        self._wake_service = wake_service or WakeService()
        self._recorder = recorder or AudioRecorder(record_duration=4.0)
        self._transcriber = transcriber or FasterWhisperTranscriber()
        self._llm_service = llm_service or LLMService()
        self._tts_service = tts_service or TextToSpeechService()
        self._player = player or AudioPlayer()
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
        wake_event = None
        if self._wake_service is not None:
            wake_event = await self._wake_service.start()
            if wake_event is None:
                logger.info("No wake word detected (timeout)")
                return {
                    "wake_detected": False,
                    "recognized_text": "",
                    "llm_response": "",
                    "execution_time": round(time.perf_counter() - start_time, 3),
                }

        logger.info("Wake word detected!")
        logger.info("Recording...")
        audio_bytes = b""
        if self._recorder is not None:
            audio_bytes = await self._recorder.record_audio()

        logger.info("Recognizing speech...")
        recognized = None
        if self._transcriber is not None and audio_bytes:
            recognized = await self._transcriber.transcribe_audio(audio_bytes)
        recognized_text = getattr(recognized, "text", "") if recognized is not None else ""
        logger.info("Recognized: %s", recognized_text)

        logger.info("Thinking...")
        llm_response = ""
        if self._llm_service is not None and recognized_text:
            llm_response = await self._llm_service.generate_completion(recognized_text)
        logger.info("LLM response: %s", llm_response)

        logger.info("Speaking...")
        if self._tts_service is not None and llm_response:
            speech_resp = await self._tts_service.speak(llm_response)
            if self._player is not None and getattr(speech_resp, "audio_bytes", None):
                await self._player.play(speech_resp.audio_bytes)

        logger.info("Done cycle.")
        return {
            "wake_detected": True,
            "recognized_text": recognized_text,
            "llm_response": llm_response,
            "execution_time": round(time.perf_counter() - start_time, 3),
        }

    def status(self) -> dict[str, Any]:
        return {"running": self._running, "state": "running" if self._running else "idle"}
