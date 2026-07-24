from __future__ import annotations

import asyncio
from typing import Any

from groq import AsyncGroq
from loguru import logger

from backend.config.settings import get_settings
from backend.interfaces.llm_provider import BaseLLMProvider
from backend.schemas.chat import ProviderResponse, StreamingChunk


class GroqProvider(BaseLLMProvider):
    """Groq-backed LLM provider implementation with retries and streaming support."""

    name = "groq"

    def __init__(self, api_key: str | None = None, client: Any | None = None) -> None:
        settings = get_settings()
        self._api_key = api_key or settings.groq_api_key
        self._default_model = settings.default_model
        self._client = client

    async def initialize(self) -> None:
        if not self._api_key:
            raise ValueError("GROQ_API_KEY is not configured")
        if self._client is None:
            self._client = AsyncGroq(api_key=self._api_key, timeout=30.0, max_retries=2)

    async def complete(self, prompt: str, *, model: str | None = None, **kwargs: Any) -> str:
        response = await self.get_response(prompt, model=model, **kwargs)
        return response.content

    def stream(self, prompt: str, *, model: str | None = None, **kwargs: Any) -> Any:
        if self._client is None:
            self._client = None

        request_kwargs = {
            "model": model or self._default_model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
            **kwargs,
        }

        async def _generator() -> Any:
            try:
                response = await self._call_with_retry(request_kwargs)
                if hasattr(response, "__aiter__"):
                    async for chunk in response:
                        if getattr(chunk, "choices", None):
                            delta = getattr(chunk.choices[0].delta, "content", None)
                            if delta:
                                yield StreamingChunk(content=delta)
                elif getattr(response, "choices", None):
                    content = response.choices[0].message.content or ""
                    if content:
                        yield StreamingChunk(content=content)
                else:
                    yield StreamingChunk(content="", done=True)
            except asyncio.TimeoutError:
                logger.warning("Groq streaming timed out")
                yield StreamingChunk(content="", done=True)
            except Exception:
                logger.exception("Groq streaming request failed")
                yield StreamingChunk(content="", done=True)

        return _generator()

    async def health_check(self) -> bool:
        try:
            if self._client is None:
                await self.initialize()
            return self._client is not None
        except Exception:
            logger.warning("Groq provider health check failed")
            return False

    async def get_response(self, prompt: str, *, model: str | None = None, **kwargs: Any) -> ProviderResponse:
        if self._client is None:
            await self.initialize()

        request_kwargs = {
            "model": model or self._default_model,
            "messages": [{"role": "user", "content": prompt}],
            **kwargs,
        }
        response = await self._call_with_retry(request_kwargs)

        if not getattr(response, "choices", None):
            raise ValueError("Groq returned an empty response")

        content = response.choices[0].message.content or ""
        if not content:
            raise ValueError("Groq returned an empty response")

        return ProviderResponse(content=content, model=model or self._default_model, provider=self.name)

    async def _call_with_retry(self, request_kwargs: dict[str, Any]) -> Any:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                return await asyncio.wait_for(self._client.chat.completions.create(**request_kwargs), timeout=20.0)
            except asyncio.TimeoutError as exc:
                last_error = exc
                logger.warning("Groq request timed out, retrying", extra={"attempt": attempt + 1})
            except Exception as exc:
                if isinstance(exc, ValueError):
                    raise
                last_error = exc
                logger.warning("Groq request failed, retrying", extra={"attempt": attempt + 1})
            if attempt < 2:
                await asyncio.sleep(0.2 * (attempt + 1))
        if last_error is not None:
            raise last_error
        raise RuntimeError("Groq request failed")


__all__ = ["GroqProvider"]
