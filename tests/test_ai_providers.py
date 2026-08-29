from __future__ import annotations

import pytest

from app.ai.base import AIProvider, AIProviderError, ChatMessage, build_provider


def test_mock_provider_known_answer():
    p = build_provider("mock")
    assert isinstance(p, AIProvider)
    reply = p.chat([ChatMessage(role="user", content="What is Python?")])
    assert "Python" in reply


def test_mock_provider_fallback():
    p = build_provider("mock")
    reply = p.chat([ChatMessage(role="user", content="completely random gibberish xyzzy")])
    assert "mock mode" in reply.lower()


def test_mock_never_raises():
    p = build_provider("mock")
    # Even empty input should not raise.
    reply = p.chat([])
    assert isinstance(reply, str)


def test_missing_openai_key():
    with pytest.raises(AIProviderError):
        build_provider("openai", openai_key="")


def test_missing_gemini_key():
    with pytest.raises(AIProviderError):
        build_provider("gemini", gemini_key="")


def test_unknown_provider():
    with pytest.raises(AIProviderError):
        build_provider("nonsense")
