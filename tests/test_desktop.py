"""Tests for the minimal floating-orb desktop shell."""
import pytest
from PySide6.QtCore import QPoint, QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.desktop import BUSY_STATES, JarvisWindow


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_desktop_is_only_a_small_floating_orb(qt_app, tmp_path):
    prefs = QSettings(str(tmp_path / "orb.ini"), QSettings.Format.IniFormat)
    window = JarvisWindow(None, autostart=False, preferences=prefs)
    window.show()
    qt_app.processEvents()
    try:
        assert window.size().width() == 180
        assert window.size().height() == 180
        assert window.orb.isVisible()
        assert window.windowFlags() & Qt.WindowType.FramelessWindowHint
        assert not hasattr(window, "chat_card")
        assert not hasattr(window, "controls")
        assert not hasattr(window, "input")
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
        assert "Say anything" in window.orb.toolTip()
        window.on_event("audio", {"level": 72, "source": "recording"})
        assert window.orb.audio_level == pytest.approx(0.72)
        window.on_event("state", "THINKING")
        assert window.current_state == "THINKING"
        assert "Thinking" in window.orb.toolTip()
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


def test_orb_can_be_dragged(qt_app, tmp_path):
    prefs = QSettings(str(tmp_path / "drag.ini"), QSettings.Format.IniFormat)
    window = JarvisWindow(None, autostart=False, preferences=prefs)
    window.show()
    qt_app.processEvents()
    start = window.pos()
    center = window.orb.rect().center()
    QTest.mousePress(window.orb, Qt.MouseButton.LeftButton, pos=center)
    end = center + QPoint(20, 12)
    QTest.mouseMove(window.orb, end, 20)
    QTest.mouseRelease(window.orb, Qt.MouseButton.LeftButton, pos=end)
    assert window.pos() != start
    window.close()