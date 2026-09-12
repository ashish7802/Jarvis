"""Wake-word detection.

Two backends are supported:

1. **openWakeWord** (default, fully local, no API key) — uses the
   pre-trained `hey_jarvis` model shipped with the `openwakeword`
   package, or a custom .tflite / .onnx model if configured.
2. **EnergyGateWakeWord** — a free fallback that uses simple energy
   + duration heuristics. Used automatically if the openWakeWord
   backend fails to load (e.g. onnxruntime missing, no internet for
   the initial model download).

A legacy Porcupine backend is still importable behind a guarded
``try/except`` so existing deployments that already have
``pvporcupine`` installed keep working, but it is *not* part of the
default path. New users should not need a Picovoice access key.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from abc import ABC, abstractmethod
from typing import Optional

import numpy as np
import sounddevice as sd

log = logging.getLogger("jarvis.wakeword")

SAMPLE_RATE = 16_000
FRAME_MS = 30
FRAME_SIZE = int(SAMPLE_RATE * FRAME_MS / 1000)  # samples per frame

# openWakeWord consumes 80 ms (1280 sample) chunks; the mic loop
# accumulates 30 ms frames into a rolling buffer of this size.
OWW_CHUNK_SAMPLES = 1280


class WakeWordDetector(ABC):
    name: str = "base"

    @abstractmethod
    def start(self) -> None:
        """Begin background capture. Idempotent."""

    @abstractmethod
    def stop(self) -> None:
        """Stop capture and release resources. Idempotent."""

    @abstractmethod
    def set_enabled(self, enabled: bool) -> None:
        """Pause/resume detection without tearing down the audio stream."""

    def set_callback(self, cb) -> None:  # noqa: D401
        """Optional: register a zero-arg callback fired on detection."""
        self._on_detect = cb  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Energy-gate fallback
# ---------------------------------------------------------------------------


class EnergyGateWakeWord(WakeWordDetector):
    """A simple fallback wake-word detector.

    It listens for a short burst of audio above a relative energy
    threshold, then ignores further audio for a short cooldown. It
    does not try to verify the *content* of the audio (no STT here),
    so it can be fooled by other loud sounds — but it is fully local
    and dependency-free beyond numpy + sounddevice.
    """

    name = "energy"

    def __init__(
        self,
        keyword: str = "jarvis",
        sample_rate: int = SAMPLE_RATE,
        frame_size: int = FRAME_SIZE,
        threshold_rms: float = 1500.0,
        trigger_frames: int = 4,  # consecutive frames above threshold
        cooldown_seconds: float = 1.5,
    ) -> None:
        self.keyword = keyword
        self.sample_rate = sample_rate
        self.frame_size = frame_size
        self.threshold_rms = threshold_rms
        self.trigger_frames = trigger_frames
        self.cooldown_seconds = cooldown_seconds
        self._stop_event = threading.Event()
        self._enabled = threading.Event()
        self._enabled.set()
        self._thread: Optional[threading.Thread] = None
        self._on_detect: Optional[threading.Callable[[], None]] = None
        self._last_trigger: float = 0.0
        # Auto-calibration runs the first second of audio to learn noise floor.
        self._noise_floor: float = 0.0

    def set_callback(self, cb) -> None:
        self._on_detect = cb

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, name="wakeword-energy", daemon=True
        )
        self._thread.start()
        log.info("EnergyGateWakeWord started (keyword=%r)", self.keyword)

    def stop(self) -> None:
        self._stop_event.set()
        t = self._thread
        if t is not None:
            t.join(timeout=2.0)
            self._thread = None
        log.info("EnergyGateWakeWord stopped")

    def set_enabled(self, enabled: bool) -> None:
        if enabled:
            self._enabled.set()
        else:
            self._enabled.clear()
        log.debug("EnergyGateWakeWord enabled=%s", enabled)

    def _run(self) -> None:
        try:
            stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="int16",
                blocksize=self.frame_size,
            )
        except Exception as exc:
            log.exception("energy-wake: cannot open mic: %s", exc)
            return
        consecutive = 0
        calibrated = False
        calib_samples: list[float] = []
        with stream:
            while not self._stop_event.is_set():
                try:
                    block, _ = stream.read(self.frame_size)
                except Exception as exc:
                    log.exception("energy-wake: read error: %s", exc)
                    break
                if block.size == 0:
                    continue
                rms = float(math.sqrt(np.mean(block.astype(np.float32) ** 2)))
                if not calibrated:
                    calib_samples.append(rms)
                    if len(calib_samples) >= 30:  # ~0.9s
                        self._noise_floor = float(np.median(calib_samples))
                        # Use the larger of configured threshold and 4x noise floor.
                        self.threshold_rms = max(self.threshold_rms, self._noise_floor * 4.0 + 200.0)
                        calibrated = True
                        log.info(
                            "energy-wake: calibrated noise_floor=%.0f threshold=%.0f",
                            self._noise_floor,
                            self.threshold_rms,
                        )
                    continue
                if not self._enabled.is_set():
                    consecutive = 0
                    continue
                if rms >= self.threshold_rms:
                    consecutive += 1
                else:
                    consecutive = 0
                if consecutive >= self.trigger_frames:
                    now = time.monotonic()
                    if now - self._last_trigger >= self.cooldown_seconds:
                        self._last_trigger = now
                        consecutive = 0
                        log.info(
                            "energy-wake: keyword detected (rms=%.0f)", rms
                        )
                        if self._on_detect is not None:
                            try:
                                self._on_detect()
                            except Exception as exc:
                                log.exception("energy-wake: callback error: %s", exc)
                    else:
                        consecutive = 0


# ---------------------------------------------------------------------------
# openWakeWord backend (default)
# ---------------------------------------------------------------------------


class OpenWakeWordDetector(WakeWordDetector):
    """openWakeWord-based local wake-word detector.

    Uses ``openwakeword`` (https://github.com/dscripka/openWakeWord) to
    run a fully local keyword-spotting model. No API key is required:
    the package ships several pre-trained models, including
    ``hey_jarvis`` which is the default for JARVIS.

    Mic frames are 16 kHz mono int16; the detector accumulates them
    into the 80 ms / 1280-sample chunks that openWakeWord expects,
    then calls ``Model.predict``. When the score for the configured
    keyword exceeds ``threshold`` (and ``patience`` consecutive
    frames are above threshold), the detection callback fires.
    """

    name = "openwakeword"

    def __init__(
        self,
        model: str = "hey_jarvis",
        threshold: float = 0.5,
        patience_frames: int = 2,  # consecutive OWW chunks above threshold
        cooldown_seconds: float = 1.5,
        sample_rate: int = SAMPLE_RATE,
        frame_size: int = FRAME_SIZE,
        inference_framework: str = "onnx",
    ) -> None:
        self.model = model
        self.threshold = float(threshold)
        self.patience_frames = int(patience_frames)
        self.cooldown_seconds = float(cooldown_seconds)
        self.sample_rate = sample_rate
        self.frame_size = frame_size
        self.inference_framework = inference_framework

        self._stop_event = threading.Event()
        self._enabled = threading.Event()
        self._enabled.set()
        self._thread: Optional[threading.Thread] = None
        self._on_detect: Optional[threading.Callable[[], None]] = None
        self._last_trigger: float = 0.0

        # Lazy: imported in start() so import-time failures don't crash
        # the whole process.
        self._oww_model = None
        # Resolved model label used as the dict key when reading scores.
        self._model_label: str = ""

        # Rolling buffer for accumulating 30 ms frames into 80 ms chunks.
        self._accum: np.ndarray = np.zeros((0,), dtype=np.int16)
        self._consecutive_hits: int = 0
        self._reset_pending = threading.Event()

    # -- public API ----------------------------------------------------------

    def set_callback(self, cb) -> None:
        self._on_detect = cb

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._load_model()
        self._stop_event.clear()
        self._consecutive_hits = 0
        self._accum = np.zeros((0,), dtype=np.int16)
        self._thread = threading.Thread(
            target=self._run, name="wakeword-openwakeword", daemon=True
        )
        self._thread.start()
        log.info(
            "OpenWakeWordDetector started (model=%s threshold=%.2f)",
            self.model,
            self.threshold,
        )

    def stop(self) -> None:
        self._stop_event.set()
        t = self._thread
        if t is not None:
            t.join(timeout=2.0)
            self._thread = None
        log.info("OpenWakeWordDetector stopped")

    def set_enabled(self, enabled: bool) -> None:
        if enabled:
            if not self._enabled.is_set():
                self._reset_pending.set()
            self._enabled.set()
        else:
            self._enabled.clear()
        log.debug("OpenWakeWordDetector enabled=%s", enabled)

    def process(self, block: np.ndarray) -> None:
        """Feed a 16 kHz mono int16 audio block (any length) into the
        detector. Useful for tests and for callers that already have a
        stream open.
        """
        if self._oww_model is None or block is None or block.size == 0:
            return
        if not self._enabled.is_set():
            self._consecutive_hits = 0
            self._accum = np.zeros((0,), dtype=np.int16)
            return

        # Only the capture thread touches model state, avoiding reset/predict races.
        if self._reset_pending.is_set():
            self._reset_pending.clear()
            self._accum = np.zeros((0,), dtype=np.int16)
            self._consecutive_hits = 0
            self._oww_model.reset()

        x = block.reshape(-1).astype(np.int16, copy=False)
        if x.size == 0:
            return

        # Append to accumulator; drain OWW_CHUNK_SAMPLES-sized chunks.
        if self._accum.size:
            self._accum = np.concatenate([self._accum, x])
        else:
            self._accum = x

        triggered = False
        max_score = 0.0
        while self._accum.size >= OWW_CHUNK_SAMPLES:
            chunk = self._accum[:OWW_CHUNK_SAMPLES]
            self._accum = self._accum[OWW_CHUNK_SAMPLES:]
            scores = self._oww_model.predict(chunk)
            score = float(scores.get(self._model_label, 0.0))
            if score > max_score:
                max_score = score
            if score >= self.threshold:
                self._consecutive_hits += 1
                if self._consecutive_hits >= self.patience_frames:
                    triggered = True
            else:
                self._consecutive_hits = 0

        if triggered:
            now = time.monotonic()
            if now - self._last_trigger >= self.cooldown_seconds:
                self._last_trigger = now
                self._consecutive_hits = 0
                log.info(
                    "openwakeword: keyword detected (model=%s score=%.2f)",
                    self._model_label,
                    max_score,
                )
                if self._on_detect is not None:
                    try:
                        self._on_detect()
                    except Exception as exc:
                        log.exception("openwakeword: callback error: %s", exc)

    # -- internals -----------------------------------------------------------

    def _load_model(self) -> None:
        if self._oww_model is not None:
            return
        try:
            from openwakeword.model import Model  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "openwakeword is not installed; "
                "run `pip install openwakeword onnxruntime`"
            ) from exc

        # openwakeword.Model accepts either a name ("hey_jarvis") or a
        # path to a .tflite / .onnx file. If a path was supplied we use
        # the basename (without extension) as the label.
        if _looks_like_path(self.model):
            label = _label_from_path(self.model)
        else:
            label = self.model

        self._oww_model = Model(
            wakeword_models=[self.model],
            inference_framework=self.inference_framework,
        )
        # The runtime may include a version suffix in its prediction key.
        labels = list(self._oww_model.models)
        self._model_label = labels[0] if len(labels) == 1 else label
        log.info(
            "openwakeword: loaded model=%r label=%s",
            self.model,
            self._model_label,
        )

    def _run(self) -> None:
        delay = 1.0
        while not self._stop_event.is_set():
            try:
                with sd.InputStream(samplerate=self.sample_rate, channels=1,
                                    dtype="int16", blocksize=self.frame_size) as stream:
                    self._reset_pending.set()
                    log.info("Wake-word microphone connected")
                    delay = 1.0
                    while not self._stop_event.is_set():
                        block, overflow = stream.read(self.frame_size)
                        if overflow:
                            self._reset_pending.set()
                        if block.size:
                            self.process(block)
            except Exception as exc:
                log.warning("Wake microphone unavailable (%s); retrying in %.0fs", type(exc).__name__, delay)
                self._stop_event.wait(delay)
                delay = min(delay * 2, 15.0)


def _looks_like_path(s: str) -> bool:
    if not s:
        return False
    if "/" in s or "\\" in s:
        return True
    return s.lower().endswith((".tflite", ".onnx"))


def _label_from_path(path: str) -> str:
    import os

    base = os.path.basename(path)
    name, _ = os.path.splitext(base)
    # openWakeWord strips version suffixes like _v0.1; mirror that so
    # the label matches what Model.predict() returns in its dict.
    for suffix in ("_v0.1", "_v1", "_v2"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    return name


# ---------------------------------------------------------------------------
# Optional legacy Porcupine backend (kept behind a guarded import)
# ---------------------------------------------------------------------------


try:  # noqa: SIM105 - optional import
    import pvporcupine  # type: ignore

    _HAS_PORCUPINE = True
except Exception:  # pragma: no cover - import is environment-dependent
    pvporcupine = None  # type: ignore
    _HAS_PORCUPINE = False


class PorcupineWakeWord(WakeWordDetector):
    """Legacy Porcupine backend. Kept for backwards compatibility for
    users who already have a Picovoice access key. Not used in the
    default path — see :func:`build_wake_word`.
    """

    name = "porcupine"

    def __init__(
        self,
        access_key: str,
        keyword_path: str = "",
        sensitivity: float = 0.5,
    ) -> None:
        if not _HAS_PORCUPINE:
            raise RuntimeError(
                "pvporcupine is not installed; install it or switch to "
                "the openWakeWord backend (the default)."
            )
        self.access_key = access_key
        self.keyword_path = keyword_path or ""
        self.sensitivity = sensitivity
        self._handle = None
        self._stop_event = threading.Event()
        self._enabled = threading.Event()
        self._enabled.set()
        self._thread: Optional[threading.Thread] = None
        self._on_detect: Optional[threading.Callable[[], None]] = None

    def set_callback(self, cb) -> None:
        self._on_detect = cb

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        if not _HAS_PORCUPINE:
            raise RuntimeError("pvporcupine is not installed")
        if not self.access_key:
            raise RuntimeError("PORCUPINE_ACCESS_KEY is empty")
        try:
            if self.keyword_path:
                self._handle = pvporcupine.create(
                    access_key=self.access_key,
                    keyword_paths=[self.keyword_path],
                    sensitivities=[self.sensitivity],
                )
            else:
                self._handle = pvporcupine.create(
                    access_key=self.access_key,
                    keywords=["jarvis"],
                    sensitivities=[self.sensitivity],
                )
        except Exception as e:
            log.exception("Porcupine init failed: %s", e)
            raise
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, name="wakeword-porcupine", daemon=True
        )
        self._thread.start()
        log.info("PorcupineWakeWord started")

    def stop(self) -> None:
        self._stop_event.set()
        t = self._thread
        if t is not None:
            t.join(timeout=2.0)
            self._thread = None
        if self._handle is not None:
            try:
                self._handle.delete()
            except Exception:
                pass
            self._handle = None
        log.info("PorcupineWakeWord stopped")

    def set_enabled(self, enabled: bool) -> None:
        if enabled:
            self._enabled.set()
        else:
            self._enabled.clear()
        log.debug("PorcupineWakeWord enabled=%s", enabled)

    def _run(self) -> None:
        assert self._handle is not None
        frame_length = self._handle.frame_length
        try:
            stream = sd.InputStream(
                samplerate=self._handle.sample_rate,
                channels=1,
                dtype="int16",
                blocksize=frame_length,
            )
        except Exception as exc:
            log.exception("porcupine: cannot open mic: %s", exc)
            return
        with stream:
            while not self._stop_event.is_set():
                try:
                    block, _ = stream.read(frame_length)
                except Exception as exc:
                    log.exception("porcupine: read error: %s", exc)
                    break
                if block.size == 0:
                    continue
                if not self._enabled.is_set():
                    continue
                pcm = block.reshape(-1).astype(np.int16)
                try:
                    idx = self._handle.process(pcm)
                except Exception as exc:
                    log.exception("porcupine: process error: %s", exc)
                    continue
                if idx >= 0:
                    log.info("porcupine: keyword detected (idx=%d)", idx)
                    if self._on_detect is not None:
                        try:
                            self._on_detect()
                        except Exception as exc:
                            log.exception("porcupine: callback error: %s", exc)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def _ready_openwakeword(**kwargs):
    detector = OpenWakeWordDetector(**kwargs)
    detector._load_model()
    return detector


def build_wake_word(
    *,
    enabled: bool,
    keyword: str = "jarvis",
    wakeword_backend: str = "openwakeword",
    openwakeword_model: str = "hey_jarvis",
    openwakeword_threshold: float = 0.5,
    porcupine_access_key: str = "",
    porcupine_keyword_path: str = "",
    porcupine_sensitivity: float = 0.5,
) -> Optional[WakeWordDetector]:
    """Return the best available wake-word detector, or None if disabled.

    Priority (with the new defaults):

    1. ``wakeword_backend == "openwakeword"`` (default) — try to load
       the openWakeWord model. If it fails (missing package, model
       not downloadable), fall back to the energy-gate detector.
    2. ``wakeword_backend == "porcupine"`` — only used if a
       Porcupine access key is set; falls back to openWakeWord, then
       energy-gate.
    3. ``wakeword_backend == "energy"`` — use the energy-gate fallback
       directly.

    The function never raises on backend failures: callers always
    get either a working detector or the energy-gate fallback so
    JARVIS remains usable.
    """
    if not enabled:
        return None

    backend = (wakeword_backend or "openwakeword").lower()

    if backend == "openwakeword":
        try:
            return _ready_openwakeword(
                model=openwakeword_model or keyword,
                threshold=openwakeword_threshold,
            )
        except Exception as exc:
            log.warning(
                "openWakeWord unavailable (%s) — using energy-gate fallback",
                exc,
            )
            return EnergyGateWakeWord(keyword=keyword)

    if backend == "porcupine":
        if porcupine_access_key:
            try:
                return PorcupineWakeWord(
                    access_key=porcupine_access_key,
                    keyword_path=porcupine_keyword_path,
                    sensitivity=porcupine_sensitivity,
                )
            except Exception as exc:
                log.warning(
                    "Porcupine unavailable (%s) — trying openWakeWord", exc
                )
                try:
                    return _ready_openwakeword(
                        model=openwakeword_model or keyword,
                        threshold=openwakeword_threshold,
                    )
                except Exception as exc2:
                    log.warning(
                        "openWakeWord also unavailable (%s) — "
                        "using energy-gate fallback",
                        exc2,
                    )
                    return EnergyGateWakeWord(keyword=keyword)
        # No Porcupine key — try openWakeWord as the free default.
        try:
            return _ready_openwakeword(
                model=openwakeword_model or keyword,
                threshold=openwakeword_threshold,
            )
        except Exception as exc:
            log.warning(
                "openWakeWord unavailable (%s) — using energy-gate fallback",
                exc,
            )
            return EnergyGateWakeWord(keyword=keyword)

    if backend == "energy":
        return EnergyGateWakeWord(keyword=keyword)

    # Unknown backend name: try openWakeWord, then energy.
    log.warning("unknown wakeword_backend=%r — trying openWakeWord", backend)
    try:
        return _ready_openwakeword(
            model=openwakeword_model or keyword,
            threshold=openwakeword_threshold,
        )
    except Exception as exc:
        log.warning(
            "openWakeWord unavailable (%s) — using energy-gate fallback",
            exc,
        )
        return EnergyGateWakeWord(keyword=keyword)
