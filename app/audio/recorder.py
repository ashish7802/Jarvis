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
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import sounddevice as sd
import soundfile as sf
from app.audio.hearing import PROFILES, NoiseFloor, boost_pcm, meter_value

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
        silence_threshold_rms: float | None = None,
        hearing_profile: str = "soft",
        on_level=None,
    ) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.max_seconds = max_seconds
        self.silence_timeout = silence_timeout
        self.silence_threshold_rms = silence_threshold_rms
        self.hearing_profile = hearing_profile if hearing_profile in PROFILES else "soft"
        self.on_level = on_level
        self.noise_source = None
        self.turn_cancelled = threading.Event()
        self._stop = threading.Event()
        self.last_error = False

    def stop(self) -> None:
        self._stop.set()

    def set_hearing_profile(self, profile):
        if profile not in PROFILES:
            raise ValueError("Unknown hearing profile")
        self.hearing_profile = profile

    def _interrupted(self):
        return self._stop.is_set() or self.turn_cancelled.is_set()

    def record(self) -> Optional[np.ndarray]:
        """Record speech with a noise-relative gate, onset buffer and bounded gain."""
        if self._interrupted():
            return None
        self.last_error = False
        profile = PROFILES[self.hearing_profile]
        block_size = max(1, int(self.sample_rate * BLOCK_MS / 1000))
        frames = []
        preroll = deque(maxlen=max(1, round(450 / BLOCK_MS)))
        noise = NoiseFloor()
        baseline = self.noise_source() if self.noise_source else None
        started = False
        consecutive = voiced = total_samples = silent_samples = 0
        deadline = time.monotonic() + self.max_seconds
        try:
            with sd.InputStream(samplerate=self.sample_rate, channels=self.channels,
                                dtype=DTYPE, blocksize=block_size) as stream:
                while not self._interrupted() and time.monotonic() < deadline:
                    block, overflowed = stream.read(block_size)
                    if not block.size:
                        continue
                    block = block.copy()
                    total_samples += len(block)
                    level = rms_level(block)
                    if baseline is None:
                        noise.update(level)
                    floor = baseline if baseline is not None else noise.value
                    threshold = self.silence_threshold_rms
                    if threshold is None:
                        threshold = max(profile.minimum_rms, (floor or 0) * profile.noise_ratio)
                    # With no standby calibration, reserve 180 ms to measure the room.
                    calibrated = floor is not None or self.silence_threshold_rms is not None
                    above = calibrated and level >= threshold
                    if self.on_level and total_samples // block_size % 3 == 0:
                        self.on_level({"level": meter_value(level), "active": above,
                                       "source": "recording", "clipping": bool(np.any(np.abs(block.astype(np.int32)) >= 32000))})
                    if started:
                        frames.append(block)
                    else:
                        preroll.append(block)
                    consecutive = consecutive + 1 if above else 0
                    if not started and consecutive >= 3:
                        started = True
                        frames.extend(preroll)
                        voiced = consecutive
                    elif started and above:
                        voiced += 1
                    if started:
                        silent_samples = 0 if above else silent_samples + len(block)
                        if silent_samples >= self.sample_rate * self.silence_timeout:
                            break
                    elif floor is not None and not above:
                        # Adapt slowly between words, never learn the active utterance as noise.
                        baseline = floor * .98 + level * .02
                    if total_samples >= int(self.sample_rate * self.max_seconds):
                        break
        except Exception as exc:
            self.last_error = True
            log.exception("recorder error: %s", exc)
            return None
        finally:
            if self.on_level:
                self.on_level({"level": 0, "active": False, "source": "recording", "clipping": False})
        if self._interrupted() or not started or voiced < 4:
            return None
        audio = np.concatenate(frames, axis=0).astype(np.int16)
        if audio.ndim > 1:
            audio = audio.mean(axis=1).astype(np.int16)
        audio = boost_pcm(audio, profile.max_gain)
        log.info("recorder.done duration=%.2fs profile=%s", len(audio) / self.sample_rate, self.hearing_profile)
        return audio

    def save_wav(self, audio: np.ndarray, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(path), audio, self.sample_rate, subtype="PCM_16")
        return path


class Player:
    """Synchronous audio playback with interrupt support."""

    def __init__(self) -> None:
        self._stop = threading.Event()
        self.turn_cancelled = threading.Event()
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
        if self.turn_cancelled.is_set():
            return False
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
                if self.turn_cancelled.is_set() or self._stop.is_set():
                    return False
                self._current_stream = sd.OutputStream(
                    samplerate=sr, channels=1, dtype="float32"
                )
                self._current_stream.start()
                stream = self._current_stream
            chunk = max(1, int(sr * 0.05))
            i = 0
            n = data.shape[0]
            while i < n and not self._stop.is_set() and not self.turn_cancelled.is_set():
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
        return not self._stop.is_set() and not self.turn_cancelled.is_set()
