from __future__ import annotations

from typing import Any

from backend.interfaces.llm_provider import BaseLLMProvider
from backend.llm.factory import LLMProviderFactory
from backend.schemas.chat import ProviderResponse, StreamingChunk


class LLMService:
    """Application-facing service for interacting with the configured LLM provider."""

    def __init__(self, provider: BaseLLMProvider | None = None) -> None:
        self._provider = provider or LLMProviderFactory().create()

    async def generate_completion(self, prompt: str, *, model: str | None = None, **kwargs: Any) -> str:
        return await self._provider.complete(prompt, model=model, **kwargs)

    async def get_provider_response(self, prompt: str, *, model: str | None = None, **kwargs: Any) -> ProviderResponse:
        return await self._provider.get_response(prompt, model=model, **kwargs)

    async def stream_tokens(self, prompt: str | list[dict[str, str]], *, model: str | None = None, **kwargs: Any):
        async for chunk in self._provider.stream(prompt, model=model, **kwargs):
            yield chunk

    async def health_check(self) -> bool:
        return await self._provider.health_check()


__all__ = ["LLMService"]
