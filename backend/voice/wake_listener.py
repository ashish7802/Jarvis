from __future__ import annotations

import asyncio
import time
from typing import Any

from loguru import logger

from backend.voice.exceptions import MicrophoneError, VoiceError
from backend.voice.wake_detector import WakeDetector
from backend.voice.wake_events import WakeEvent
from backend.voice.audio_capture import AudioRecorder


class WakeListener:
    """Asynchronous microphone listener for wake word detection."""

    def __init__(self, detector: WakeDetector, *, timeout: float = 5.0, cooldown: float = 1.0, recorder: AudioRecorder | None = None) -> None:
        self.detector = detector
        self.timeout = timeout
        self.cooldown = cooldown
        self.recorder = recorder or AudioRecorder(chunk_size=1280)
        self._running = False
        self._paused = False
        self._last_event_at = 0.0
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        self._running = True
        self._paused = False
        self._stop_event.clear()
        logger.info("listener started", extra={"timeout": self.timeout, "cooldown": self.cooldown})

    async def stop(self) -> None:
        self._running = False
        self._paused = False
        self._stop_event.set()
        logger.info("listener stopped")

    async def pause(self) -> None:
        self._paused = True
        logger.info("listener paused")

    async def resume(self) -> None:
        self._paused = False
        logger.info("listener resumed")

    async def listen(self) -> WakeEvent | None:
        if not self._running:
            await self.start()
        if self._paused:
            return None
        start_time = time.perf_counter()
        
        try:
            from backend.voice.audio_capture import sounddevice
        except Exception:
            sounddevice = None

        if sounddevice is None:
            while not self._stop_event.is_set() and time.perf_counter() - start_time < self.timeout:
                if self._paused:
                    return None
                await asyncio.sleep(0.1)
                if time.perf_counter() - self._last_event_at < self.cooldown:
                    continue
                score = await self.detector.predict(b"\x00" * 2560)
                if score >= self.detector.threshold:
                    self._last_event_at = time.perf_counter()
                    event = WakeEvent(timestamp=self._now(), confidence=score, wake_word=self.detector.model, engine=self.detector.engine, device=self.detector.device)
                    logger.info("wake detected", extra={"confidence": score, "wake_word": event.wake_word})
                    return event
            return None

        try:
            with sounddevice.InputStream(
                samplerate=self.recorder.sample_rate,
                channels=self.recorder.channels,
                blocksize=1280,
                dtype="int16",
                device=self.detector.device
            ) as stream:
                while not self._stop_event.is_set() and time.perf_counter() - start_time < self.timeout:
                    if self._paused:
                        return None
                    chunk, _ = await asyncio.to_thread(self.recorder._read_chunk, stream)
                    if not chunk:
                        await asyncio.sleep(0.01)
                        continue
                    if time.perf_counter() - self._last_event_at < self.cooldown:
                        continue
                    
                    score = await self.detector.predict(chunk)
                    if score >= self.detector.threshold:
                        self._last_event_at = time.perf_counter()
                        event = WakeEvent(timestamp=self._now(), confidence=score, wake_word=self.detector.model, engine=self.detector.engine, device=self.detector.device)
                        logger.info("wake detected", extra={"confidence": score, "wake_word": event.wake_word})
                        return event
        except Exception as exc:
            logger.warning("Error reading microphone for wake detection: %s", exc)
        return None

    def is_running(self) -> bool:
        return self._running

    def is_paused(self) -> bool:
        return self._paused

    def _now(self) -> Any:
        from datetime import datetime, timezone

        return datetime.now(timezone.utc)
