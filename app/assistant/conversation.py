"""Short-term in-memory conversation context.

Explicitly out of scope: persistent storage, embeddings, RAG, long-term
memory. We only keep a rolling window of the last N non-system turns.
The system prompt is always pinned at the head of the list.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, List

from app.ai.base import ChatMessage


@dataclass
class ConversationContext:
    system_prompt: str
    max_messages: int = 20
    _messages: List[ChatMessage] = field(init=False)

    def __post_init__(self) -> None:
        self._messages = []
        if self.system_prompt:
            self._messages.append(ChatMessage(role="system", content=self.system_prompt))

    def add_user(self, content: str) -> None:
        self._add(ChatMessage(role="user", content=content))

    def add_assistant(self, content: str) -> None:
        self._add(ChatMessage(role="assistant", content=content))

    def _add(self, msg: ChatMessage) -> None:
        # Cap total size (including system) to max_messages by dropping
        # the oldest non-system message(s) until under the cap.
        self._messages.append(msg)
        while len(self._messages) > self.max_messages:
            # Find the oldest non-system message and drop it.
            drop_idx = -1
            for i, m in enumerate(self._messages):
                if m.role != "system":
                    drop_idx = i
                    break
            if drop_idx == -1:
                break  # only system messages left
            del self._messages[drop_idx]

    def clear(self) -> None:
        self._messages = []
        if self.system_prompt:
            self._messages.append(ChatMessage(role="system", content=self.system_prompt))

    def messages(self) -> List[ChatMessage]:
        return list(self._messages)

    def __len__(self) -> int:
        return len(self._messages)

    def last_assistant(self) -> str | None:
        for m in reversed(self._messages):
            if m.role == "assistant":
                return m.content
        return None
