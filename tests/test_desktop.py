"""Tests for the holographic desktop assistant console."""
import threading

import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QLineEdit, QMessageBox

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
        assert window.hands_free_toggle.isVisible()
        assert window.input_device_combo.isVisible()
        assert not window.orb.draggable
    finally:
        window.close()


def test_clear_memory_requires_confirmation(qt_app, tmp_path, monkeypatch):
    class Worker:
        cleared = False

        def clear(self):
            self.cleared = True
            return True

    prefs = QSettings(str(tmp_path / "memory-clear.ini"), QSettings.Format.IniFormat)
    window = JarvisWindow(None, autostart=False, preferences=prefs)
    worker = Worker()
    window.worker = worker
    monkeypatch.setattr(
        "app.desktop.QMessageBox.question",
        lambda *_args: QMessageBox.StandardButton.No,
    )
    window._clear_conversation()
    assert not worker.cleared
    window.worker = None
    window.close()


def test_file_content_sharing_is_denied_by_default(qt_app, tmp_path, monkeypatch):
    prefs = QSettings(str(tmp_path / "file-consent.ini"), QSettings.Format.IniFormat)
    window = JarvisWindow(None, autostart=False, preferences=prefs)
    request = {"path": "C:/outside/private.txt", "decision": {}, "answered": threading.Event()}
    monkeypatch.setattr(
        "app.desktop.QMessageBox.question",
        lambda *_args: QMessageBox.StandardButton.No,
    )
    window._confirm_file_content_share(request)
    assert request["decision"]["approved"] is False
    assert request["answered"].is_set()
    window.close()


def test_file_edit_preview_cancel_never_writes(qt_app, tmp_path, monkeypatch):
    class Worker:
        def __init__(self):
            self.saved = []

        def save_file_draft(self, *args):
            self.saved.append(args)
            return "saved"

    prefs = QSettings(str(tmp_path / "file-preview.ini"), QSettings.Format.IniFormat)
    window = JarvisWindow(None, autostart=False, preferences=prefs)
    worker = Worker()
    window.worker = worker
    monkeypatch.setattr(
        "app.desktop.QDialog.exec",
        lambda _dialog: QDialog.DialogCode.Rejected,
    )
    window._confirm_file_edit({
        "path": "C:/outside/draft.txt",
        "content": "review me",
        "expected_sha256": None,
        "user_text": "create file",
        "outside_project": True,
    })
    assert worker.saved == []
    assert "No file was changed" in window.notice_label.text()
    window.worker = None
    window.close()


def test_file_edit_preview_requires_and_obeys_explicit_save_approval(qt_app, tmp_path, monkeypatch):
    class Worker:
        def __init__(self):
            self.saved = []

        def save_file_draft(self, *args):
            self.saved.append(args)
            return "Saved the approved draft."

    prefs = QSettings(str(tmp_path / "file-approve.ini"), QSettings.Format.IniFormat)
    window = JarvisWindow(None, autostart=False, preferences=prefs)
    worker = Worker()
    window.worker = worker
    monkeypatch.setattr(
        "app.desktop.QDialog.exec",
        lambda _dialog: QDialog.DialogCode.Accepted,
    )
    window._confirm_file_edit({
        "path": "C:/outside/draft.txt",
        "content": "reviewed content",
        "expected_sha256": None,
        "user_text": "create file",
        "outside_project": True,
    })
    assert worker.saved == [(
        "create file",
        "C:/outside/draft.txt",
        "reviewed content",
        None,
    )]
    assert "approved" in window.notice_label.text()
    window.worker = None
    window.close()


def test_research_sources_render_as_clickable_links(qt_app, tmp_path):
    from app.assistant.research import ResearchResult

    prefs = QSettings(str(tmp_path / "sources.ini"), QSettings.Format.IniFormat)
    window = JarvisWindow(None, autostart=False, preferences=prefs)
    window._append_research_sources([
        ResearchResult("Official source", "https://example.com", "snippet")
    ])
    links = [label for label in window.messages_widget.findChildren(QLabel)
             if "Official source" in label.text()]
    assert len(links) == 1
    assert links[0].openExternalLinks()
    assert "https://example.com" in links[0].text()
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


def test_power_action_dialog_defaults_to_cancel_and_does_not_execute(qt_app, tmp_path, monkeypatch):
    class Worker:
        def __init__(self):
            self.actions = []

        def confirm_system_action(self, action):
            self.actions.append(action)
            return "scheduled"

    prefs = QSettings(str(tmp_path / "power-cancel.ini"), QSettings.Format.IniFormat)
    window = JarvisWindow(None, autostart=False, preferences=prefs)
    worker = Worker()
    window.worker = worker
    monkeypatch.setattr(
        "app.desktop.QMessageBox.warning",
        lambda *_args: QMessageBox.StandardButton.No,
    )

    window._confirm_system_action({
        "action": "shutdown_windows",
        "message": "Do you want to shut down Windows?",
    })

    assert worker.actions == []
    assert "cancelled" in window.notice_label.text().lower()
    window.worker = None
    window.close()


def test_power_action_only_runs_after_explicit_dialog_approval(qt_app, tmp_path, monkeypatch):
    class Worker:
        def __init__(self):
            self.actions = []

        def confirm_system_action(self, action):
            self.actions.append(action)
            return "Windows restart is scheduled in 60 seconds."

    prefs = QSettings(str(tmp_path / "power-confirm.ini"), QSettings.Format.IniFormat)
    window = JarvisWindow(None, autostart=False, preferences=prefs)
    worker = Worker()
    window.worker = worker
    monkeypatch.setattr(
        "app.desktop.QMessageBox.warning",
        lambda *_args: QMessageBox.StandardButton.Yes,
    )

    window._confirm_system_action({
        "action": "restart_windows",
        "message": "Do you want to restart Windows?",
    })

    assert worker.actions == ["restart_windows"]
    assert "60 seconds" in window.notice_label.text()
    window.worker = None
    window.close()