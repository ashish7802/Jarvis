from types import SimpleNamespace
import numpy as np
import pytest

from app.assistant.calculator import calculation_reply
from app.assistant.states import State
from app.stt.service import STTService
from tests.test_engine import _make_engine, FakeSTT, FakeRecorder


@pytest.mark.parametrize("question, result", [
    ("What is 17 times 23?", "391"),
    ("Calculate 0.1 plus 0.2", "0.3"),
    ("What is 12.5 percent of 240?", "30"),
    ("What is two plus two?", "4"),
    ("Calculate (8 + 4) / 3", "4"),
    ("Calculate 2 to the power of 10", "1024"),
    ("Calculate -5 plus 2", "-3"),
    ("Calculate 1,000,000 / 4", "250000"),
    ("Calculate 1 / 3", "approximately 0.333333"),
])
def test_local_math(question, result):
    assert calculation_reply(question) == f"The result is {result}."


def test_undefined_calculation():
    assert "divide by zero" in calculation_reply("Calculate 8 / 0")


@pytest.mark.parametrize("question", [
    "Explain how Python works", "What is the weather?", "Tell me about twenty one pilots",
    "calculate __import__('os').system('whoami')", "calculate 2 ** 999999",
    "Calculate 10 ** 12 ** 12", "Calculate open('secret').read()",
])
def test_other_questions_and_unsafe_expressions_are_not_evaluated(question):
    assert calculation_reply(question) is None


def run_cycle(engine):
    engine._on_wake()
    engine.process_pending_wake()


def test_local_answers_survive_repeat_and_followup():
    engine = _make_engine(stt=FakeSTT("Calculate 17 times 23"), cooldown_seconds=0)
    engine.startup()
    run_cycle(engine)
    assert not engine.ai.calls
    assert engine.context.last_assistant() == "The result is 391."
    engine.stt = FakeSTT("repeat that")
    run_cycle(engine)
    assert engine.tts.spoken[-1] == "The result is 391."
    engine.stt = FakeSTT("Explain how you got that")
    run_cycle(engine)
    assert any(message.content == "The result is 391." for message in engine.ai.calls[-1])
    engine.stt = FakeSTT("clear conversation")
    run_cycle(engine)
    assert len(engine.context) == 1


def test_mic_failure_gives_feedback_and_recovers():
    recorder = FakeRecorder(None)
    recorder.last_error = True
    engine = _make_engine(recorder=recorder, cooldown_seconds=0)
    engine.startup()
    run_cycle(engine)
    assert "microphone" in engine.tts.spoken[-1]
    assert engine.state == State.STANDBY and engine.wake.enabled
    assert not engine.ai.calls


def test_unrecognized_speech_gives_feedback_without_inventing_a_question():
    engine = _make_engine(stt=FakeSTT(""), cooldown_seconds=0)
    engine.startup()
    run_cycle(engine)
    assert "couldn't understand" in engine.tts.spoken[-1]
    assert not engine.ai.calls
    assert len(engine.context) == 1


def test_new_wake_event_is_not_overwritten_by_previous_command_cleanup():
    engine = _make_engine(cooldown_seconds=0)
    engine.startup()
    original = engine.wake.set_enabled
    queued = []
    def enable(value):
        original(value)
        if value and not queued:
            queued.append(True)
            engine._on_wake()
    engine.wake.set_enabled = enable
    run_cycle(engine)
    assert engine.state == State.WAKE_DETECTED
    assert engine._wake_event.is_set()
    engine.process_pending_wake()
    assert len(engine.ai.calls) == 2
    assert engine.state == State.STANDBY


def stub_stt():
    received = []
    def transcribe(audio, **kwargs):
        received.append(audio.copy())
        return [SimpleNamespace(text=" Test speech. ")], None
    stt = STTService()
    stt._model = SimpleNamespace(transcribe=transcribe)
    return stt, received


@pytest.mark.parametrize("dtype", [np.float32, np.float64])
def test_float_audio_keeps_volume_and_never_becomes_a_filename(dtype):
    stt, received = stub_stt()
    assert stt.transcribe(np.full(1600, 0.5, dtype=dtype)) == "Test speech."
    assert received[0].dtype == np.float32
    assert np.allclose(received[0], 0.5)


def test_pcm_stereo_and_sample_rate_are_normalized():
    stt, received = stub_stt()
    assert stt.transcribe(np.full((4800, 2), 16384, dtype=np.int16), 48000) == "Test speech."
    assert received[0].shape == (1600,)
    assert np.isclose(received[0][100:-100].mean(), 0.5, atol=0.001)


@pytest.mark.parametrize("audio", [np.zeros(1600), np.full(10, np.nan), np.full(10, np.inf)])
def test_silence_and_invalid_audio_never_reach_whisper(audio):
    stt, received = stub_stt()
    assert stt.transcribe(audio) == ""
    assert not received
