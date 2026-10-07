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
        """Return reply text, or raise AIProviderError with a speakable error."""

    def cancel(self) -> None:
        """Cancel pending retries during shutdown, when supported."""

    def shutdown(self) -> None:
        """Release provider resources, when supported."""


class AIProviderError(RuntimeError):
    """Raised for unrecoverable provider errors during *initialization*."""


def build_provider(name: str, *, groq_key: str = "", model: str = "", request_timeout: float = 15.0, max_attempts: int = 2, max_tokens: int = 350) -> AIProvider:
    name = (name or "").strip().lower()
    if name == "groq":
        from app.ai.groq_provider import GroqProvider

        if not groq_key:
            raise AIProviderError("GROQ_API_KEY is required when AI_PROVIDER=groq")
        return GroqProvider(api_key=groq_key, model=model or "llama-3.3-70b-versatile",
                            request_timeout=request_timeout, max_attempts=max_attempts, max_tokens=max_tokens)
    if name == "mock":
        from app.ai.mock_provider import MockProvider

        return MockProvider()
    raise AIProviderError(f"Unknown AI_PROVIDER: {name!r}")
