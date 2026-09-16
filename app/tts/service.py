"""Cancellable cloud speech with bounded retries and in-memory phrase caching."""
import asyncio
from collections import OrderedDict
import concurrent.futures
import logging
import re
import threading
import uuid
from pathlib import Path

log = logging.getLogger("jarvis.tts")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?।])\s+")


def _split_sentences(text):
    text = re.sub(r"\[([^\]]+)\]\(https?://[^)]+\)", r"\1", text)
    text = re.sub(r"(?m)^\s*(?:#{1,6}\s+|[-*]\s+)", "", text)
    text = text.replace("**", "").replace("`", "").strip()
    pieces = []
    for sentence in _SENTENCE_SPLIT.split(text):
        words = sentence.split()
        current = ""
        for word in words:
            if len(current) + len(word) > 500 and current:
                pieces.append(current)
                current = ""
            current = (current + " " + word).strip()
        if current:
            pieces.append(current)
    # Synthesize short replies together so each sentence doesn't need another
    # network round trip before it can play. Keep long replies bounded.
    chunks = []
    for piece in pieces:
        if chunks and len(chunks[-1]) + len(piece) + 1 <= 500:
            chunks[-1] += " " + piece
        else:
            chunks.append(piece)
    return chunks


class TTSService:
    def __init__(self, voice="en-US-GuyNeural", cache_dir=None,
                 hindi_voice="hi-IN-SwaraNeural", provider="edge"):
        self.voice, self.hindi_voice, self.provider = voice, hindi_voice, provider
        self.cache_dir = cache_dir or (Path(tempfile_default()) / "tts_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._player = None
        self._stop = threading.Event()
        self.turn_cancelled = threading.Event()
        self.language_hint = "en"
        self._closed = threading.Event()
        self._loop = None
        self._loop_thread = None
        self._pending = None
        self._loop_lock = threading.Lock()
        self._phrases = OrderedDict()

    def attach_player(self, player):
        self._player = player

    def _interrupted(self):
        return self._stop.is_set() or self._closed.is_set() or self.turn_cancelled.is_set()

    def stop(self):
        self._stop.set()
        if self._pending is not None:
            self._pending.cancel()
        if self._player is not None:
            self._player.stop()

    def cancel(self):
        self._closed.set()
        self.stop()

    def _ensure_loop(self):
        with self._loop_lock:
            if self._closed.is_set():
                raise RuntimeError("TTS is shut down")
            if self._loop is None:
                self._loop = asyncio.new_event_loop()
                self._loop_thread = threading.Thread(target=self._loop.run_forever,
                                                     name="tts-loop", daemon=True)
                self._loop_thread.start()
            return self._loop

    def _synthesize_sync(self, text):
        loop = self._ensure_loop()
        future = asyncio.run_coroutine_threadsafe(self._synthesize_async(text), loop)
        self._pending = future
        try:
            import time
            deadline = time.monotonic() + 20
            while not self._interrupted() and time.monotonic() < deadline:
                try:
                    return future.result(timeout=.05)
                except concurrent.futures.TimeoutError:
                    continue
            future.cancel()
            return None
        except (concurrent.futures.TimeoutError, concurrent.futures.CancelledError):
            future.cancel()
            return None
        finally:
            self._pending = None

    def prewarm(self, phrases):
        """Cache short acknowledgements during startup without playing them."""
        if self.provider == "mock" or self._closed.is_set():
            return
        async def prepare():
            for phrase in phrases:
                if self._closed.is_set():
                    return
                path = await self._synthesize_async(phrase)
                if path is not None:
                    path.unlink(missing_ok=True)
        asyncio.run_coroutine_threadsafe(prepare(), self._ensure_loop())

    async def _synthesize_async(self, text):
        import edge_tts
        voice = self.hindi_voice if re.search(r"[\u0900-\u097f]", text) or self.language_hint == "hi" else self.voice
        key = (voice, text)
        path = self.cache_dir / f"tts-{uuid.uuid4().hex}.mp3"
        complete = False
        try:
            if key in self._phrases:
                path.write_bytes(self._phrases[key])
                self._phrases.move_to_end(key)
            else:
                async with asyncio.timeout(15):
                    await edge_tts.Communicate(text=text, voice=voice).save(str(path))
            if not path.exists() or path.stat().st_size == 0:
                return None
            if len(text) <= 120 and path.stat().st_size <= 128000:
                self._phrases[key] = path.read_bytes()
                while len(self._phrases) > 16:
                    self._phrases.popitem(last=False)
            complete = True
            return path
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("Speech synthesis failed: %s", type(exc).__name__)
            return None
        finally:
            if not complete or self._interrupted():
                path.unlink(missing_ok=True)

    def speak(self, text):
        if self._closed.is_set() or self.turn_cancelled.is_set():
            return False
        self._stop.clear()
        sentences = _split_sentences(text)
        if self.provider == "mock":
            return bool(sentences)
        if self._player is None or not sentences:
            return False
        for sentence in sentences:
            path = None
            for attempt in range(2):
                if self._interrupted():
                    return False
                try:
                    path = self._synthesize_sync(sentence)
                except Exception as exc:
                    log.warning("TTS failed: %s", type(exc).__name__)
                if path is not None:
                    break
                if attempt == 0 and self._stop.wait(0.3):
                    return False
            if path is None:
                return False
            try:
                if self._interrupted():
                    return False
                if not self._player.play_file(path):
                    return False
            except Exception:
                log.exception("Speech playback failed")
                return False
            finally:
                path.unlink(missing_ok=True)
            if self._stop.wait(0.05):
                return False
        return not self._interrupted()

    def shutdown(self):
        self.cancel()
        loop = self._loop
        if loop is not None and loop.is_running():
            async def drain():
                tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
            future = asyncio.run_coroutine_threadsafe(drain(), loop)
            try:
                future.result(timeout=3)
            finally:
                loop.call_soon_threadsafe(loop.stop)
                self._loop_thread.join(timeout=3)
            if not self._loop_thread.is_alive():
                loop.close()
        self._phrases.clear()


def tempfile_default():
    import tempfile
    return tempfile.gettempdir()
