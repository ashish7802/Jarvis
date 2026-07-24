from __future__ import annotations

from backend.schemas.chat import IntentResult


class IntentDetector:
    """Determine the likely intent of a user message."""

    async def detect(self, message: str) -> IntentResult:
        normalized = (message or "").strip().lower()

        if not normalized:
            return IntentResult(intent="conversation", confidence=0.2, reason="Empty input provided")

        if normalized.endswith("?") or any(keyword in normalized for keyword in ["what", "why", "how", "when", "where", "who", "can you", "tell me"]):
            intent = "question"
            confidence = 0.9
            reason = "The message appears to request information."
        elif any(keyword in normalized for keyword in ["summarize", "summary", "tl;dr"]):
            intent = "summarization"
            confidence = 0.9
            reason = "The message asks for summarization."
        elif any(keyword in normalized for keyword in ["code", "implement", "function", "class", "debug", "test", "script"]):
            intent = "coding"
            confidence = 0.9
            reason = "The message appears related to software development."
        elif any(keyword in normalized for keyword in ["plan", "strategy", "roadmap", "steps", "timeline"]):
            intent = "planning"
            confidence = 0.88
            reason = "The message requests planning or a sequence of actions."
        elif any(keyword in normalized for keyword in ["research", "look up", "find information", "investigate"]):
            intent = "research"
            confidence = 0.86
            reason = "The message asks for research or information gathering."
        elif any(keyword in normalized for keyword in ["analyze", "compare", "evaluate", "inspect"]):
            intent = "analysis"
            confidence = 0.84
            reason = "The message asks for synthesis or analysis."
        elif any(keyword in normalized for keyword in ["automation", "automate", "run", "schedule", "workflow"]):
            intent = "automation"
            confidence = 0.82
            reason = "The message mentions automation or task execution."
        elif any(keyword in normalized for keyword in ["hi", "hello", "hello there", "talk", "conversation", "chat"]):
            intent = "conversation"
            confidence = 0.8
            reason = "The message appears conversational."
        else:
            intent = "command"
            confidence = 0.55
            reason = "The intent is not strongly expressed."

        return IntentResult(intent=intent, confidence=confidence, reason=reason)
