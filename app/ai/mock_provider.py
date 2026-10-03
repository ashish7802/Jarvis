from __future__ import annotations

import logging
from typing import Iterable

from app.ai.base import AIProvider, ChatMessage

log = logging.getLogger("jarvis.ai.mock")


_MOCK_REPLIES: dict[str, str] = {
    "hello": "Hey! Good to hear from you. What's up?",
    "hi": "Hey! Good to hear from you. What's up?",
    "what time is it": "I can't check the clock in demo mode, but I can still help with a few built-in questions.",
    "what is python": "Python is a popular programming language known for readable code and a huge range of uses.",
    "what can you do": (
        "I can demonstrate the voice pipeline and answer a few built-in questions. "
        "For open-ended conversation, add a Groq API key."
    ),
}


_FALLBACK = (
    "I'm in mock mode right now, so I can only answer a few built-in examples. "
    "To chat about any topic, add a Groq API key."
)


def _match(text: str) -> str | None:
    t = text.strip().lower().rstrip(".?!")
    for key, reply in _MOCK_REPLIES.items():
        if key in t:
            return reply
    return None


class MockProvider(AIProvider):
    name = "mock"

    def chat(self, messages: list[ChatMessage]) -> str:
        try:
            user_msg = next((m.content for m in reversed(messages) if m.role == "user"), "")
            matched = _match(user_msg)
            if matched:
                log.debug("mock reply matched for %r", user_msg[:40])
                return matched
            return _FALLBACK
        except Exception as exc:  # never raise from a provider
            log.exception("mock provider failure: %s", exc)
            return _FALLBACK
