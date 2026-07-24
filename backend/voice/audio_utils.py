from __future__ import annotations

import io
import wave
from pathlib import Path

from backend.voice.exceptions import AudioFormatError

try:
    import numpy as np
except Exception:  # pragma: no cover - optional dependency
    np = None


def ensure_wav_bytes(audio_bytes: bytes) -> bytes:
    """Convert raw PCM bytes into a WAV container when possible."""
    if not audio_bytes:
        raise AudioFormatError("Audio payload is empty")

    try:
        with wave.open(io.BytesIO(audio_bytes), "rb") as wav_file:
            return audio_bytes
    except (wave.Error, EOFError):
        pass

    if np is None:
        return audio_bytes

    pcm = np.frombuffer(audio_bytes, dtype=np.int16)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(16000)
        wav_file.writeframes(pcm.tobytes())
    return buffer.getvalue()


def read_audio_file(audio_path: str | Path) -> bytes:
    path = Path(audio_path)
    if not path.exists():
        raise AudioFormatError(f"Audio file not found: {path}")
    return path.read_bytes()
