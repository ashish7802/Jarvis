"""Speech-to-text using faster-whisper, loaded once and reused."""

from __future__ import annotations

import logging
import tempfile
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

    def __init__(self, model_size: str = "base", device: str = "cpu", compute_type: str = "int8") -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = None
        self._lock = threading.Lock()

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        with self._lock:
            if self._model is not None:
                return
            from faster_whisper import WhisperModel  # type: ignore

            log.info(
                "Loading Whisper model size=%s device=%s compute=%s",
                self.model_size,
                self.device,
                self.compute_type,
            )
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
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

            # Write to a temp WAV so Whisper can read it with its native
            # audio loader. (WhisperModel.transcribe also accepts numpy
            # arrays, but a file path keeps us compatible with the
            # broadest range of faster-whisper versions.)
            with tempfile.NamedTemporaryFile(
                suffix=".wav", delete=False
            ) as tmp:
                tmp_path = Path(tmp.name)
            try:
                import soundfile as sf

                # Ensure float32 contiguous for soundfile.
                if audio.dtype != np.float32:
                    audio_f = audio.astype(np.float32) / 32768.0
                else:
                    audio_f = audio
                sf.write(str(tmp_path), audio_f, sample_rate, subtype="FLOAT")

                log.debug("STT transcribing %d samples", audio.shape[0])
                segments, _info = self._model.transcribe(
                    str(tmp_path),
                    beam_size=1,
                    vad_filter=True,
                    language="en",
                )
                texts = [seg.text.strip() for seg in segments]
                text = " ".join(t for t in texts if t).strip()
                log.info("STT -> %r", text)
                return text
            finally:
                try:
                    tmp_path.unlink(missing_ok=True)
                except Exception:
                    pass
        except Exception as exc:
            log.exception("STT failed: %s", exc)
            return ""

    def shutdown(self) -> None:
        # WhisperModel has no explicit close in faster-whisper 1.x; drop ref.
        self._model = None
