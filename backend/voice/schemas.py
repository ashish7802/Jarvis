from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AudioMetadata(BaseModel):
    sample_rate: int = Field(default=16000)
    channels: int = Field(default=1)
    chunk_size: int = Field(default=1024)
    record_duration: float = Field(default=5.0)
    device: str | None = None


class TranscriptionRequest(BaseModel):
    audio_bytes: str | None = None
    audio_path: str | None = None
    language: str | None = None
    model: str | None = None
    device: str | None = None
    metadata: AudioMetadata | None = None


class TranscriptionResponse(BaseModel):
    text: str
    language: str | None = None
    confidence: float | None = None
    processing_time: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SpeechRequest(BaseModel):
    text: str
    voice: str | None = None
    rate: str | None = None
    volume: str | None = None
    pitch: str | None = None
    file_format: str = Field(default="wav")
    output_path: str | None = None


class SpeechResponse(BaseModel):
    audio_bytes: bytes
    content_type: str
    voice: str
    file_format: str
    cached: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class VoiceInfo(BaseModel):
    name: str
    locale: str | None = None
    gender: str | None = None
    short_name: str | None = None


class WakeRequest(BaseModel):
    wake_word: str | None = None
    engine: str | None = None
    threshold: float | None = None
    timeout: float | None = None
    cooldown: float | None = None
    device: str | None = None


class WakeResponse(BaseModel):
    success: bool
    message: str
    status: str
    event: dict[str, Any] | None = None


class WakeStatus(BaseModel):
    running: bool
    paused: bool
    engine: str
    wake_word: str
    threshold: float
    timeout: float
    cooldown: float
    device: str | None = None
    last_event: dict[str, Any] | None = None


class WakeEventModel(BaseModel):
    timestamp: str
    confidence: float
    wake_word: str
    engine: str
    device: str | None = None
