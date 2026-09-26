import re
from types import SimpleNamespace

import numpy as np
import pytest

from app.assistant.language import reply_language
from app.assistant.commands import desktop_command
from app.stt.service import STTService
from app.tts.service import TTSService
from tests.test_engine import _make_engine


@pytest.mark.parametrize("text,expected", [
    ("Mujhe Python simple language mein samjhao", "hi"),
    ("ये काम कैसे करता है?", "hi"),
    ("Yaar kya haal hai", "hi"),
    ("Yaar, mujhe is app ko easy words mein samjhao", "hi"),
    ("Aaj weather kaisa hai?", "hi"),
    ("Can you batao what this button does?", "hi"),
    ("Kya this app is ready?", "hi"),
    ("Explain the main function in Python", "en"),
    ("What is Python?", "en"),
    ("How can I start the app?", "en"),
    ("The main feature is easy to use", "en"),
    ("I need a simple answer", "en"),
])
def test_language_hint_understands_roman_hindi_without_forcing_english(text, expected):
    assert reply_language(text) == expected


@pytest.mark.parametrize("text", ["haan", "nahi", "theek hai", "accha"])
def test_short_hinglish_followups_keep_hindi_replies(text):
    assert reply_language(text, previous="hi") == "hi"


def test_short_english_followup_keeps_english_reply():
    assert reply_language("okay", previous="en") == "en"


def test_auto_switches_languages_on_new_question_and_keeps_neutral_followup():
    engine = _make_engine(cooldown_seconds=0)
    engine.startup()
    for question, language in [("mujhe Python samjhao", "hi"), ("okay", "hi"),
                               ("Explain a computer in English", "en")]:
        engine.submit_text(question)
        engine.process_pending_wake()
        assert engine._reply_language == language
        assert "latest user message" in engine.ai.calls[-1][0].content
    assert len(engine.context) == 7


@pytest.mark.parametrize("command,mode", [("हिंदी में बात करो", "hi"), ("English mein baat karo", "en"),
                                         ("hinglish mein baat karo", "hinglish"), ("meri language mein baat karo", "auto")])
def test_spoken_language_switch_is_local_and_updates_recognition(command, mode):
    events = []
    engine = _make_engine(cooldown_seconds=0, on_event=lambda *x: events.append(x))
    engine.startup()
    engine.submit_text(command)
    engine.process_pending_wake()
    assert engine.language_mode == mode
    assert ("language", mode) in events
    assert not engine.ai.calls and len(engine.context) == 1
    assert engine.stt.language == ("hi" if mode == "hinglish" else None if mode == "auto" else mode)


def test_discussing_language_setting_does_not_change_it():
    assert desktop_command("Why should I use Hindi mode for this example?") is None


def test_hindi_time_and_repeat_are_local_and_spoken_in_hindi():
    engine = _make_engine(cooldown_seconds=0)
    engine.startup()
    engine.submit_text("अभी कितने बजे हैं")
    engine.process_pending_wake()
    answer = engine.context.last_assistant()
    assert "बजे हैं" in answer and engine.tts.language_hint == "hi"
    engine.submit_text("phir se bolo")
    engine.process_pending_wake()
    assert engine.tts.spoken[-1] == answer
    assert not engine.ai.calls


def test_language_selection_cannot_mutate_an_active_transcription():
    engine = _make_engine(cooldown_seconds=0)
    engine.startup()
    assert engine.set_language_mode("hi")
    engine.request_listen()
    assert not engine.set_language_mode("en")
    assert engine.language_mode == "hi"


def test_recognition_uses_transcription_not_english_translation():
    seen = []
    stt = STTService(language="auto")
    def recognize(audio, **kwargs):
        seen.append(kwargs)
        return [SimpleNamespace(text="मुझे Python समझाओ")], SimpleNamespace(language="hi")
    stt._model = SimpleNamespace(transcribe=recognize)
    assert "Python" in stt.transcribe(np.ones(16000, dtype=np.int16) * 1500)
    assert seen[0]["language"] is None and seen[0]["task"] == "transcribe"
    assert "हिंदी" in seen[0]["initial_prompt"] and stt.last_language == "hi"


def test_hinglish_uses_hindi_voice_and_english_uses_english_voice(monkeypatch, tmp_path):
    import asyncio
    import edge_tts
    voices = []
    class Communicate:
        def __init__(self, *, text, voice):
            voices.append(voice)
        async def save(self, path):
            from pathlib import Path
            Path(path).write_bytes(b"voice")
    monkeypatch.setattr(edge_tts, "Communicate", Communicate)
    tts = TTSService(cache_dir=tmp_path)
    async def check():
        tts.language_hint = "hi"
        path = await tts._synthesize_async("Haan yaar, Python easy hai.")
        path.unlink()
        tts.language_hint = "en"
        path = await tts._synthesize_async("Python is a programming language.")
        path.unlink()
    asyncio.run(check())
    assert voices == [tts.hindi_voice, tts.voice]


def test_hinglish_greeting_sets_first_wake_and_retry_language():
    from tests.test_engine import FakeRecorder
    engine = _make_engine(recorder=FakeRecorder(audio=None), cooldown_seconds=0)
    engine.startup_greeting = "Hey! मैं ready हूँ।"
    engine.startup()
    engine._on_wake()
    engine.process_pending_wake()
    assert engine.tts.spoken[1] == "हाँ, बोलो।"
    assert "सुनाई नहीं दिया" in engine.tts.spoken[-1]
    assert engine.tts.language_hint == "hi"
    assert not engine.ai.calls


def test_casual_local_feedback_keeps_the_language_switch_and_error_information():
    from app.assistant.language import localize
    engine = _make_engine(cooldown_seconds=0, on_event=lambda *event: None)
    engine.startup()
    engine.submit_text("meri language mein baat karo")
    engine.process_pending_wake()
    assert engine.language_mode == "auto"
    assert "Hindi-English mix" in engine.tts.spoken[-1]
    message = localize("My Gemini access was denied. Please check the API key and its permissions.", "hi")
    assert "API key" in message and "permissions" in message
    assert "कीजिए" not in message
