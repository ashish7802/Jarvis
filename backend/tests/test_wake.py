from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.config.settings import Settings
from backend.voice.wake_detector import WakeDetector
from backend.voice.wake_listener import WakeListener
from backend.voice.wake_service import WakeService


class FakeModel:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def predict(self, payload):
        return {"score": 0.91}


class FakeOpenWakeWordModule:
    OpenWakeWordModel = FakeModel


class FakeDetector(WakeDetector):
    async def initialize(self):
        self._initialized = True
        self._model = FakeModel()


@pytest.mark.asyncio
async def test_detector_initializes_and_predicts(monkeypatch):
    monkeypatch.setattr("backend.voice.wake_detector.openwakeword", FakeOpenWakeWordModule())
    monkeypatch.setattr("backend.voice.wake_detector.sounddevice", object())
    monkeypatch.setattr("backend.voice.wake_detector.np", type("NumpyStub", (), {"int16": "int16", "frombuffer": staticmethod(lambda data, dtype=None: data)}))

    detector = WakeDetector(engine="openwakeword", model="hey_jarvis", threshold=0.5, device="default")
    await detector.initialize()
    score = await detector.predict(b"abc")

    assert score >= 0.5


@pytest.mark.asyncio
async def test_listener_start_stop_pause_resume():
    detector = FakeDetector(engine="openwakeword", model="hey_jarvis", threshold=0.5, device="default")
    listener = WakeListener(detector, timeout=0.1, cooldown=0.0)
    await listener.start()
    await listener.pause()
    await listener.resume()
    await listener.stop()

    assert listener.is_running() is False


def test_wake_service_status(monkeypatch):
    class FakeListener:
        def __init__(self):
            self.timeout = 1.0
            self.cooldown = 0.0

        def is_running(self):
            return True

        def is_paused(self):
            return False

    class FakeDetector:
        engine = "openwakeword"
        model = "hey_jarvis"
        threshold = 0.5
        device = "default"

    service = WakeService(detector=FakeDetector(), listener=FakeListener())
    status = service.get_status()

    assert status.engine == "openwakeword"
    assert status.running is True


def test_status_endpoint(monkeypatch):
    monkeypatch.setattr("backend.api.routes.get_wake_service", lambda: FakeWakeService())
    client = TestClient(app)

    response = client.get("/api/voice/wake/status")

    assert response.status_code == 200


class FakeWakeService:
    def get_status(self):
        from backend.voice.schemas import WakeStatus

        return WakeStatus(running=True, paused=False, engine="openwakeword", wake_word="hey_jarvis", threshold=0.5, timeout=5.0, cooldown=1.0, device="default", last_event=None)


def test_settings_load_wake_configuration(monkeypatch):
    monkeypatch.setenv("WAKE_ENGINE", "openwakeword")
    monkeypatch.setenv("WAKE_WORD", "hey_jarvis")
    monkeypatch.setenv("WAKE_MODEL", "hey_jarvis")
    monkeypatch.setenv("WAKE_THRESHOLD", "0.7")
    monkeypatch.setenv("WAKE_TIMEOUT", "2.0")
    monkeypatch.setenv("WAKE_COOLDOWN", "0.5")
    monkeypatch.setenv("MIC_DEVICE", "default")

    settings = Settings()

    assert settings.wake_engine == "openwakeword"
    assert settings.wake_threshold == 0.7


def asyncio_run(coro):
    return asyncio.run(coro)
