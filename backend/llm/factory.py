from __future__ import annotations

from backend.config.settings import get_settings
from backend.interfaces.llm_provider import BaseLLMProvider
from backend.llm.providers.groq.provider import GroqProvider


class LLMProviderFactory:
    """Factory for constructing providers based on configuration."""

    def __init__(self, provider_name: str | None = None) -> None:
        settings = get_settings()
        self._provider_name = provider_name or settings.llm_provider or "groq"

    def create(self) -> BaseLLMProvider:
        if self._provider_name == "groq":
            return GroqProvider()
        raise ValueError(f"Unsupported provider: {self._provider_name}")


__all__ = ["LLMProviderFactory"]
