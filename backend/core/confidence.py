from __future__ import annotations

from typing import Any
from backend.schemas.chat import ConfidenceResult, IntentResult


class ConfidenceEngine:
    """Evaluates response confidence scores and clarification flags."""

    async def evaluate(self, text: str, intent: IntentResult | None = None) -> ConfidenceResult:
        if not text or len(text.strip()) == 0:
            return ConfidenceResult(score=0.0, reason="Empty text input", needs_clarification=True, uncertainty=True)
        return ConfidenceResult(score=1.0, reason="High confidence", needs_clarification=False, uncertainty=False)
