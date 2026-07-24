from __future__ import annotations

from backend.schemas.chat import ConfidenceResult, IntentResult


class ConfidenceEngine:
    """Assess confidence in the inferred intent and downstream response."""

    async def evaluate(self, message: str, intent: IntentResult) -> ConfidenceResult:
        normalized = (message or "").strip()
        score = intent.confidence
        reason = intent.reason
        uncertainty = False

        if len(normalized.split()) < 3:
            score = max(0.1, score - 0.2)
            uncertainty = True
            reason = "The input is too short to be confident."
        elif intent.intent in {"command", "conversation"}:
            score = max(0.3, score - 0.1)
            uncertainty = True
            reason = "The intent is broad and may need clarification."

        return ConfidenceResult(score=round(score, 2), reason=reason, uncertainty=uncertainty)
