"""Desktop/engine integration: real queues and Qt widgets, fake cloud/audio."""
import time
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel

from app.assistant.states import State
from app.desktop import JarvisWindow
from tests.test_engine import _make_engine


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def wait_until(qt_app, predicate, seconds=3):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        qt_app.processEvents()
        if predicate():
            return
        QTest.qWait(10)
    assert predicate()


def test_manual_talk_emits_transcript_and_reply_without_blocking():
    events = []
    engine = _make_engine(cooldown_seconds=0, on_event=lambda *e: events.append(e))
    engine.startup()
    assert engine.request_listen()
    assert not engine.request_listen()
    assert engine.recorder.calls == 0
    engine.process_pending_wake()
    messages = [payload for name, payload in events if name == "message"]
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[0]["text"] == "what is Python"
    assert ("state", "TRANSCRIBING") in events


def test_pause_closes_wake_stream_and_blocks_voice_but_allows_text():
    engine = _make_engine(cooldown_seconds=0)
    engine.startup()
    assert engine.set_listening_enabled(False)
    assert not engine.request_listen()
    engine.process_controls()
    assert engine.wake.stopped
    assert engine.submit_text("What is 12.5 percent of 240?")
    assert not engine.submit_text("Another question")
    engine.process_pending_wake()
    assert engine.recorder.calls == 0
    assert "30" in engine.context.last_assistant()
    assert not engine.wake.enabled
    assert engine.set_listening_enabled(True)
    engine.process_controls()
    assert engine.wake.enabled
    assert engine.request_listen()


def test_clear_rejected_mid_turn_and_clears_memory_when_ready():
    engine = _make_engine(cooldown_seconds=0)
    engine.startup()
    engine.context.add_turn("Hello", "Hi")
    engine.submit_text("What time is it?")
    assert not engine.clear_conversation()
    engine.process_pending_wake()
    assert engine.clear_conversation()
    assert len(engine.context) == 1


def test_muted_reply_is_still_visible_and_retained_in_context():
    events = []
    engine = _make_engine(cooldown_seconds=0, on_event=lambda *e: events.append(e))
    engine.startup()
    engine.set_speech_enabled(False)
    engine.submit_text("Explain Python")
    engine.process_pending_wake()
    assert not engine.tts.spoken
    assert engine.context.last_assistant()
    assert any(name == "message" and value["role"] == "assistant" for name, value in events)


def test_speaker_failure_is_visible_without_losing_answer():
    events = []
    engine = _make_engine(cooldown_seconds=0, on_event=lambda *e: events.append(e))
    engine.startup()
    engine.tts.speak = lambda text: False
    engine.submit_text("Explain Python")
    engine.process_pending_wake()
    assert engine.context.last_assistant()
    assert any(name == "notice" and "playback failed" in value for name, value in events)


def factory_for(engine, tmp_path):
    def factory(callback):
        engine.on_event = callback
        engine.tts.prewarm = lambda phrases: None
        return engine, SimpleNamespace(hotkey_exit="Ctrl+Shift+J", logs_dir=tmp_path)
    return factory


@pytest.fixture
def window(qt_app, tmp_path, monkeypatch):
    monkeypatch.setattr("app.desktop_worker.EmergencyHotkey.start", lambda self: True)
    monkeypatch.setattr("app.desktop_worker.EmergencyHotkey.stop", lambda self: None)
    engine = _make_engine(cooldown_seconds=0, continuous_without_wake=False)
    prefs = QSettings(str(tmp_path / "ui.ini"), QSettings.Format.IniFormat)
    w = JarvisWindow(factory_for(engine, tmp_path), preferences=prefs)
    w.show()
    wait_until(qt_app, lambda: w.current_state == "STANDBY")
    w.show_controls(True)
    wait_until(qt_app, lambda: w.controls.width() >= 275)
    yield w
    w.close()
    wait_until(qt_app, lambda: not w.worker.isRunning())
    qt_app.processEvents()


