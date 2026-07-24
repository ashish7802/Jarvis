from __future__ import annotations

from pydantic import BaseModel, Field


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
    event: dict | None = None


class WakeStatus(BaseModel):
    running: bool
    paused: bool
    engine: str
    wake_word: str
    threshold: float
    timeout: float
    cooldown: float
    device: str | None = None
    last_event: dict | None = None


class WakeEventModel(BaseModel):
    timestamp: str
    confidence: float
    wake_word: str
    engine: str
    device: str | None = None
