"""Audio recording and playback for JARVIS.

Defaults:
- 16 kHz, mono, int16 — Whisper-friendly and small.
- Uses sounddevice for both capture and playback.
- All blocking calls are wrapped so they can be interrupted by a
  shutdown event.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import sounddevice as sd
import soundfile as sf

log = logging.getLogger("jarvis.audio")


SAMPLE_RATE = 16_000
CHANNELS = 1
DTYPE = "int16"
BLOCK_MS = 30  # ~30ms blocks — small enough for responsive VAD


@dataclass
class AudioError(RuntimeError):
    pass


def rms_level(frames: np.ndarray) -> float:
    if frames.size == 0:
        return 0.0
    f = frames.astype(np.float32)
    if f.ndim > 1:
        f = f.mean(axis=1)
    return float(math.sqrt(np.mean(f * f) + 1e-12))


class Recorder:
    """Synchronous one-shot command recorder with silence detection."""

    def __init__(
        self,
        sample_rate: int = SAMPLE_RATE,
        channels: int = CHANNELS,
        max_seconds: float = 10.0,
        silence_timeout: float = 1.5,
        silence_threshold_rms: float = 600.0,
    ) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.max_seconds = max_seconds
        self.silence_timeout = silence_timeout
        self.silence_threshold_rms = silence_threshold_rms
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def record(self) -> Optional[np.ndarray]:
        """Record one utterance. Returns int16 mono numpy array, or None on
        silence-only / error / interruption."""
        self._stop.clear()
        block_size = max(1, int(self.sample_rate * BLOCK_MS / 1000))
        frames: list[np.ndarray] = []
        started_at: float | None = None
        last_sound_at = time.monotonic()
        total_samples = 0

        log.debug(
            "recorder.start sr=%d bs=%d max=%.1fs sil=%.1fs thr=%.0f",
            self.sample_rate,
            block_size,
            self.max_seconds,
            self.silence_timeout,
            self.silence_threshold_rms,
        )

        try:
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=DTYPE,
                blocksize=block_size,
            ) as stream:
                while not self._stop.is_set():
                    block, _overflowed = stream.read(block_size)
                    if block.size == 0:
                        continue
                    frames.append(block.copy())
                    total_samples += block.shape[0]
                    level = rms_level(block)
                    now = time.monotonic()
                    if level >= self.silence_threshold_rms:
                        if started_at is None:
                            started_at = now
                            log.debug("recorder.voice_start level=%.0f", level)
                        last_sound_at = now
                    if started_at is not None and (now - last_sound_at) >= self.silence_timeout:
                        log.debug("recorder.silence_timeout")
                        break
                    if total_samples >= int(self.sample_rate * self.max_seconds):
                        log.debug("recorder.max_timeout")
                        break
        except Exception as exc:
            log.exception("recorder error: %s", exc)
            return None

        if not frames or started_at is None:
            log.debug("recorder.no_speech")
            return None

        audio = np.concatenate(frames, axis=0).astype(np.int16)
        if audio.ndim > 1:
            audio = audio.mean(axis=1).astype(np.int16)
        duration = audio.shape[0] / self.sample_rate
        log.info("recorder.done duration=%.2fs samples=%d", duration, audio.shape[0])
        return audio

    def save_wav(self, audio: np.ndarray, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(path), audio, self.sample_rate, subtype="PCM_16")
        return path


class Player:
    """Synchronous audio playback with interrupt support."""

    def __init__(self) -> None:
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._current_stream: sd.OutputStream | None = None

    def stop(self) -> None:
        self._stop.set()
        with self._lock:
            if self._current_stream is not None:
                try:
                    self._current_stream.abort()
                except Exception:
                    pass

    def play_file(self, path: Path) -> bool:
        """Play a wav/mp3 file. Returns True if fully played."""
        self._stop.clear()
        if not path.exists():
            log.error("player.missing_file path=%s", path)
            return False
        try:
            data, sr = sf.read(str(path), dtype="float32")
            if data.ndim > 1:
                data = data.mean(axis=1)
        except Exception as exc:
            log.exception("player.read_failed path=%s err=%s", path, exc)
            return False

        log.info("player.play path=%s sr=%d dur=%.2fs", path, sr, data.shape[0] / sr)
        try:
            with self._lock:
                self._current_stream = sd.OutputStream(
                    samplerate=sr, channels=1, dtype="float32"
                )
                self._current_stream.start()
                stream = self._current_stream
            chunk = max(1, int(sr * 0.05))
            i = 0
            n = data.shape[0]
            while i < n and not self._stop.is_set():
                end = min(i + chunk, n)
                stream.write(data[i:end].reshape(-1, 1))
                i = end
            with self._lock:
                if self._current_stream is stream:
                    self._current_stream.stop()
                    self._current_stream.close()
                    self._current_stream = None
        except Exception as exc:
            log.exception("player.play_failed err=%s", exc)
            with self._lock:
                if self._current_stream is not None:
                    try:
                        self._current_stream.close()
                    except Exception:
                        pass
                    self._current_stream = None
            return False
        return not self._stop.is_set()
