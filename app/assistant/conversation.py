"""Session-only history, trimmed at complete turn boundaries."""
from dataclasses import dataclass, field
from app.ai.base import ChatMessage


@dataclass
class ConversationContext:
    system_prompt: str
    max_messages: int = 21
    max_characters: int = 24000
    _messages: list[ChatMessage] = field(init=False)

    def __post_init__(self):
        if self.max_messages < 3 or self.max_characters < 1000:
            raise ValueError("Conversation limits are too small")
        self.clear()

    def add_user(self, content):
        self._add(ChatMessage("user", content))

    def add_assistant(self, content):
        self._add(ChatMessage("assistant", content))

    def add_turn(self, user, assistant):
        self.add_user(user)
        self.add_assistant(assistant)

    def _add(self, message):
        self._messages.append(ChatMessage(message.role, message.content[:8000]))
        first = 1 if self.system_prompt else 0
        while (len(self._messages) > self.max_messages or
               sum(len(m.content) for m in self._messages) > self.max_characters):
            next_user = next((i for i in range(first + 1, len(self._messages))
                              if self._messages[i].role == "user"), None)
            if next_user is None:
                break
            del self._messages[first:next_user]

    def clear(self):
        self._messages = [ChatMessage("system", self.system_prompt)] if self.system_prompt else []

    def messages(self):
        return [ChatMessage(m.role, m.content) for m in self._messages]

    def __len__(self):
        return len(self._messages)

    def last_assistant(self):
        return next((m.content for m in reversed(self._messages) if m.role == "assistant"), None)
