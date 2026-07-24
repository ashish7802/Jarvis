from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from backend.schemas.chat import ProviderResponse, StreamingChunk


class BaseLLMProvider(ABC):
    """Contract for all LLM providers."""

    name: str = ""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize provider-specific resources."""

    @abstractmethod
    async def complete(self, prompt: str, *, model: str | None = None, **kwargs: Any) -> str:
        """Generate a completion for the provided prompt."""

    @abstractmethod
    def stream(self, prompt: str, *, model: str | None = None, **kwargs: Any) -> Any:
        """Stream completion chunks for the provided prompt."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Return whether the provider is healthy."""

    @abstractmethod
    async def get_response(self, prompt: str, *, model: str | None = None, **kwargs: Any) -> ProviderResponse:
        """Return a structured provider response."""


__all__ = ["BaseLLMProvider"]
