from types import SimpleNamespace

import pytest

from backend.llm.providers.groq.provider import GroqProvider


class DummyResponse:
    def __init__(self, text: str = "stub") -> None:
        self.choices = [SimpleNamespace(message=SimpleNamespace(content=text))]


class DummyClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):
        self.calls.append(kwargs)
        return DummyResponse("stub")


@pytest.mark.asyncio
async def test_complete_returns_provider_output() -> None:
    client = DummyClient()
    provider = GroqProvider(api_key="test-key", client=client)

    result = await provider.complete("Hello", model="test-model")

    assert result == "stub"
    assert client.calls[0]["model"] == "test-model"


@pytest.mark.asyncio
async def test_stream_emits_chunks() -> None:
    client = DummyClient()
    provider = GroqProvider(api_key="test-key", client=client)

    chunks = [chunk async for chunk in provider.stream("Hello", model="test-model")]

    assert len(chunks) >= 1
    assert chunks[0].content
