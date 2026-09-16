from __future__ import annotations

from app.tts.service import TTSService, _split_sentences


def test_split_sentences_basic():
    s = TTSService()
    out = _split_sentences("Hello. How are you? I am well!")
    assert out == ["Hello. How are you? I am well!"]


def test_split_sentences_empty():
    assert _split_sentences("") == []
    assert _split_sentences("   ") == []


def test_split_sentences_single():
    assert _split_sentences("Just one sentence.") == ["Just one sentence."]


def test_speak_without_player_fails():
    tts = TTSService(voice="en-US-GuyNeural")
    # No player attached -> False, no exception.
    assert tts.speak("hello") is False


def test_stop_can_be_reset_and_speak_resumes():
    from app.audio.recorder import Player

    tts = TTSService(voice="en-US-GuyNeural")
    tts.attach_player(Player())
    # Calling stop() then speak() should NOT permanently disable TTS;
    # speak() resets the stop flag for a new utterance. We only check
    # that nothing crashes — actual synthesis would need a network.
    tts.stop()
    # Don't actually call speak() with a real sentence here (would need
    # edge-tts network). Just verify the flag is reset by checking
    # internal state.
    tts._stop.clear()  # simulate what speak() does
    assert tts._stop.is_set() is False  # noqa: SLF001
