"""Small, bounded audio adjustments; no cloud audio or extra model required."""
from collections import deque
from dataclasses import dataclass
import math

import numpy as np


@dataclass(frozen=True)
class HearingProfile:
    label: str
    minimum_rms: float
    noise_ratio: float
    max_gain: float
    wake_gain: float


PROFILES = {
    "soft": HearingProfile("Soft voice", 80, 1.8, 6, 2.5),
    "balanced": HearingProfile("Balanced", 150, 2.4, 4, 1.5),
    "noisy": HearingProfile("Noisy room", 350, 3.2, 2, 1),
}


class NoiseFloor:
    """Lower rolling percentile resists brief speech and isolated bumps."""
    def __init__(self):
        self.levels = deque(maxlen=100)

    def update(self, level):
        self.levels.append(float(level))

    @property
    def value(self):
        if len(self.levels) < 6:
            return None
        return float(np.percentile(list(self.levels), 20))


def boost_pcm(audio, max_gain, target_rms=1800):
    """Lift quiet confirmed recordings, bounded by gain and peak headroom."""
    x = audio.astype(np.float32)
    if not x.size:
        return audio
    level = float(np.sqrt(np.mean(x * x)))
    peak = float(np.max(np.abs(x)))
    if level < 1 or peak < 1:
        return audio
    gain = max(1.0, min(max_gain, target_rms / level, 30000 / peak))
    return np.clip(x * gain, -32768, 32767).astype(np.int16)


def meter_value(level):
    """Logarithmic input meter: quiet speech is visible, zero stays zero."""
    if level < 1:
        return 0
    return round(max(0, min(100, (20 * math.log10(level / 32768) + 72) / 72 * 100)))
