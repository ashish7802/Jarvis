from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.config.settings import Settings
from backend.voice.text_to_speech import TextToSpeechService
from backend.voice.voice_cache import VoiceCache
from backend.voice.schemas import SpeechRequest, SpeechResponse, VoiceInfo


class FakeCommunicate:
    def __init__(self, text: str, *, voice: str | None = None, rate: str | None = None, volume: str | None = None, pitch: str | None = None):
        self.text = text
        self.voice = voice
        self.rate = rate
        self.volume = volume
        self.pitch = pitch

    async def stream(self):
        yield b"RIFF"
        yield b"audio"

    async def save(self, file_path):
        with open(file_path, "wb") as handle:
            handle.write(b"RIFFaudio")


class FakeEdgeTTSModule:
    def Communicate(self, text: str, *, voice: str | None = None, rate: str | None = None, volume: str | None = None, pitch: str | None = None):
        return FakeCommunicate(text, voice=voice, rate=rate, volume=volume, pitch=pitch)


@pytest.mark.asyncio
async def test_speech_service_generates_audio_bytes():
    service = TextToSpeechService(edge_tts_module=FakeEdgeTTSModule(), cache=VoiceCache())

    response = await service.speak("hello world", voice="en-US-AriaNeural")

    assert isinstance(response, SpeechResponse)
    assert response.audio_bytes.startswith(b"RIFF")
    assert response.voice == "en-US-AriaNeural"


def test_cache_reuses_audio_bytes():
    service = TextToSpeechService(edge_tts_module=FakeEdgeTTSModule(), cache=VoiceCache())

    first = asyncio_run(service.speak("repeat me", voice="en-US-GuyNeural"))
    second = asyncio_run(service.speak("repeat me", voice="en-US-GuyNeural"))

    assert first.audio_bytes == second.audio_bytes
    assert second.cached is True


def test_speak_endpoint(monkeypatch):
    class FakeService:
        async def speak(self, text: str, **kwargs):
            return SpeechResponse(audio_bytes=b"abc", content_type="audio/wav", voice="en-US-AriaNeural", file_format="wav", cached=False)

    monkeypatch.setattr("backend.api.routes.get_tts_service", lambda: FakeService())
    client = TestClient(app)

    response = client.post("/api/voice/speak", json={"text": "hello", "voice": "en-US-AriaNeural"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["voice"] == "en-US-AriaNeural"


def test_voice_list_endpoint(monkeypatch):
    class FakeService:
        def list_voices(self):
            return [VoiceInfo(name="en-US-AriaNeural", locale="en-US", gender="female")]

    monkeypatch.setattr("backend.api.routes.get_tts_service", lambda: FakeService())
    client = TestClient(app)

    response = client.get("/api/voice/voices")

    assert response.status_code == 200
    payload = response.json()
    assert payload["voices"][0]["name"] == "en-US-AriaNeural"


def test_settings_load_edge_tts_configuration(monkeypatch):
    monkeypatch.setenv("EDGE_TTS_VOICE", "en-US-GuyNeural")
    monkeypatch.setenv("EDGE_TTS_RATE", "+10%")
    monkeypatch.setenv("EDGE_TTS_VOLUME", "+20%")
    monkeypatch.setenv("EDGE_TTS_PITCH", "+2Hz")

    settings = Settings()

    assert settings.edge_tts_voice == "en-US-GuyNeural"
    assert settings.edge_tts_rate == "+10%"
    assert settings.edge_tts_volume == "+20%"
    assert settings.edge_tts_pitch == "+2Hz"


def asyncio_run(coro):
    return asyncio.run(coro)
