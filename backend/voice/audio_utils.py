from __future__ import annotations

import os


def ensure_wav_bytes(audio_bytes: bytes) -> bytes:
    """Ensure audio bytes are returned as valid audio payload."""
    if not audio_bytes:
        return b""
    return audio_bytes


def read_audio_file(audio_path: str) -> bytes:
    """Read binary contents of an audio file path."""
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    with open(audio_path, "rb") as f:
        return f.read()
