from __future__ import annotations

import threading
import time
from typing import Optional

import numpy as np

from app.ai.base import AIProvider, ChatMessage
from app.assistant.engine import AssistantEngine
from app.assistant.states import State
from app.audio.recorder import Player
from app.stt.service import STTService
from app.tts.service import TTSService
from app.wakeword.detector import WakeWordDetector


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeAI(AIProvider):
    name = "fake-ai"

    def __init__(self, reply: str = "I am here, Sir.") -> None:
        self._reply = reply
        self.calls: list[list[ChatMessage]] = []
        self.raise_once: Optional[Exception] = None

    def chat(self, messages):
        self.calls.append(messages)
        if self.raise_once is not None:
            exc = self.raise_once
            self.raise_once = None
            raise exc
        return self._reply


class FakeSTT(STTService):
    def __init__(self, transcript: str = "what is Python") -> None:
        # Skip super().__init__ — we override transcribe.
        self._transcript = transcript
        self.calls = 0

    def transcribe(self, audio, sample_rate: int = 16_000) -> str:  # type: ignore[override]
        self.calls += 1
        return self._transcript

    def shutdown(self) -> None:  # type: ignore[override]
        pass


class FakeTTS(TTSService):
    def __init__(self) -> None:  # noqa: D401
        # skip init - we override speak entirely
        self.spoken: list[str] = []
        self.raise_once: Optional[Exception] = None
        self.player = None

    def attach_player(self, player):  # type: ignore[override]
        self.player = player

    def speak(self, text: str) -> bool:  # type: ignore[override]
        self.spoken.append(text)
        if self.raise_once is not None:
            exc = self.raise_once
            self.raise_once = None
            raise exc
        return True

    def stop(self) -> None:  # type: ignore[override]
        pass

    def cancel(self):
        pass

    def shutdown(self):
        pass


class FakeWake(WakeWordDetector):
    name = "fake-wake"

    def __init__(self) -> None:
        self.cb = None
        self.enabled = True
        self.started = False
        self.stopped = False

    def set_callback(self, cb) -> None:
        self.cb = cb

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled

    def fire(self) -> None:
        if self.cb is not None:
            self.cb()


class FakeRecorder:
    def __init__(self, audio: Optional[np.ndarray] = None) -> None:
        self._audio = audio
        self.calls = 0
        self.stopped = False

    def record(self):
        self.calls += 1
        return self._audio

    def stop(self) -> None:
        self.stopped = True


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def _make_engine(ai=None, stt=None, tts=None, wake=None, recorder=None, player=None, **kwargs):
    ai = ai or FakeAI()
    stt = stt or FakeSTT()
    tts = tts or FakeTTS()
    wake = wake or FakeWake()
    recorder = recorder or FakeRecorder(audio=np.zeros(1600, dtype=np.int16))
    player = player or Player()  # not actually used (tts is faked)
    tts.attach_player(player)
    eng = AssistantEngine(
        ai=ai,
        stt=stt,
        tts=tts,
        wake=wake,
        recorder=recorder,
        player=player,
        startup_greeting=None,  # don't block on greeting in tests
        **kwargs,
    )
    return eng


def test_engine_happy_path():
    eng = _make_engine()
    eng.startup()
    assert eng.state == State.STANDBY
    eng._on_wake()
    eng.process_pending_wake()
    assert eng.state == State.STANDBY
    assert eng.ai.calls, "AI was not called"
    assert eng.stt.calls == 1
    assert "I am here" in eng.tts.spoken[-1]
    assert "what is Python" in eng.context.messages()[-2].content


def test_engine_no_speech_returns_to_standby():
    eng = _make_engine(recorder=FakeRecorder(audio=None))
    eng.startup()
    eng._on_wake()
    eng.process_pending_wake()
    assert eng.state == State.STANDBY
    assert eng.ai.calls == []
    assert eng.tts.spoken[0] == "Yes, Sir?"
    assert "didn't hear" in eng.tts.spoken[-1]


def test_engine_empty_stt_returns_to_standby():
    eng = _make_engine(stt=FakeSTT(transcript=""))
    eng.startup()
    eng._on_wake()
    eng.process_pending_wake()
    assert eng.state == State.STANDBY
    assert eng.ai.calls == []


def test_engine_ai_failure_does_not_crash():
    ai = FakeAI()
    ai.raise_once = RuntimeError("boom")
    eng = _make_engine(ai=ai)
    eng.startup()
    eng._on_wake()
    eng.process_pending_wake()
    assert eng.state == State.STANDBY
    # TTS should still have been called with the fallback reply.
    assert any("went wrong" in s or "didn't catch" in s for s in eng.tts.spoken)


def test_engine_tts_failure_does_not_crash():
    tts = FakeTTS()
    tts.raise_once = RuntimeError("tts boom")
    eng = _make_engine(tts=tts)
    eng.startup()
    eng._on_wake()
    eng.process_pending_wake()
    assert eng.state == State.STANDBY


def test_wake_disabled_during_speaking():
    eng = _make_engine()
    eng.startup()
    wake = eng.wake
    eng._on_wake()
    eng.process_pending_wake()
    # After the cycle, wake must be re-enabled.
    assert wake.enabled is True
    # During the cycle, set_enabled(False) must have been called at
    # least once (we check via the recorded transitions by setting a
    # counter manually).
    counters = {"disable": 0, "enable": 0}
    orig = wake.set_enabled

    def spy(enabled):
        if enabled:
            counters["enable"] += 1
        else:
            counters["disable"] += 1
        orig(enabled)

    wake.set_enabled = spy  # type: ignore[assignment]
    eng._on_wake()
    eng.process_pending_wake()
    assert counters["disable"] >= 1
    assert counters["enable"] >= 1


def test_wake_callback_ignored_in_non_standby_state():
    eng = _make_engine()
    eng.startup()
    eng.set_state(State.LISTENING)  # simulate a stale state
    eng._on_wake()
    eng.process_pending_wake()
    # Nothing should happen; AI not called.
    assert eng.ai.calls == []


def test_shutdown_is_clean():
    eng = _make_engine()
    eng.startup()
    eng.request_shutdown()
    # The shutdown is async via engine.run; simulate it.
    eng._shutdown_sequence()
    assert eng.state == State.SHUTTING_DOWN
    assert eng.wake.stopped is True
    assert eng.recorder.stopped is True


def test_context_preserved_across_turns():
    eng = _make_engine()
    eng.startup()
    eng.context.add_user("Write a short email to John.")
    eng.context.add_assistant("Sure, what should it say?")
    eng._on_wake()
    eng.process_pending_wake()
    msgs = eng.context.messages()
    # Initial system + the 2 preloaded + new user + assistant
    assert msgs[0].role == "system"
    assert any(m.content == "Write a short email to John." for m in msgs)
    assert any(m.content == "Sure, what should it say?" for m in msgs)
    assert any(m.content == "what is Python" for m in msgs)
