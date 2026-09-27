"""Minimal native desktop shell for the voice assistant.

The normal desktop surface is intentionally just one floating orb. Jarvis is
used by voice, so a dashboard full of controls and a transcript only gets in
the way. A small right-click menu keeps the few safety and recovery actions
available without turning the app back into a control panel.
"""
from __future__ import annotations

from pathlib import Path
import ctypes
from ctypes import wintypes
import os
import sys

from PySide6.QtCore import Qt, QSettings, QTimer, Slot
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QMainWindow, QMenu

from app.hud_widgets import STYLE, VoiceOrb, app_icon
from app.desktop_worker import AssistantWorker


TITLE = "JARVIS"
BUSY_STATES = {
    "WAKE_DETECTED",
    "ACKNOWLEDGING",
    "LISTENING",
    "TRANSCRIBING",
    "THINKING",
    "SPEAKING",
}
STATE_HINTS = {
    "STARTING": "Starting Jarvis…",
    "STANDBY": "Click to talk · drag to move · right-click for options",
    "WAKE_DETECTED": "I’m listening",
    "ACKNOWLEDGING": "I’m listening",
    "LISTENING": "Say anything",
    "TRANSCRIBING": "Understanding you…",
    "THINKING": "Thinking…",
    "SPEAKING": "Replying…",
    "PAUSED": "Microphone paused",
    "ERROR": "Jarvis needs attention",
    "SHUTTING_DOWN": "Closing Jarvis…",
}


