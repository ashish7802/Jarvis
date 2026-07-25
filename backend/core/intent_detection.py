from __future__ import annotations

from typing import Any
from backend.schemas.chat import IntentResult


class IntentDetector:
    """Classifies user intent from natural language input."""

    async def detect(self, text: str) -> IntentResult:
        lowered = text.lower()
        if any(word in lowered for word in ["hello", "hi", "hey"]):
            return IntentResult(intent="greeting", confidence=0.95)
        if any(word in lowered for word in ["time", "date"]):
            return IntentResult(intent="query_time", confidence=0.90)
        return IntentResult(intent="general_chat", confidence=0.85)
