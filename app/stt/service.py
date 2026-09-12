"""Speech-to-text using faster-whisper, loaded once and reused."""

from __future__ import annotations

import logging
import math
import threading
from pathlib import Path
from typing import Optional

import numpy as np

log = logging.getLogger("jarvis.stt")


class STTService:
    """Wrapper around faster-whisper with lazy model loading.

    The model is loaded once on first use and held in memory. Reusing
    the same instance across many requests is the whole point.
    """

    def __init__(self, model_size: str = "base", device: str = "cpu", compute_type: str = "int8", language: str = "auto", beam_size: int = 3) -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = None if language in ("auto", "") else language
        self.beam_size = beam_size
        self._model = None
        self._lock = threading.Lock()

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        with self._lock:
            if self._model is not None:
                return
            from faster_whisper import WhisperModel  # type: ignore
            from faster_whisper.utils import download_model
            from huggingface_hub.errors import LocalEntryNotFoundError

            cache_dir = str(Path(__file__).resolve().parents[2] / ".cache" / "whisper")
            model_source = self.model_size
            if not Path(model_source).is_dir():
                try:
                    model_source = download_model(
                        self.model_size, cache_dir=cache_dir, local_files_only=True
                    )
                except LocalEntryNotFoundError:
                    pass  # First run downloads the model below.

            log.info(
                "Loading Whisper model size=%s device=%s compute=%s",
                self.model_size,
                self.device,
                self.compute_type,
            )
            self._model = WhisperModel(
                model_source,
                device=self.device,
                compute_type=self.compute_type,
                download_root=cache_dir,
            )
            if self.language and self.language not in self._model.supported_languages:
                self._model = None
                raise ValueError(f"Unsupported STT_LANGUAGE: {self.language}")
            log.info("Whisper model loaded")

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16_000) -> str:
        """Transcribe a numpy int16 mono array. Returns the recognized text
        (stripped) or "" if nothing was recognized.

        Never raises — all exceptions are caught and logged.
        """
        if audio is None or audio.size == 0:
            return ""
        try:
            self._ensure_model()
            assert self._model is not None

            if not isinstance(sample_rate, int) or sample_rate <= 0:
                raise ValueError("sample_rate must be a positive integer")
            audio_f = audio.astype(np.float32)
            if np.issubdtype(audio.dtype, np.signedinteger):
                audio_f /= float(-np.iinfo(audio.dtype).min)
            elif not np.issubdtype(audio.dtype, np.floating):
                raise ValueError("Audio must contain signed PCM or normalized floats")
            if audio_f.ndim == 2:
                audio_f = audio_f.mean(axis=1)
            if audio_f.ndim != 1 or not np.isfinite(audio_f).all():
                raise ValueError("Invalid audio shape or sample values")
            if not np.any(audio_f):
                return ""
            if sample_rate != 16000:
                from scipy.signal import resample_poly
                divisor = math.gcd(sample_rate, 16000)
                audio_f = resample_poly(audio_f, 16000 // divisor, sample_rate // divisor)
            audio_f = np.ascontiguousarray(np.clip(audio_f, -1, 1), dtype=np.float32)
            # faster-whisper accepts 16 kHz floats directly; no microphone WAV
            # is written to disk, and float64 input keeps its original volume.
            segments, _info = self._model.transcribe(
                audio_f, beam_size=self.beam_size, vad_filter=True,
                language=self.language, condition_on_previous_text=False,
            )
            text = " ".join(seg.text.strip() for seg in segments if seg.text.strip())
            log.debug("STT -> %r", text)
            return text
        except Exception as exc:
            log.exception("STT failed: %s", exc)
            return ""

    def shutdown(self) -> None:
        # WhisperModel has no explicit close in faster-whisper 1.x; drop ref.
        self._model = None
