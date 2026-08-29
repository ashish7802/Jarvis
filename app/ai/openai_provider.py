from __future__ import annotations

import logging
from typing import Any

from app.ai.base import AIProvider, ChatMessage

log = logging.getLogger("jarvis.ai.openai")


def _to_openai(messages: list[ChatMessage]) -> list[dict[str, str]]:
    return [{"role": m.role, "content": m.content} for m in messages]


class OpenAIProvider(AIProvider):
    name = "openai"

    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "openai package not installed. `pip install openai` to use OpenAIProvider."
            ) from e
        self._client = OpenAI(api_key=api_key)
        self._model = model
        log.info("OpenAIProvider initialised (model=%s)", self._model)

    def chat(self, messages: list[ChatMessage]) -> str:
        try:
            resp: Any = self._client.chat.completions.create(
                model=self._model,
                messages=_to_openai(messages),
                temperature=0.7,
            )
            choice = resp.choices[0]
            return (choice.message.content or "").strip()
        except Exception as exc:
            log.exception("OpenAI chat failed: %s", exc)
            return (
                "I'm sorry, Sir. I'm having trouble reaching my language model. "
                "Please try again in a moment."
            )
