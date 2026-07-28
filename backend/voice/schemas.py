from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class SpeechRequest(BaseModel):
    text: str = Field(..., description="Text to convert to speech")
    voice: str | None = Field(default=None, description="Optional voice model/name")


class SpeechResponse(BaseModel):
    success: bool = True
    message: str = ""
    audio_base64: str | None = None
    duration: float = 0.0


class TranscriptionRequest(BaseModel):
    audio_base64: str | None = None
    language: str | None = None


class TranscriptionResponse(BaseModel):
    text: str = ""
    confidence: float = 1.0
    language: str = "en"
    duration: float = 0.0
    processing_time: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class VoiceInfo(BaseModel):
    name: str
    gender: str | None = None
    language: str = "en"


class WakeRequest(BaseModel):
    engine: str | None = "openwakeword"
    model: str | None = "hey_jarvis"
    threshold: float | None = 0.5


class WakeResponse(BaseModel):
    success: bool
    message: str
    status: str
    event: dict[str, Any] | None = None


class WakeStatus(BaseModel):
    state: str = "stopped"
    engine: str = "openwakeword"
    model: str = "hey_jarvis"
    threshold: float = 0.5
