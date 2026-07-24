from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(slots=True)
class WakeEvent:
    """Represents a wake word detection event."""

    timestamp: datetime
    confidence: float
    wake_word: str
    engine: str
    device: str | None = None
