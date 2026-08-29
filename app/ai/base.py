from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal


Role = Literal["system", "user", "assistant"]


@dataclass
class ChatMessage:
    role: Role
    content: str


class AIProvider(ABC):
    """Provider-agnostic chat interface."""

    name: str = "base"

    @abstractmethod
    def chat(self, messages: list[ChatMessage]) -> str:
        """Return the assistant's reply text. Must not raise on transient
        errors — providers should catch and return a friendly string."""


class AIProviderError(RuntimeError):
    """Raised for unrecoverable provider errors during *initialization*."""


def build_provider(name: str, *, openai_key: str = "", gemini_key: str = "", model: str = "") -> AIProvider:
    name = (name or "").strip().lower()
    if name == "openai":
        from app.ai.openai_provider import OpenAIProvider

        if not openai_key:
            raise AIProviderError("OPENAI_API_KEY is required when AI_PROVIDER=openai")
        return OpenAIProvider(api_key=openai_key, model=model or "gpt-4o-mini")
    if name == "gemini":
        from app.ai.gemini_provider import GeminiProvider

        if not gemini_key:
            raise AIProviderError("GEMINI_API_KEY is required when AI_PROVIDER=gemini")
        return GeminiProvider(api_key=gemini_key, model=model or "gemini-1.5-flash")
    if name == "mock":
        from app.ai.mock_provider import MockProvider

        return MockProvider()
    raise AIProviderError(f"Unknown AI_PROVIDER: {name!r}")
