from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    app_name: str = Field(default="Altron")
    app_env: str = Field(default="development")
    debug: bool = Field(default=False)
    database_url: str = Field(default="postgresql+asyncpg://postgres:postgres@localhost:5432/altron")
    redis_url: str = Field(default="redis://localhost:6379/0")
    groq_api_key: str = Field(default="")
    default_model: str = Field(default="llama-3.3-70b-versatile")
    log_level: str = Field(default="INFO")
    llm_provider: str = Field(default="groq")
    temperature: float = Field(default=0.7)
    max_tokens: int = Field(default=512)
    top_p: float = Field(default=1.0)
    streaming: bool = Field(default=True)
    whisper_model: str = Field(default="base")
    whisper_device: str = Field(default="cpu")
    whisper_compute_type: str = Field(default="int8")
    audio_sample_rate: int = Field(default=16000)
    audio_channels: int = Field(default=1)
    edge_tts_voice: str = Field(default="en-US-AriaNeural")
    edge_tts_rate: str = Field(default="0%")
    edge_tts_volume: str = Field(default="0%")
    edge_tts_pitch: str = Field(default="0Hz")
    wake_engine: str = Field(default="openwakeword")
    wake_word: str = Field(default="hey_jarvis")
    wake_model: str = Field(default="hey_jarvis")
    wake_threshold: float = Field(default=0.5)
    wake_timeout: float = Field(default=5.0)
    wake_cooldown: float = Field(default=1.0)
    mic_device: str | None = Field(default=None)

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_settings(self) -> "Settings":
        """Validate environment-specific settings before use."""
        env_name = self.app_env.lower()
        allowed_envs = {"development", "testing", "production"}
        if env_name not in allowed_envs:
            raise ValueError(f"APP_ENV must be one of {sorted(allowed_envs)}")
        if env_name != "development" and not self.groq_api_key:
            raise ValueError("GROQ_API_KEY is required outside development")
        return self

    def is_development(self) -> bool:
        return self.app_env.lower() == "development"

    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached application settings instance."""
    return Settings()


def get_settings_from_env() -> Settings:
    """Compatibility helper for dependency injection."""
    return get_settings()


__all__ = ["Settings", "get_settings", "get_settings_from_env"]
