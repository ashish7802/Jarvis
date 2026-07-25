from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., description="User message input")
    session_id: str | None = None
    stream: bool = False


class ChatResponse(BaseModel):
    response: str
    session_id: str | None = None
    confidence: float = 1.0
    intent: str | None = None


class ConfidenceResult(BaseModel):
    score: float = 1.0
    reason: str | None = None
    needs_clarification: bool = False
    uncertainty: bool = False


class IntentResult(BaseModel):
    intent: str = "general"
    confidence: float = 1.0
    entities: dict[str, Any] = Field(default_factory=dict)


class StreamingChunk(BaseModel):
    content: str = ""
    finish_reason: str | None = None
    done: bool = False


class ProviderResponse(BaseModel):
    content: str
    model: str | None = None
    provider: str = "groq"
