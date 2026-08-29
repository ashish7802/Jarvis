"""Live smoke test of the JARVIS pipeline against real hardware.

Runs without wake word:
  1. Speak a startup greeting via real edge-tts + speaker.
  2. Wait for a short recording (mic).
  3. Transcribe it with real faster-whisper.
  4. Get a mock AI reply.
  5. Speak the reply.

This proves that the full pipeline works on this machine.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Allow running as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402

from app.ai.mock_provider import MockProvider  # noqa: E402
from app.audio.recorder import Player, Recorder  # noqa: E402
from app.stt.service import STTService  # noqa: E402
from app.tts.service import TTSService  # noqa: E402


def main() -> int:
    print("[smoke] initialising services...")
    player = Player()
    tts = TTSService(voice="en-US-GuyNeural", cache_dir=Path("tts_cache"))
    tts.attach_player(player)
    stt = STTService(model_size="base", device="cpu", compute_type="int8")
    ai = MockProvider()
    rec = Recorder(max_seconds=6.0, silence_timeout=1.2, silence_threshold_rms=600.0)

    print("[smoke] speaking greeting...")
    tts.speak("Good morning, Sir. JARVIS at your service.")
    print("[smoke] greeting done")

    print("[smoke] say something (up to 6s, or stay silent to time out)...")
    audio = rec.record()
    if audio is None:
        print("[smoke] no speech captured — that is fine for the smoke test.")
        return 0
    print(f"[smoke] captured {audio.shape[0]} samples ({audio.shape[0]/16000:.2f}s)")

    text = stt.transcribe(audio, sample_rate=16000)
    print(f"[smoke] STT -> {text!r}")
    if not text:
        print("[smoke] STT returned nothing — try again louder.")
        return 0

    reply = ai.chat([
        type("M", (), {"role": "user", "content": text})(),  # type: ignore
    ])
    print(f"[smoke] AI  -> {reply!r}")

    print("[smoke] speaking reply...")
    tts.speak(reply)
    print("[smoke] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
