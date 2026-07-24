from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    stream: bool = False
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None


class IntentResult(BaseModel):
    intent: Literal[
        "question",
        "conversation",
        "command",
        "research",
        "coding",
        "automation",
        "summarization",
        "planning",
        "analysis",
    ]
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str


class ConfidenceResult(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    reason: str
    uncertainty: bool = False


class ProviderResponse(BaseModel):
    content: str
    model: str | None = None
    provider: str = "groq"
    metadata: dict[str, Any] = Field(default_factory=dict)


class StreamingChunk(BaseModel):
    content: str
    done: bool = False
    provider: str = "groq"


class ChatResponse(BaseModel):
    content: str
    intent: IntentResult
    confidence: ConfidenceResult
    provider: str = "groq"
    model: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
