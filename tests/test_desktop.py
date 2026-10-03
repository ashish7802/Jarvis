"""Tests for the minimal floating-orb desktop shell."""
import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication, QLineEdit

from app.assistant.commands import desktop_command
from app.assistant.language import localize
from app.desktop import BUSY_STATES, JarvisWindow


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_desktop_shows_original_holographic_assistant_console(qt_app, tmp_path):
    prefs = QSettings(str(tmp_path / "hud.ini"), QSettings.Format.IniFormat)
    window = JarvisWindow(None, autostart=False, preferences=prefs)
    window.show()
    qt_app.processEvents()
    try:
        assert window.size().width() >= 1120
        assert window.size().height() >= 700
        assert window.orb.isVisible()
        assert not window.windowFlags() & Qt.WindowType.FramelessWindowHint
        assert window.system_panel.isVisible()
        assert window.message_scroll.isVisible()
        assert isinstance(window.input, QLineEdit)
        assert window.talk_button.isVisible()
        assert not window.orb.draggable
    finally:
        window.close()


def test_orb_state_and_audio_feedback(qt_app, tmp_path):
    prefs = QSettings(str(tmp_path / "state.ini"), QSettings.Format.IniFormat)
    window = JarvisWindow(None, autostart=False, preferences=prefs)
    window.show()
    qt_app.processEvents()
    try:
        window.on_event("state", "LISTENING")
        assert window.current_state == "LISTENING"
        assert window.orb.mode == "LISTENING"
        assert "Say anything" in window.core_state_label.text()
        window.on_event("audio", {"level": 72, "source": "recording"})
        assert window.orb.audio_level == pytest.approx(0.72)
        window.on_event("state", "THINKING")
        assert window.current_state == "THINKING"
        assert "Thinking" in window.core_state_label.text()
        assert "LISTENING" in BUSY_STATES
    finally:
        window.close()


def test_orb_click_delegates_to_worker_when_ready(qt_app, tmp_path):
    class Worker:
        def __init__(self):
            self.listen_calls = 0

        def listen(self):
            self.listen_calls += 1
            return True

    prefs = QSettings(str(tmp_path / "click.ini"), QSettings.Format.IniFormat)
    window = JarvisWindow(None, autostart=False, preferences=prefs)
    worker = Worker()
    window.worker = worker
    window.current_state = "STANDBY"
    window._listen()
    assert worker.listen_calls == 1
    window.worker = None
    window.close()


def test_conversation_events_render_in_the_chat_panel(qt_app, tmp_path):
    prefs = QSettings(str(tmp_path / "messages.ini"), QSettings.Format.IniFormat)
    window = JarvisWindow(None, autostart=False, preferences=prefs)
    window.on_event("message", {"role": "user", "text": "Hello Jarvis"})
    window.on_event("message", {"role": "assistant", "text": "Hello! I'm here."})
    labels = [label.text() for label in window.messages_widget.findChildren(type(window.core_state_label))]
    assert "Hello Jarvis" in labels
    assert "Hello! I'm here." in labels
    window.on_event("notice", "The microphone is unavailable.")
    assert not window.notice_label.isHidden()
    assert "microphone" in window.notice_label.text()
    window.close()


def test_text_input_submits_to_the_worker(qt_app, tmp_path):
    class Worker:
        submitted = None

        def submit(self, text):
            self.submitted = text
            return True

    prefs = QSettings(str(tmp_path / "input.ini"), QSettings.Format.IniFormat)
    window = JarvisWindow(None, autostart=False, preferences=prefs)
    worker = Worker()
    window.worker = worker
    window.input.setText("  What time is it?  ")
    window._send_text()
    assert worker.submitted == "What time is it?"
    assert window.input.text() == ""
    window.worker = None
    window.close()


def test_spoken_panel_hints_match_the_visible_console():
    expected_terms = {
        "show controls": "left",
        "hide controls": "minimize",
        "show chat": "center",
        "hide chat": "Clear",
    }
    for command, expected in expected_terms.items():
        action, reply = desktop_command(command)
        assert action in {"show_controls", "hide_controls", "show_chat", "hide_chat"}
        assert expected in reply
        assert localize(reply, "hi") != reply