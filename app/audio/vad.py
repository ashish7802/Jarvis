"""Low-cost local voice-activity segmentation for the always-listening path."""
from collections import deque

import numpy as np

from app.audio.hearing import PROFILES, NoiseFloor, boost_pcm


class VoiceActivitySegmenter:
    def __init__(
        self,
        sample_rate: int = 16_000,
        block_ms: int = 30,
        silence_seconds: float = 0.65,
        max_seconds: float = 12.0,
    ) -> None:
        self.sample_rate = sample_rate
        self.block_ms = block_ms
        self.silence_samples = int(sample_rate * silence_seconds)
        self.max_samples = int(sample_rate * max_seconds)
        self._noise = NoiseFloor()
        self._preroll = deque(maxlen=max(1, round(300 / block_ms)))
        self._frames: list[np.ndarray] = []
        self._active = False
        self._consecutive = 0
        self._voiced_frames = 0
        self._silent_samples = 0
        self._total_samples = 0

    def reset(self) -> None:
        self._preroll.clear()
        self._frames.clear()
        self._active = False
        self._consecutive = 0
        self._voiced_frames = 0
        self._silent_samples = 0
        self._total_samples = 0
        self._noise = NoiseFloor()

    def feed(self, block: np.ndarray, profile: str = "soft") -> np.ndarray | None:
        if block is None or not block.size:
            return None
        profile_settings = PROFILES.get(profile, PROFILES["soft"])
        frame = block.reshape(-1).astype(np.int16, copy=True)
        level = float(np.sqrt(np.mean(frame.astype(np.float32) ** 2)))
        floor = self._noise.value
        threshold = max(profile_settings.minimum_rms, (floor or 0.0) * profile_settings.noise_ratio)
        above = floor is not None and level >= threshold

        if self._active:
            self._frames.append(frame)
            self._total_samples += frame.size
        else:
            self._preroll.append(frame)
        self._consecutive = self._consecutive + 1 if above else 0

        if not self._active and self._consecutive >= 3:
            self._active = True
            self._frames = list(self._preroll)
            self._total_samples = sum(part.size for part in self._frames)
            self._voiced_frames = self._consecutive
            self._silent_samples = 0
        elif self._active and above:
            self._voiced_frames += 1

        if self._active:
            self._silent_samples = 0 if above else self._silent_samples + frame.size
            if self._silent_samples >= self.silence_samples or self._total_samples >= self.max_samples:
                audio = np.concatenate(self._frames) if self._frames else np.empty(0, dtype=np.int16)
                voiced_frames = self._voiced_frames
                self._finish_segment()
                if voiced_frames < 5 or audio.size == 0:
                    return None
                return boost_pcm(audio, profile_settings.max_gain)
        elif not above:
            self._noise.update(level)

        return None

    def _finish_segment(self) -> None:
        self._preroll.clear()
        self._frames = []
        self._active = False
        self._consecutive = 0
        self._voiced_frames = 0
        self._silent_samples = 0
        self._total_samples = 0
