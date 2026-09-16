import asyncio
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import threading
import time
import uuid

import numpy as np
import pytest

from app.ai.base import AIProviderError, ChatMessage
from app.ai.gemini_provider import GeminiProvider
from app.assistant.commands import local_reply
from app.assistant.conversation import ConversationContext
from app.assistant.states import State
from app.audio.recorder import Recorder
from app.system.instance import SingleInstance
from app.tts.service import TTSService
from app.wakeword.detector import OpenWakeWordDetector
from tests.test_engine import _make_engine, FakeAI, FakeSTT


def cycle(engine):
    engine._on_wake()
    engine.process_pending_wake()


def test_wake_callback_only_queues_and_deduplicates():
    engine = _make_engine(cooldown_seconds=0)
    engine.startup()
    engine._on_wake()
    engine._on_wake()
    assert engine.recorder.calls == 0
    assert engine.tts.spoken == []
    assert engine.state == State.WAKE_DETECTED
    engine.process_pending_wake()
    engine.process_pending_wake()
    assert len(engine.ai.calls) == 1
    assert engine.state == State.STANDBY


def test_real_run_loop_processes_wake_and_stops():
    ready = threading.Event()
    engine = _make_engine(cooldown_seconds=0,
                          on_state_change=lambda state: ready.set() if state == State.STANDBY else None)
    thread = threading.Thread(target=engine.run)
    thread.start()
    try:
        assert ready.wait(2)
        engine.wake.fire()
        deadline = time.monotonic() + 2
        while not engine.ai.calls and time.monotonic() < deadline:
            time.sleep(0.01)
        assert engine.ai.calls
    finally:
        engine.request_shutdown()
        thread.join(2)
    assert not thread.is_alive()
    assert engine.wake.stopped


def test_shutdown_during_ai_never_plays_late_reply():
    engine = _make_engine(cooldown_seconds=0)
    engine.startup()
    def cancelled(messages):
        engine.request_shutdown()
        return "This answer arrived too late."
    engine.ai.chat = cancelled
    cycle(engine)
    assert engine.tts.spoken == [engine.acknowledgement]
    assert len(engine.context) == 1
    assert not engine.wake.enabled


def test_transcription_exception_recovers_next_command():
    engine = _make_engine(cooldown_seconds=0)
    engine.startup()
    engine.stt.transcribe = lambda audio: (_ for _ in ()).throw(RuntimeError("bad audio"))
    cycle(engine)
    assert engine.state == State.STANDBY and engine.wake.enabled
    engine.stt = FakeSTT()
    cycle(engine)
    assert len(engine.ai.calls) == 1


def test_failed_reply_does_not_pollute_memory():
    ai = FakeAI()
    ai.raise_once = AIProviderError("Temporary network failure.")
    engine = _make_engine(ai=ai, cooldown_seconds=0)
    engine.startup()
    cycle(engine)
    assert len(engine.context) == 1
    assert engine.tts.spoken[-1] == "Temporary network failure."
    cycle(engine)
    assert len(engine.context) == 3


def test_history_never_starts_with_orphan_assistant():
    context = ConversationContext("system", max_messages=4)
    for i in range(10):
        context.add_turn(f"question {i}", f"answer {i}")
        assert [m.role for m in context.messages()] == ["system", "user", "assistant"]
    copy = context.messages()
    copy[0].content = "changed"
    assert context.messages()[0].content == "system"


def test_local_controls_are_exact_and_use_real_time():
    context = ConversationContext("system")
    context.add_turn("Hello", "Hi there.")
    assert local_reply("Repeat that!", context) == "Hi there."
    assert "3:42 PM" in local_reply("What time is it?", context, datetime(2026, 9, 11, 15, 42))
    assert local_reply("Explain why people repeat themselves", context) is None
    assert local_reply("clear conversation", context)
    assert len(context) == 1


def provider_with(responses):
    provider = GeminiProvider.__new__(GeminiProvider)
    provider._model_name = "test-model"
    provider._cancelled = threading.Event()
    provider.turn_cancelled = threading.Event()
    provider.max_attempts = 2
    calls = []
    def generate_content(**kwargs):
        calls.append(kwargs)
        response = responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return SimpleNamespace(text=response)
    provider._client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    return provider, calls


class ApiError(Exception):
    def __init__(self, code):
        self.code = code


def test_gemini_retries_temporary_failure(monkeypatch):
    provider, calls = provider_with([ApiError(503), "Recovered"])
    monkeypatch.setattr(provider.turn_cancelled, "wait", lambda delay: False)
    assert provider.chat([ChatMessage("user", "Hi")]) == "Recovered"
    assert len(calls) == 2


