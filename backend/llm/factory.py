from __future__ import annotations

from typing import Any

from backend.interfaces.llm_provider import BaseLLMProvider
from backend.llm.providers.groq.provider import GroqProvider


class LLMProviderFactory:
    """Factory for instantiating LLM providers."""

    def create(self, provider_name: str = "groq", **kwargs: Any) -> BaseLLMProvider:
        if provider_name.lower() == "groq":
            return GroqProvider(**kwargs)
        raise ValueError(f"Unsupported LLM provider: {provider_name}")
