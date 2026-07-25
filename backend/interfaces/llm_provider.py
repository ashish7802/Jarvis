from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator

from backend.schemas.chat import ProviderResponse, StreamingChunk


class BaseLLMProvider(ABC):
    """Abstract interface for LLM provider implementations."""

    name: str = "base"

    @abstractmethod
    async def complete(self, prompt: str, *, model: str | None = None, **kwargs: Any) -> str:
        """Generate a complete text response for a given prompt."""
        pass

    @abstractmethod
    def stream(self, prompt: str | list[dict[str, str]], *, model: str | None = None, **kwargs: Any) -> AsyncIterator[StreamingChunk]:
        """Stream response tokens standard AsyncIterator."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check availability of the underlying provider API."""
        pass

    @abstractmethod
    async def get_response(self, prompt: str | list[dict[str, str]], *, model: str | None = None, **kwargs: Any) -> ProviderResponse:
        """Fetch structured ProviderResponse containing response content and metadata."""
        pass
