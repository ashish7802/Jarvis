from __future__ import annotations

import logging
from typing import Iterable

from app.ai.base import AIProvider, ChatMessage

log = logging.getLogger("jarvis.ai.mock")


_MOCK_REPLIES: dict[str, str] = {
    "hello": "Hello, Sir. JARVIS at your service.",
    "hi": "Hello, Sir. JARVIS at your service.",
    "what time is it": "I'm afraid I don't have access to the system clock, Sir. The mock provider keeps things simple.",
    "what is python": "Python is a high-level, interpreted programming language known for its clear syntax and broad ecosystem, Sir.",
    "what can you do": (
        "I can hold a conversation, answer questions, and demonstrate the JARVIS pipeline, Sir. "
        "Beyond that, I do not currently control the computer."
    ),
}


_FALLBACK = (
    "I am operating in mock mode, Sir. I can demonstrate the pipeline, "
    "but I do not have access to a real language model. Set AI_PROVIDER to "
    "openai or gemini and provide an API key for live answers."
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
