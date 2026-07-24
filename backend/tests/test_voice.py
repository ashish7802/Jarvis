from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.voice.audio_capture import AudioRecorder
from backend.voice.schemas import TranscriptionResponse
from backend.voice.speech_to_text import FasterWhisperTranscriber, TranscriptionService


class DummyStream:
    def __init__(self, frames):
        self.frames = frames
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.closed = True

    def read(self, n_frames):
        return self.frames[:n_frames]


class DummySoundDevice:
    def __init__(self):
        self.started = False

    def query_devices(self):
        return ["default"]

    def InputStream(self, *args, **kwargs):
        self.started = True
        return DummyStream([b"abc", b"def"])


@pytest.mark.asyncio
async def test_audio_recorder_records_audio(monkeypatch):
    dummy_sd = DummySoundDevice()
    monkeypatch.setattr("backend.voice.audio_capture.sounddevice", dummy_sd)

    recorder = AudioRecorder(sample_rate=16000, channels=1, chunk_size=1024, record_duration=0.1)
    audio_bytes = await recorder.record_audio()

    assert audio_bytes
    assert dummy_sd.started


def test_transcription_service_returns_response(monkeypatch):
    class FakeTranscriber:
        def __init__(self):
            self.calls = []

        async def transcribe_audio(self, audio_bytes, *, language=None, **kwargs):
            self.calls.append((audio_bytes, language))
            return TranscriptionResponse(text="hello world", language="en", confidence=0.95, processing_time=0.12)

    transcriber = FakeTranscriber()
    service = TranscriptionService(transcriber=transcriber)

    response = asyncio_run(service.transcribe_audio(b"abc"))

    assert response.text == "hello world"
    assert response.language == "en"


def test_model_loading_uses_configured_model(monkeypatch):
    class FakeModel:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

    monkeypatch.setattr("backend.voice.speech_to_text._WHISPER_MODEL_CLASS", FakeModel)
    transcriber = FasterWhisperTranscriber(model_name="tiny")
    model = transcriber.load_model()

    assert model is not None


def test_voice_transcribe_endpoint(monkeypatch):
    class FakeService:
        async def transcribe_audio(self, audio_bytes, *, language=None, **kwargs):
            return TranscriptionResponse(text="hello", language="en", confidence=0.92, processing_time=0.05)

    monkeypatch.setattr("backend.api.routes.get_transcription_service", lambda: FakeService())
    client = TestClient(app)

    response = client.post("/api/voice/transcribe", json={"audio_bytes": "abc", "language": "en"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["text"] == "hello"


def asyncio_run(coro):
    import asyncio

    return asyncio.run(coro)
