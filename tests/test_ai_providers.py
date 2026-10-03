from __future__ import annotations

import pytest

from app.ai.base import AIProvider, AIProviderError, ChatMessage, build_provider


def test_mock_provider_known_answer():
    p = build_provider("mock")
    assert isinstance(p, AIProvider)
    reply = p.chat([ChatMessage(role="user", content="What is Python?")])
    assert "Python" in reply
    assert "Sir" not in reply


def test_mock_provider_fallback():
    p = build_provider("mock")
    reply = p.chat([ChatMessage(role="user", content="completely random gibberish xyzzy")])
    assert "mock mode" in reply.lower()
    assert "groq api key" in reply.lower()


def test_mock_never_raises():
    p = build_provider("mock")
    # Even empty input should not raise.
    reply = p.chat([])
    assert isinstance(reply, str)


def test_groq_requires_api_key():
    with pytest.raises(AIProviderError):
        build_provider("groq", groq_key="")


def test_groq_key_auto_selects_live_provider(monkeypatch):
    from types import SimpleNamespace
    import app.main as main

    calls = []
    monkeypatch.setattr(main, "build_provider", lambda name, **kwargs: calls.append((name, kwargs)) or "provider")
    settings = SimpleNamespace(
        ai_provider="mock", groq_api_key="gsk-test", ai_model="",
        ai_request_timeout=10, ai_max_attempts=1,
    )
    assert main._build_ai(settings) == "provider"
    assert calls[0][0] == "groq"
    assert calls[0][1]["groq_key"] == "gsk-test"


def test_unknown_provider():
    with pytest.raises(AIProviderError):
        build_provider("nonsense")


def test_groq_provider_preserves_chat_history(monkeypatch):
    from app.ai.groq_provider import GroqProvider

    calls = []

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": " Ready. "}}]}

    class Client:
        def __init__(self, **kwargs):
            self.options = kwargs

        def post(self, url, *, json):
            calls.append((url, json))
            return Response()

        def close(self):
            pass

    monkeypatch.setattr("app.ai.groq_provider.httpx.Client", Client)
    provider = GroqProvider("test-key", model="test-model")
    answer = provider.chat([
        ChatMessage("system", "Be concise."), ChatMessage("user", "Hello"),
        ChatMessage("assistant", "Hi"), ChatMessage("user", "Ready?"),
    ])
    assert answer == "Ready."
    assert calls[0][0] == "https://api.groq.com/openai/v1/chat/completions"
    assert calls[0][1]["model"] == "test-model"
    assert calls[0][1]["messages"] == [
        {"role": "system", "content": "Be concise."},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
        {"role": "user", "content": "Ready?"},
    ]
