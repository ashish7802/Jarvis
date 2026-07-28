from __future__ import annotations

from typing import Any


class ConversationManager:
    """Manages multi-turn chat history and prompt construction."""

    def __init__(self, max_history: int = 10) -> None:
        self.max_history = max_history
        self._system_prompt: str | None = None
        self._history: list[dict[str, str]] = []

    def set_system_prompt(self, prompt: str) -> None:
        self._system_prompt = prompt

    def add_user_message(self, content: str) -> None:
        self._history.append({"role": "user", "content": content})
        self._trim_history()

    def add_assistant_message(self, content: str) -> None:
        self._history.append({"role": "assistant", "content": content})
        self._trim_history()

    def build_messages(self) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if self._system_prompt:
            messages.append({"role": "system", "content": self._system_prompt})
        messages.extend(self._history)
        return messages

    def clear_history(self) -> None:
        self._history.clear()

    def _trim_history(self) -> None:
        if len(self._history) > self.max_history:
            self._history = self._history[-self.max_history:]