def test_desktop_buttons_drive_engine_and_render_plain_text(qt_app, window):
    window.input.setText("What is 12.5 percent of 240?")
    QTest.mouseClick(window.send, Qt.MouseButton.LeftButton)
    wait_until(qt_app, lambda: len(window.message_widgets) == 2 and window.current_state == "STANDBY"
               and not window.message_widgets[-1].findChild(QLabel, "message").timer.isActive())
    assert "30" in window.message_widgets[-1].findChild(QLabel, "message").text()
    assert not window.input.text()
    window.add_message("assistant", '<script>alert("hello")</script> नमस्ते')
    message = window.message_widgets[-1].findChild(QLabel, "message")
    assert message.textFormat() == Qt.TextFormat.PlainText
    QTest.mouseClick(window.clear, Qt.MouseButton.LeftButton)
    wait_until(qt_app, lambda: not window.message_widgets)
    assert len(window.worker.engine.context) == 1


def test_desktop_mic_pause_resume_and_talk(qt_app, window):
    QTest.mouseClick(window.pause, Qt.MouseButton.LeftButton)
    wait_until(qt_app, lambda: window.paused)
    assert not window.talk.isEnabled() and window.input.isEnabled()
    assert "paused" in window.badge.text()
    QTest.mouseClick(window.pause, Qt.MouseButton.LeftButton)
    wait_until(qt_app, lambda: not window.paused)
    QTest.mouseClick(window.talk, Qt.MouseButton.LeftButton)
    wait_until(qt_app, lambda: len(window.message_widgets) == 2)
    assert window.worker.engine.recorder.calls == 1


def test_closing_window_stops_worker_and_microphone(qt_app, window):
    window.close()
    wait_until(qt_app, lambda: not window.worker.isRunning())
    assert window.worker.engine.wake.stopped
    assert window.worker.engine.recorder.stopped


def test_hearing_profile_persists_and_voice_command_updates_control(qt_app, window):
    window.hearing.setCurrentIndex(window.hearing.findData("noisy"))
    wait_until(qt_app, lambda: window.preferences.value("hearing_profile") == "noisy")
    assert window.worker.engine.hearing_profile == "noisy"
    window._send("soft voice mode")
    wait_until(qt_app, lambda: window.current_state == "STANDBY" and
               window.preferences.value("hearing_profile") == "soft")
    assert window.hearing.currentData() == "soft"
    assert not window.worker.engine.ai.calls


def test_language_preference_and_voice_switch_update_ui(qt_app, window):
    window.language.setCurrentIndex(window.language.findData("hi"))
    wait_until(qt_app, lambda: window.preferences.value("language_mode") == "hi")
    assert window.worker.engine.stt.language == "hi"
    window._send("speak English")
    wait_until(qt_app, lambda: window.current_state == "STANDBY" and window.language.currentData() == "en")
    assert window.preferences.value("language_mode") == "en"
    window._send("match my language")
    wait_until(qt_app, lambda: window.current_state == "STANDBY" and window.language.currentData() == "auto")
    assert window.worker.engine.stt.language is None


def test_mic_level_connection_and_pause_status(qt_app, window):
    window.on_event("microphone", False)
    assert "disconnected" in window.badge.text().lower()
    window.on_event("microphone", True)
    window.on_event("state", "LISTENING")
    window.on_event("audio", {"source": "recording", "level": 64, "active": True})
    assert window.mic_meter.value() == 64 and window.orb.audio_level == .64
    # A queued standby frame cannot overwrite recording feedback.
    window.on_event("audio", {"source": "wake", "level": 5, "active": False})
    assert window.mic_meter.value() == 64
    window.on_event("state", "STANDBY")
    window.on_event("listening", False)
    window.on_event("audio", {"source": "wake", "level": 80, "active": False})
    assert window.mic_meter.value() == 0 and "paused" in window.mic_status.text()


def test_escape_cancels_busy_turn_without_losing_typed_draft(qt_app, window):
    import threading
    entered, release = threading.Event(), threading.Event()
    def delayed(messages):
        entered.set()
        release.wait(3)
        return "Too late"
    window.worker.engine.ai.chat = delayed
    window._send("Tell me a story")
    wait_until(qt_app, lambda: entered.is_set() and window.current_state == "THINKING")
    window.input.setText("Keep my next question")
    assert window.input.isEnabled() and not window.send.isEnabled()
    # Dispatch the real shortcut even when the text field has focus.
    window.activateWindow()
    window.input.setFocus()
    QTest.qWait(30)
    QTest.keyClick(window.input, Qt.Key.Key_Escape)
    try:
        wait_until(qt_app, lambda: window.cancelling)
    finally:
        release.set()
    wait_until(qt_app, lambda: window.current_state == "STANDBY")
    assert window.input.text() == "Keep my next question"
    assert len(window.worker.engine.context) == 1


