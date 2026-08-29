"""Text-to-speech using edge-tts (Microsoft cloud), played locally.

NOTE: edge-tts is a *cloud-dependent* service. Playback is local
through sounddevice, but the audio is synthesized via Microsoft's
endpoint. This is honestly documented in the README.
"""

from __future__ import annotations

import asyncio
import logging
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

log = logging.getLogger("jarvis.tts")


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _split_sentences(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    return [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]


class TTSService:
    """Synthesizes text with edge-tts and plays it through the audio player.

    The service owns its own cache directory and cleans up files after
    playback so disk usage does not grow.
    """

    def __init__(
        self,
        voice: str = "en-US-GuyNeural",
        cache_dir: Optional[Path] = None,
    ) -> None:
        self.voice = voice
        self.cache_dir = cache_dir or (Path(tempfile_default()) / "tts_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._player = None  # injected by main
        self._stop = threading.Event()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Wiring
    # ------------------------------------------------------------------
    def attach_player(self, player) -> None:
        self._player = player

    def stop(self) -> None:
        self._stop.set()
        if self._player is not None:
            self._player.stop()

    # ------------------------------------------------------------------
    # Synthesis
    # ------------------------------------------------------------------
    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is not None and self._loop.is_running():
            return self._loop
        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(
            target=self._loop.run_forever,
            name="tts-loop",
            daemon=True,
        )
        self._loop_thread.start()
        return self._loop

    def _synthesize_sync(self, text: str) -> Optional[Path]:
        loop = self._ensure_loop()
        coro = self._synthesize_async(text)
        fut = asyncio.run_coroutine_threadsafe(coro, loop)
        return fut.result(timeout=30)

    async def _synthesize_async(self, text: str) -> Optional[Path]:
        try:
            import edge_tts  # type: ignore
        except ImportError as e:
            log.error("edge-tts not installed: %s", e)
            return None
        out_path = self.cache_dir / f"tts-{uuid.uuid4().hex}.mp3"
        try:
            communicate = edge_tts.Communicate(text=text, voice=self.voice)
            await communicate.save(str(out_path))
            if not out_path.exists() or out_path.stat().st_size == 0:
                log.error("TTS produced empty file for %r", text[:60])
                return None
            return out_path
        except Exception as exc:
            log.exception("TTS synthesis failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Public speak API
    # ------------------------------------------------------------------
    def speak(self, text: str) -> bool:
        """Synthesize and play `text`. Returns True on full playback."""
        self._stop.clear()
        if self._player is None:
            log.error("TTS has no player attached")
            return False
        sentences = _split_sentences(text)
        if not sentences:
            return False
        for sentence in sentences:
            if self._stop.is_set():
                return False
            try:
                path = self._synthesize_sync(sentence)
            except Exception as exc:
                log.exception("TTS synth exception: %s", exc)
                path = None
            if path is None:
                # Fall back to a no-audio-but-no-crash path.
                continue
            try:
                ok = self._player.play_file(path)
            except Exception as exc:
                log.exception("TTS playback exception: %s", exc)
                ok = False
            finally:
                try:
                    path.unlink(missing_ok=True)
                except Exception:
                    pass
            if not ok or self._stop.is_set():
                return False
            time.sleep(0.05)  # tiny gap between sentences
        return not self._stop.is_set()


def tempfile_default() -> str:
    import tempfile

    return tempfile.gettempdir()
