from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class WakeEvent:
    """Data object representing a detected wake word event."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    confidence: float = 0.0
    wake_word: str = "hey_jarvis"
    engine: str = "openwakeword"
    device: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)
