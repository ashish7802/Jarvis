from __future__ import annotations

from typing import Any


class ConversationManager:
    """Manage conversation state for prompt construction and history trimming."""

    def __init__(self, max_history: int = 10, system_prompt: str | None = None) -> None:
        self.max_history = max_history
        self.system_prompt = system_prompt or "You are a helpful AI assistant."
        self._history: list[dict[str, str]] = []
        self.assistant_replies: list[str] = []
        self.user_messages: list[str] = []

    def add_user_message(self, message: str) -> None:
        self.user_messages.append(message)
        self._history.append({"role": "user", "content": message})
        self._trim_history()

    def add_assistant_message(self, message: str) -> None:
        self.assistant_replies.append(message)
        self._history.append({"role": "assistant", "content": message})
        self._trim_history()

    def set_system_prompt(self, prompt: str) -> None:
        self.system_prompt = prompt

    def get_history(self) -> list[dict[str, str]]:
        return list(self._history[-self.max_history :])

    def build_messages(self) -> list[dict[str, str]]:
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(self.get_history())
        return messages

    def _trim_history(self) -> None:
        if len(self._history) > self.max_history:
            self._history = self._history[-self.max_history :]

    def to_dict(self) -> dict[str, Any]:
        return {
            "system_prompt": self.system_prompt,
            "history": self.get_history(),
            "assistant_replies": self.assistant_replies,
            "user_messages": self.user_messages,
        }