def test_startup_failure_stays_visible_and_retry_recovers(qt_app, window):
    # Finish the first worker, then start a fresh window with one failing load.
    attempts = []
    good = window.factory
    def factory(callback):
        attempts.append(True)
        if len(attempts) == 1:
            raise RuntimeError("missing audio model")
        engine = _make_engine(cooldown_seconds=0, continuous_without_wake=False)
        return factory_for(engine, window.logs_dir)(callback)
    failed = JarvisWindow(factory, preferences=window.preferences)
    failed.show()
    try:
        wait_until(qt_app, lambda: failed.failed and failed.retry.isVisible())
        assert failed.isVisible() and not failed.talk.isEnabled()
        QTest.mouseClick(failed.retry, Qt.MouseButton.LeftButton)
        wait_until(qt_app, lambda: failed.current_state == "STANDBY")
        assert failed.talk.isEnabled() and not failed.failed
    finally:
        failed.close()
        wait_until(qt_app, lambda: not failed.worker.isRunning())


def test_paused_microphone_is_not_reenabled_after_text_answer(qt_app, window):
    QTest.mouseClick(window.pause, Qt.MouseButton.LeftButton)
    wait_until(qt_app, lambda: window.paused)
    window.input.setText("What time is it?")
    QTest.keyClick(window.input, Qt.Key.Key_Return)
    wait_until(qt_app, lambda: len(window.message_widgets) == 2 and window.current_state == "STANDBY")
    assert window.paused and not window.worker.engine.wake.enabled


def test_hud_starts_with_tools_and_chat_hidden(qt_app, tmp_path):
    prefs = QSettings(str(tmp_path / "clean.ini"), QSettings.Format.IniFormat)
    w = JarvisWindow(None, autostart=False, preferences=prefs)
    w.show()
    qt_app.processEvents()
    try:
        assert not w.controls.isVisible()
        assert not w.chat_card.isVisible()
        assert w.orb.isVisible()
        w.add_message("assistant", "Hello")
        assert not w.chat_card.isVisible()
        w.add_message("user", "Hello Jarvis")
        assert w.chat_card.isVisible()
        w.on_event("state", "STANDBY")
        w._idle_chat()
        assert not w.chat_card.isVisible()
    finally:
        w.close()


@pytest.mark.parametrize("phrase,action", [
    ("Show controls", "show_controls"), ("controls dikhao", "show_controls"),
    ("सेटिंग्स दिखाओ", "show_controls"), ("Jarvis, hide controls please", "hide_controls"),
    ("chat dikhao", "show_chat"), ("चैट छुपाओ", "hide_chat"), ("clear chat", "clear_chat"),
])
def test_voice_ui_commands_are_local_and_dont_pollute_ai_context(phrase, action):
    events = []
    engine = _make_engine(cooldown_seconds=0, on_event=lambda *e: events.append(e))
    engine.startup()
    engine.submit_text(phrase)
    engine.process_pending_wake()
    assert ("ui", {"action": action}) in events
    assert not engine.ai.calls
    assert len(engine.context) == 1


def test_discussing_controls_does_not_trigger_them():
    from app.assistant.commands import desktop_command
    assert desktop_command("Explain how flight controls work") is None
    assert desktop_command("Write code to hide controls in Python") is None


def test_voice_hide_chat_keeps_acknowledgement_hidden(qt_app, window):
    window.worker.submit("hide chat")
    wait_until(qt_app, lambda: len(window.message_widgets) == 2 and window.current_state == "STANDBY")
    assert not window.chat_card.isVisible()
    window.worker.submit("show controls")
    wait_until(qt_app, lambda: len(window.message_widgets) == 4)
    assert window.controls_open


def test_chat_clear_by_voice_clears_actual_memory(qt_app, window):
    window.worker.engine.context.add_turn("Remember this", "I will")
    window.worker.submit("clear chat")
    wait_until(qt_app, lambda: window.current_state == "STANDBY" and len(window.worker.engine.context) == 1)
    assert not window.chat_card.isVisible()
