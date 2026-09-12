"""Check real mic access, wake inference, Whisper, Gemini, and speaker playback.

Uses synthesized test speech for repeatable recognition checks. Does not save
microphone recordings. Run with the project's virtual-environment Python.
"""
import math
from pathlib import Path

from app.config import get_settings
from app.ai.base import ChatMessage, build_provider
from app.audio.recorder import Player
from app.stt.service import STTService
from app.tts.service import TTSService
from app.wakeword.detector import OpenWakeWordDetector

import numpy as np
import sounddevice as sd
import soundfile as sf
from scipy.signal import resample_poly


def as_pcm(path):
    data, rate = sf.read(str(path), dtype="float32")
    if data.ndim > 1:
        data = data.mean(axis=1)
    divisor = math.gcd(rate, 16000)
    data = resample_poly(data, 16000 // divisor, rate // divisor)
    return (np.clip(data, -1, 1) * 32767).astype(np.int16)


def main():
    settings = get_settings()
    print("Checking microphone access...", flush=True)
    with sd.InputStream(samplerate=16000, channels=1, dtype="int16") as mic:
        audio, _ = mic.read(1600)
        assert audio.size == 1600, "Microphone returned no audio"
    print("Microphone OK.", flush=True)
    tts = TTSService(voice=settings.tts_voice, cache_dir=settings.tts_cache_dir)
    tts.attach_player(Player())
    paths = []
    try:
        question = tts._synthesize_sync("What is Python?")
        assert question is not None, "Speech synthesis failed"
        paths.append(question)
        text = STTService().transcribe(as_pcm(question))
        assert "python" in text.lower(), f"Unexpected transcription: {text!r}"
        print("Whisper recognized:", text, flush=True)

        wake_audio = tts._synthesize_sync("Hey Jarvis.")
        assert wake_audio is not None, "Wake-word speech synthesis failed"
        paths.append(wake_audio)
        wake = OpenWakeWordDetector(threshold=settings.openwakeword_threshold)
        wake._load_model()
        fired = []
        wake.set_callback(lambda: fired.append(True))
        samples = np.concatenate([np.zeros(32000, dtype=np.int16), as_pcm(wake_audio), np.zeros(16000, dtype=np.int16)])
        for offset in range(0, len(samples), 1280):
            wake.process(samples[offset:offset + 1280])
        assert fired, "Wake model did not detect the synthesized 'hey Jarvis'"
        print("Wake-word detection OK.", flush=True)

        ai = build_provider(settings.ai_provider, gemini_key=settings.gemini_api_key,
                            openai_key=settings.openai_api_key, model=settings.ai_model)
        reply = ai.chat([ChatMessage("system", "Answer in one short sentence."), ChatMessage("user", text)])
        assert reply and "trouble reaching" not in reply, "AI request failed"
        print("AI reply:", reply, flush=True)
        assert tts.speak(reply), "Speaker playback failed"
        print("PASS: microphone, wake word, STT, AI, and speaker playback.", flush=True)
    finally:
        for path in paths:
            Path(path).unlink(missing_ok=True)
        tts.shutdown()


if __name__ == "__main__":
    main()
