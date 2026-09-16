from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def _user_data_dir() -> Path:
    """Per-user writable directory used when running as a frozen EXE."""
    base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "JARVIS"


def _default_logs_dir() -> Path:
    if _is_frozen():
        d = _user_data_dir() / "logs"
    else:
        d = PROJECT_ROOT / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _default_tts_cache_dir() -> Path:
    if _is_frozen():
        d = _user_data_dir() / "tts_cache"
    else:
        d = PROJECT_ROOT / "tts_cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _resolve_env_file() -> str | None:
    """Return the path to the .env file to load, honouring
    JARVIS_ENV_FILE for tests / packaging, defaulting to the project
    root .env if it exists."""
    custom = os.environ.get("JARVIS_ENV_FILE")
    if custom:
        return custom
    root = Path(sys.executable).resolve().parent if _is_frozen() else PROJECT_ROOT
    candidate = root / ".env"
    return str(candidate) if candidate.exists() else None


class Settings(BaseSettings):
    """Application settings loaded from environment / .env."""

    # env_file is set dynamically per-instance (see ``_build``) so
    # tests can swap the env file via $JARVIS_ENV_FILE.
    model_config = SettingsConfigDict(
        env_file=None,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # General
    jarvis_name: str = "Jarvis"

    # Startup
    startup_greeting_enabled: bool = True
    startup_greeting_delay: float = 5.0
    startup_greeting: str = "Good morning, Sir."

    # Wake word
    wake_word_enabled: bool = True
    wake_word: str = "jarvis"
    # Backend selection. "openwakeword" is the default and runs fully
    # locally with no API key. "energy" is the simple energy-gate
    # fallback. "porcupine" still works if PORCUPINE_ACCESS_KEY is set.
    wakeword_backend: Literal["openwakeword", "energy", "porcupine"] = "openwakeword"
    # openWakeWord settings
    openwakeword_model: str = "hey_jarvis"
    openwakeword_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    # Legacy Porcupine settings (optional, retained for back-compat
    # with existing .env files; not required for the default path).
    porcupine_access_key: str = ""
    porcupine_keyword_path: str = ""
    porcupine_sensitivity: float = Field(default=0.5, ge=0.0, le=1.0)

    # Listening
    listen_timeout: float = 10.0
    silence_timeout: float = 1.5
    hearing_profile: Literal["soft", "balanced", "noisy"] = "soft"
    language_mode: Literal["auto", "hi", "hinglish", "en"] = "auto"
    stt_model: str = "base"
    stt_language: str = "auto"
    stt_beam_size: int = Field(default=3, ge=1, le=5)
    user_name: str = ""
    context_messages: int = Field(default=31, ge=3, le=101)
    ai_request_timeout: float = Field(default=15.0, ge=5.0, le=60.0)
    ai_max_attempts: int = Field(default=2, ge=1, le=3)

    # AI
    ai_provider: Literal["openai", "gemini", "mock"] = "mock"
    ai_model: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""

    # TTS
    tts_provider: Literal["edge", "mock"] = "edge"
    tts_voice: str = "en-US-GuyNeural"
    tts_hindi_voice: str = "hi-IN-SwaraNeural"

    # Hotkey
    hotkey_exit: str = "Ctrl+Shift+J"

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    logs_dir: Path = Field(default_factory=_default_logs_dir)
    tts_cache_dir: Path = Field(default_factory=_default_tts_cache_dir)

    @field_validator("startup_greeting_delay")
    @classmethod
    def _delay_non_negative(cls, v: float) -> float:
        if v < 0:
            return 0.0
        return v

    @field_validator("listen_timeout", "silence_timeout")
    @classmethod
    def _timeouts_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("timeouts must be > 0")
        return v


_settings: Settings | None = None


def _build() -> Settings:
    """Build a Settings instance using the current env file."""
    path = _resolve_env_file()
    inst = Settings(_env_file=path)
    inst.logs_dir.mkdir(parents=True, exist_ok=True)
    inst.tts_cache_dir.mkdir(parents=True, exist_ok=True)
    return inst


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = _build()
    return _settings


def reset_settings_cache() -> None:
    """For tests."""
    global _settings
    _settings = None
