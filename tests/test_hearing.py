"""Audio/cancellation regressions, independent of room noise and cloud services."""
import asyncio
import threading
from types import SimpleNamespace

import numpy as np
import pytest

from app.audio.hearing import boost_pcm
from app.audio.recorder import Recorder, Player, rms_level
from app.assistant.states import State
from app.tts.service import TTSService
from tests.test_engine import _make_engine


def fake_microphone(monkeypatch, levels, on_read=None):
    class Stream:
        def __init__(self, **kwargs):
            self.index = 0

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, count):
            if on_read:
                on_read(self.index)
            level = levels[min(self.index, len(levels) - 1)]
            self.index += 1
            # Zero-mean PCM, avoiding a DC-only test signal.
            return np.tile([level, -level], count // 2).astype(np.int16).reshape(-1, 1), False
    monkeypatch.setattr("app.audio.recorder.sd.InputStream", Stream)


def test_soft_voice_records_below_old_threshold_and_keeps_onset(monkeypatch):
    fake_microphone(monkeypatch, [10] * 8 + [120] * 9 + [10] * 20)
    readings = []
    rec = Recorder(max_seconds=2, silence_timeout=.21, on_level=readings.append)
    audio = rec.record()
    assert audio is not None and audio.dtype == np.int16
    assert np.count_nonzero(np.abs(audio) > 100) == 9 * 480
    assert any(x["active"] for x in readings)
    assert readings[-1]["level"] == 0


@pytest.mark.parametrize("levels", [[240] * 50, [10] * 8 + [5000] + [10] * 40, [0] * 50])
def test_stationary_noise_silence_and_single_bump_are_not_questions(monkeypatch, levels):
    fake_microphone(monkeypatch, levels)
    assert Recorder(max_seconds=1.5).record() is None


def test_seeded_room_floor_preserves_immediate_quiet_first_word(monkeypatch):
    fake_microphone(monkeypatch, [120] * 10 + [10] * 20)
    rec = Recorder(max_seconds=2, silence_timeout=.2)
    rec.noise_source = lambda: 10
    audio = rec.record()
    assert audio is not None
    assert np.count_nonzero(np.abs(audio) > 100) == 10 * 480


def test_recording_cancel_discards_partial_audio_and_allows_next_turn(monkeypatch):
    rec = Recorder(max_seconds=1.5, silence_timeout=.2)
    rec.noise_source = lambda: 10
    fake_microphone(monkeypatch, [150] * 10 + [0] * 20,
                    lambda index: rec.turn_cancelled.set() if index == 5 else None)
    assert rec.record() is None
    assert not rec.last_error
    rec.turn_cancelled.clear()
    fake_microphone(monkeypatch, [150] * 10 + [0] * 20)
    assert rec.record() is not None


def test_quiet_gain_is_bounded_and_does_not_clip_or_amplify_silence():
    quiet = np.tile([120, -120], 800).astype(np.int16)
    assert rms_level(boost_pcm(quiet, 6)) == pytest.approx(720)
    peaked = quiet.copy()
    peaked[0] = 29000
    assert np.max(np.abs(boost_pcm(peaked, 6).astype(np.int32))) <= 30000
    assert not boost_pcm(np.zeros(100, dtype=np.int16), 6).any()


def test_cancel_during_ai_drops_late_answer_and_next_question_succeeds():
    events = []
    engine = _make_engine(cooldown_seconds=0, on_event=lambda *args: events.append(args))
    entered, release = threading.Event(), threading.Event()
    original = engine.ai.chat
    def delayed(messages):
        entered.set()
        assert release.wait(3)
        return "An answer that arrived too late"
    engine.ai.chat = delayed
    engine.startup()
    engine.submit_text("Tell me a story")
    thread = threading.Thread(target=engine.process_pending_wake)
    thread.start()
    assert entered.wait(2)
    assert engine.cancel_turn()
    assert not engine.submit_text("Too soon")
    release.set()
    thread.join(2)
    assert not thread.is_alive() and engine.state == State.STANDBY
    assert len(engine.context) == 1 and not engine.tts.spoken
    assert not any(k == "message" and p["role"] == "assistant" for k, p in events)
    engine.ai.chat = original
    assert engine.submit_text("Explain Python")
    engine.process_pending_wake()
    assert engine.context.last_assistant() and engine.tts.spoken


def test_cancel_before_capture_does_not_open_microphone():
    engine = _make_engine(cooldown_seconds=0)
    engine.startup()
    engine.request_listen()
    assert engine.cancel_turn()
    engine.process_pending_wake()
    assert engine.recorder.calls == 0 and not engine.tts.spoken
    assert engine.request_listen()
    engine.process_pending_wake()
    assert engine.recorder.calls == 1


def test_short_multisentence_reply_uses_one_synthesis_request(tmp_path):
    tts = TTSService(cache_dir=tmp_path)
    calls = []
    def synthesize(text):
        calls.append(text)
        path = tmp_path / "sample.mp3"
        path.write_bytes(b"synthetic")
        return path
    tts._synthesize_sync = synthesize
    tts.attach_player(SimpleNamespace(play_file=lambda path: path.exists(), stop=lambda: None))
    assert tts.speak("Hello there. I can help. What do you need?")
    assert calls == ["Hello there. I can help. What do you need?"]
    assert not list(tmp_path.glob("*.mp3"))
    tts.shutdown()


def test_turn_cancel_interrupts_synthesis_and_service_can_be_reused(tmp_path):
    tts = TTSService(cache_dir=tmp_path)
    entered, stopped = threading.Event(), threading.Event()
    played = []
    async def slow_synthesis(text):
        entered.set()
        try:
            await asyncio.sleep(30)
        finally:
            stopped.set()
    tts._synthesize_async = slow_synthesis
    tts.attach_player(SimpleNamespace(play_file=lambda path: played.append(path) or True, stop=lambda: None))
    result = []
    thread = threading.Thread(target=lambda: result.append(tts.speak("Wait")))
    thread.start()
    try:
        assert entered.wait(2)
        tts.turn_cancelled.set()
        thread.join(1)
        assert not thread.is_alive() and result == [False]
        assert stopped.wait(1) and not played
        tts.turn_cancelled.clear()
        tts.provider = "mock"
        assert tts.speak("Ready again")
    finally:
        tts.shutdown()


def test_cancel_between_file_read_and_playback_does_not_open_speaker(monkeypatch, tmp_path):
    player = Player()
    path = tmp_path / "sample.wav"
    path.touch()
    def read(*args, **kwargs):
        player.turn_cancelled.set()
        return np.zeros(1600), 16000
    monkeypatch.setattr("app.audio.recorder.sf.read", read)
    monkeypatch.setattr("app.audio.recorder.sd.OutputStream", lambda **kw: pytest.fail("Late playback"))
    assert not player.play_file(path)


def test_cancelled_gemini_turn_skips_retry_but_can_be_reused():
    from app.ai.base import AIProviderError, ChatMessage
    from tests.test_reliability import provider_with, ApiError
    provider, calls = provider_with(["Next turn succeeds"])
    original = provider._client.models.generate_content
    failed = []
    def cancelled_request(**kwargs):
        failed.append(True)
        provider.turn_cancelled.set()
        raise ApiError(503)
    provider._client.models.generate_content = cancelled_request
    with pytest.raises(AIProviderError, match="cancelled"):
        provider.chat([ChatMessage("user", "Hello")])
    assert len(failed) == 1
    provider.turn_cancelled.clear()
    provider._client.models.generate_content = original
    assert provider.chat([ChatMessage("user", "Hello again")]) == "Next turn succeeds"
    assert len(calls) == 1
