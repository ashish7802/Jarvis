from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.voice.voice_controller import VoiceController
from backend.voice.voice_pipeline import VoicePipeline


class FakeWakeService:
    async def start(self):
        return {"wake": True}

    async def stop(self):
        return None

    async def pause(self):
        return None

    async def resume(self):
        return None


class FakeRecorder:
    async def record_audio(self):
        return b"audio-bytes"


class FakeTranscriber:
    async def transcribe_audio(self, audio_bytes, *, language=None, **kwargs):
        return type("Result", (), {"text": "hello"})()


class FakeLLMService:
    async def generate_completion(self, prompt, *, model=None, **kwargs):
        return "Hi there"


class FakeTTSService:
    async def speak(self, text, **kwargs):
        return type("Speech", (), {"audio_bytes": b"wav", "voice": "en-US-AriaNeural"})()


class FakePipeline:
    def __init__(self):
        self.started = False
        self.stopped = False

    async def start(self):
        self.started = True
        return {"status": "running"}

    async def stop(self):
        self.stopped = True
        return {"status": "stopped"}

    async def run_once(self):
        return {"result": "ok"}

    def status(self):
        return {"state": "idle"}


@pytest.mark.asyncio
async def test_pipeline_runs_once_with_fakes():
    pipeline = VoicePipeline(
        wake_service=FakeWakeService(),
        recorder=FakeRecorder(),
        transcriber=FakeTranscriber(),
        llm_service=FakeLLMService(),
        tts_service=FakeTTSService(),
    )

    result = await pipeline.run_once()

    assert result["recognized_text"] == "hello"
    assert result["llm_response"] == "Hi there"


@pytest.mark.asyncio
async def test_controller_delegates_to_pipeline():
    fake_pipeline = FakePipeline()
    controller = VoiceController(pipeline=fake_pipeline)

    await controller.start()
    await controller.stop()
    result = await controller.run_once()
    status = controller.status()

    assert fake_pipeline.started is True
    assert fake_pipeline.stopped is True
    assert result["result"] == "ok"
    assert status["state"] == "idle"


def test_voice_start_stop_and_status_endpoints(monkeypatch):
    class FakeVoiceController:
        def __init__(self):
            self.calls = []

        async def start(self):
            self.calls.append("start")
            return {"status": "running"}

        async def stop(self):
            self.calls.append("stop")
            return {"status": "stopped"}

        async def run_once(self):
            self.calls.append("run_once")
            return {"ok": True}

        def status(self):
            return {"state": "idle"}

    fake_controller = FakeVoiceController()
    monkeypatch.setattr("backend.api.routes.get_voice_controller", lambda: fake_controller)

    client = TestClient(app)

    start_response = client.post("/api/voice/start")
    stop_response = client.post("/api/voice/stop")
    run_once_response = client.post("/api/voice/run-once")
    status_response = client.get("/api/voice/status")

    assert start_response.status_code == 200
    assert stop_response.status_code == 200
    assert run_once_response.status_code == 200
    assert status_response.status_code == 200
    assert fake_controller.calls == ["start", "stop", "run_once"]
