"""Real wake/Whisper inference on quiet synthetic speech; never saves mic audio."""
import json
from unittest.mock import patch

import numpy as np

from app.audio.recorder import Recorder, rms_level
from app.config import get_settings
from app.stt.service import STTService
from app.tts.service import TTSService
from app.wakeword.detector import OpenWakeWordDetector
from smoke_pipeline import as_pcm


def main():
    settings = get_settings()
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    tts = TTSService(voice=settings.tts_voice, cache_dir=settings.tts_cache_dir)
    paths, result = [], {"passed": False}
    try:
        question = tts._synthesize_sync("What is Python?")
        assert question, "Test speech unavailable"
        paths.append(question)
        pcm = as_pcm(question)
        loudest = max(rms_level(pcm[i:i+480]) for i in range(0, len(pcm), 480))
        # Every original speech frame stays below the previous 600 RMS gate.
        quiet = (pcm.astype(np.float32) * min(.12, 240 / max(1, loudest))).astype(np.int16)
        result["quiet_speech_peak_frame_rms"] = round(max(rms_level(quiet[i:i+480]) for i in range(0, len(quiet), 480)))
        samples = np.concatenate([np.zeros(8000, dtype=np.int16), quiet, np.zeros(32000, dtype=np.int16)])
        class Input:
            def __init__(self, **kwargs):
                self.offset = 0
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def read(self, count):
                block = samples[self.offset:self.offset+count]
                self.offset += count
                if len(block) < count:
                    block = np.pad(block, (0, count-len(block)))
                return block.reshape(-1, 1), False
        with patch("app.audio.recorder.sd.InputStream", Input):
            recorded = Recorder(max_seconds=10, silence_timeout=1, hearing_profile="soft").record()
        assert recorded is not None, "Quiet question was rejected"
        result["transcript"] = STTService().transcribe(recorded)
        assert "python" in result["transcript"].lower(), "Quiet question was misunderstood"
        print("Quiet question recognized:", result["transcript"], flush=True)

        wake_path = tts._synthesize_sync("Hey Jarvis.")
        assert wake_path, "Wake test speech unavailable"
        paths.append(wake_path)
        wake = OpenWakeWordDetector(threshold=settings.openwakeword_threshold)
        wake.set_hearing_profile("soft")
        wake._load_model()
        fired = []
        wake.set_callback(lambda: fired.append(True))
        wake_pcm = (as_pcm(wake_path).astype(np.float32) * .1).astype(np.int16)
        samples = np.concatenate([np.zeros(32000, dtype=np.int16), wake_pcm, np.zeros(16000, dtype=np.int16)])
        for offset in range(0, len(samples), 480):
            wake.process(samples[offset:offset+480])
        result["wake_at_tenth_amplitude"] = bool(fired)
        assert fired, "Quiet synthesized wake word was missed"
        print("Wake word recognized at one tenth amplitude.", flush=True)
        wake.set_enabled(False)
        wake.set_enabled(True)
        wake._last_trigger = 0
        fired.clear()
        noise = np.random.default_rng(7).normal(0, 100, 16000 * 6).astype(np.int16)
        for offset in range(0, len(noise), 480):
            wake.process(noise[offset:offset+480])
        assert not fired, "Stationary test noise triggered the wake word"
        result["stationary_noise_rejected"] = True
        result["passed"] = True
        print("PASS: quiet recording, Whisper, wake word and stationary noise.", flush=True)
    finally:
        for path in paths:
            path.unlink(missing_ok=True)
        tts.shutdown()
        (settings.logs_dir / "hearing-check.json").write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
