import pytest

from backend.core.intent_detection import IntentDetector


@pytest.mark.asyncio
async def test_detects_question_intent() -> None:
    detector = IntentDetector()

    result = await detector.detect("What is the capital of France?")

    assert result.intent == "question"
    assert result.confidence >= 0.5