class JarvisWindow(QMainWindow):
    """A small always-on-top voice orb with no persistent dashboard UI."""

    def __init__(self, factory, *, autostart=True, preferences=None):
        super().__init__()
        self.factory = factory
        self.worker = None
        self.preferences = preferences if preferences is not None else QSettings("Jarvis", "Desktop")
        self.closing = False
        self.failed = False
        self.paused = False
        self.pause_pending = False
        self.microphone_connected = None
        self.cancelling = False
        self.current_state = "STARTING"
        self.wake_backend = "disabled"
        self.logs_dir = Path(os.environ.get("APPDATA", ".")) / "JARVIS" / "logs"
        self.voice_enabled = self.preferences.value("spoken_replies", True, type=bool)
        self.screen_read_enabled = self.preferences.value(
            "screen_read_enabled", False, type=bool
        )

        self.setWindowTitle(TITLE)
        self.setWindowIcon(app_icon())
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(180, 180)
        self.setStyleSheet(STYLE)
        self._build_ui()
        self._place_orb()

        self.talk_shortcut = QShortcut(QKeySequence("Ctrl+Space"), self)
        self.talk_shortcut.activated.connect(self._listen)
        self.cancel_shortcut = QShortcut(QKeySequence("Escape"), self)
        self.cancel_shortcut.activated.connect(self._cancel_turn)
        if autostart:
            QTimer.singleShot(0, self.start_assistant)

    def _build_ui(self):
        self.orb = VoiceOrb(self)
        self.orb.setFixedSize(170, 170)
        self.orb.activated.connect(self._listen)
        self.orb.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.orb.customContextMenuRequested.connect(
            lambda point: self._show_menu(self.orb.mapToGlobal(point))
        )
        self.setCentralWidget(self.orb)
        self._refresh_state()

    def _place_orb(self):
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        self.move(area.right() - self.width() - 28, area.top() + 64)

    def _show_menu(self, position):
        menu = QMenu(self)
        menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        talk = QAction("Talk to Jarvis", menu)
        talk.triggered.connect(self._listen)
        talk.setEnabled(self.current_state == "STANDBY" and not self.paused)
        menu.addAction(talk)

        cancel = QAction("Stop current reply", menu)
        cancel.triggered.connect(self._cancel_turn)
        cancel.setEnabled(self.current_state in BUSY_STATES and not self.cancelling)
        menu.addAction(cancel)

        menu.addSeparator()
        pause = QAction("Resume microphone" if self.paused else "Pause microphone", menu)
        pause.triggered.connect(self._toggle_pause)
        pause.setEnabled(
            self.current_state == "STANDBY" and not self.pause_pending
        )
        menu.addAction(pause)

        voice = QAction("Voice replies", menu)
        voice.setCheckable(True)
        voice.setChecked(self.voice_enabled)
        voice.toggled.connect(self._toggle_voice)
        voice.setEnabled(not self.closing and not self.failed)
        menu.addAction(voice)

        screen_read = QAction("Allow screen reading", menu)
        screen_read.setCheckable(True)
        screen_read.setChecked(self.screen_read_enabled)
        screen_read.toggled.connect(self._toggle_screen_read)
        screen_read.setEnabled(
            self.current_state == "STANDBY" and not self.closing and not self.failed
        )
        menu.addAction(screen_read)

        menu.addSeparator()
        logs = QAction("Open diagnostic logs", menu)
        logs.triggered.connect(self._open_logs)
        menu.addAction(logs)
        exit_action = QAction("Quit Jarvis", menu)
        exit_action.triggered.connect(self.close)
        menu.addAction(exit_action)
        menu.exec(position)

    @Slot()
    def start_assistant(self):
        if self.closing or (self.worker is not None and self.worker.isRunning()):
            return
        if self.worker is not None:
            self.worker.deleteLater()
        self.failed = False
        self.paused = False
        self.pause_pending = False
        self.current_state = "STARTING"
        self._refresh_state()
        self.worker = AssistantWorker(
            self.factory,
            self.voice_enabled,
            self,
            hearing_profile=self.preferences.value("hearing_profile"),
            language_mode=self.preferences.value("language_mode"),
            screen_read_enabled=self.preferences.value(
                "screen_read_enabled", False, type=bool
            ),
        )
        self.worker.event.connect(self.on_event)
        self.worker.finished.connect(self._worker_finished)
        self.worker.start()

    @Slot(str, object)
    def on_event(self, event, payload):
        if event == "state":
            if not self.failed:
                self.current_state = payload
            if payload == "STANDBY":
                self.cancelling = False
            self._refresh_state()
        elif event == "audio":
            if self.paused or self.closing:
                return
            self.orb.audio_level = payload.get("level", 0) / 100
            self.orb.update()
        elif event == "microphone":
            self.microphone_connected = bool(payload)
            self._refresh_state()
        elif event == "progress":
            self.orb.setToolTip(str(payload))
        elif event == "notice":
            self.orb.setToolTip(str(payload))
        elif event == "fatal":
            self.failed = True
            self.current_state = "ERROR"
            self.orb.setToolTip(str(payload))
            self._refresh_state()
        elif event == "listening":
            self.paused = not payload
            self.pause_pending = False
            if self.paused:
                self.orb.audio_level = 0
            self._refresh_state()
        elif event == "configured":
            self.logs_dir = Path(payload["logs"])
            self.wake_backend = payload["wake"]
            self._refresh_state()
        elif event == "screen_read":
            self.screen_read_enabled = bool(payload)
            self.preferences.setValue("screen_read_enabled", self.screen_read_enabled)

    def _refresh_state(self):
        mode = "SHUTTING_DOWN" if self.closing else self.current_state
        if mode == "STANDBY" and self.paused:
            mode = "PAUSED"
        if mode == "STANDBY" and self.microphone_connected is False:
            hint = "Microphone disconnected · right-click to retry or quit"
        elif mode == "STANDBY" and self.wake_backend == "disabled":
            hint = "Click to talk · right-click for options"
        else:
            hint = STATE_HINTS.get(mode, "Jarvis")
        self.orb.mode = mode
        self.orb.setAccessibleName(
            "Stop current Jarvis turn"
            if mode in BUSY_STATES
            else "Talk to Jarvis"
        )
        self.orb.setToolTip(hint)
        self.orb.update()

    def _listen(self):
        if self.current_state in BUSY_STATES:
            self._cancel_turn()
            return
        if self.paused:
            self._toggle_pause()
            return
        if self.worker is not None and not self.worker.listen():
            self.on_event("notice", "Jarvis is still getting ready. Try again in a moment.")

    def _cancel_turn(self):
        if self.worker is not None and self.worker.cancel_turn():
            self.cancelling = True
            self._refresh_state()

    def _toggle_pause(self):
        if self.worker is not None and self.worker.pause(not self.paused):
            self.pause_pending = True
        self._refresh_state()

    def _toggle_voice(self, enabled):
        self.voice_enabled = bool(enabled)
        self.preferences.setValue("spoken_replies", self.voice_enabled)
        if self.worker is not None:
            self.worker.set_voice(self.voice_enabled)

    def _toggle_screen_read(self, enabled):
        self.screen_read_enabled = bool(enabled)
        self.preferences.setValue("screen_read_enabled", self.screen_read_enabled)
        if self.worker is not None and not self.worker.set_screen_read_enabled(
            self.screen_read_enabled
        ):
            self.screen_read_enabled = bool(
                getattr(self.worker.engine, "screen_read_enabled", False)
            )

    def _open_logs(self):
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        if hasattr(os, "startfile"):
            os.startfile(str(self.logs_dir))
        else:
            self.orb.setToolTip(f"Logs are in {self.logs_dir}")

    @Slot()
    def _worker_finished(self):
        if self.closing:
            self.close()
        elif self.failed:
            self.orb.setToolTip("Jarvis could not start. Check the logs and restart.")
        else:
            self.close()

    def closeEvent(self, event):
        if self.worker is not None and self.worker.isRunning():
            event.ignore()
            if not self.closing:
                self.closing = True
                self._refresh_state()
                self.worker.request_stop()
            return
        event.accept()

    def showEvent(self, event):
        super().showEvent(event)
        if os.name == "nt":
            try:
                enabled = ctypes.c_int(1)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    wintypes.HWND(int(self.winId())),
                    20,
                    ctypes.byref(enabled),
                    ctypes.sizeof(enabled),
                )
            except OSError:
                pass


def activate_existing_window():
    if os.name != "nt":
        return
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    user32.FindWindowW.restype = wintypes.HWND
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    window = user32.FindWindowW(None, TITLE)
    if window:
        user32.ShowWindow(window, 9)
        user32.SetForegroundWindow(window)


def run_desktop(factory):
    if os.name == "nt":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "Jarvis.Desktop.Assistant"
        )
    app = QApplication(sys.argv[:1])
    app.setApplicationName("JARVIS")
    app.setStyle("Fusion")
    window = JarvisWindow(factory)
    window.show()
    return app.exec()