def test_gemini_does_not_retry_access_errors():
    provider, calls = provider_with([ApiError(403)])
    with pytest.raises(AIProviderError, match="access was denied"):
        provider.chat([ChatMessage("user", "Hi")])
    assert len(calls) == 1


def test_gemini_empty_response_is_an_error():
    provider, _ = provider_with([""])
    with pytest.raises(AIProviderError, match="rephrase"):
        provider.chat([ChatMessage("user", "Hi")])


def test_stopped_recorder_does_not_reopen_microphone(monkeypatch):
    import app.audio.recorder as audio
    monkeypatch.setattr(audio.sd, "InputStream", lambda **kw: pytest.fail("Mic reopened after stop"))
    recorder = Recorder()
    recorder.stop()
    assert recorder.record() is None


def test_single_instance_releases_on_exit():
    import os
    if os.name != "nt":
        pytest.skip("Windows mutex")
    name = "Local\\JARVIS-test-" + uuid.uuid4().hex
    first, second = SingleInstance(name), SingleInstance(name)
    try:
        assert first.acquire()
        assert not second.acquire()
        first.release()
        assert second.acquire()
    finally:
        first.release()
        second.release()


def test_wake_resets_audio_history_after_pause():
    wake = OpenWakeWordDetector()
    resets = []
    wake._oww_model = SimpleNamespace(reset=lambda: resets.append(True), predict=lambda x: {"hey_jarvis": 0.0})
    wake._model_label = "hey_jarvis"
    wake._accum = np.ones(1000, dtype=np.int16)
    wake.set_enabled(False)
    wake.set_enabled(True)
    wake.process(np.zeros(1280, dtype=np.int16))
    assert resets == [True]
    assert wake._accum.size == 0


def test_wake_reconnects_after_microphone_failure(monkeypatch):
    import app.wakeword.detector as module
    wake = OpenWakeWordDetector()
    attempts = []
    class Stream:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, count):
            wake._stop_event.set()
            return np.zeros(0, dtype=np.int16), False
    def connect(**kwargs):
        attempts.append(True)
        if len(attempts) == 1:
            raise RuntimeError("device disconnected")
        return Stream()
    monkeypatch.setattr(module.sd, "InputStream", connect)
    monkeypatch.setattr(wake._stop_event, "wait", lambda seconds: False)
    wake._run()
    assert len(attempts) == 2


def test_cancelled_synthesis_removes_partial_file(monkeypatch, tmp_path):
    import edge_tts
    started = threading.Event()
    class Communicate:
        def __init__(self, **kw): pass
        async def save(self, path):
            Path(path).write_bytes(b"partial audio")
            started.set()
            await asyncio.Event().wait()
    monkeypatch.setattr(edge_tts, "Communicate", Communicate)
    tts = TTSService(cache_dir=tmp_path)
    worker = threading.Thread(target=tts._synthesize_sync, args=("Hello",))
    worker.start()
    try:
        assert started.wait(2)
        tts.cancel()
        worker.join(2)
        assert not worker.is_alive()
    finally:
        tts.shutdown()
    assert not list(tmp_path.glob("*.mp3"))
    assert not tts.speak("Late reply")


def test_hindi_uses_hindi_voice_and_phrase_cache(monkeypatch, tmp_path):
    import edge_tts
    voices = []
    class Communicate:
        def __init__(self, text, voice): voices.append(voice)
        async def save(self, path): Path(path).write_bytes(b"audio")
    monkeypatch.setattr(edge_tts, "Communicate", Communicate)
    tts = TTSService(cache_dir=tmp_path)
    async def synthesize():
        for text in ("नमस्ते", "नमस्ते", "Hello"):
            path = await tts._synthesize_async(text)
            path.unlink()
    asyncio.run(synthesize())
    tts.shutdown()
    assert voices == ["hi-IN-SwaraNeural", "en-US-GuyNeural"]


def test_hotkey_failure_is_reported(monkeypatch):
    import keyboard
    from app.system.hotkey import EmergencyHotkey
    monkeypatch.setattr(keyboard, "add_hotkey", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("unavailable")))
    assert EmergencyHotkey().start() is False


def test_mock_tts_never_contacts_network(monkeypatch, tmp_path):
    tts = TTSService(cache_dir=tmp_path, provider="mock")
    monkeypatch.setattr(tts, "_synthesize_sync", lambda text: pytest.fail("Network used in mock mode"))
    assert tts.speak("Testing.")
    tts.shutdown()
