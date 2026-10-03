"""Native desktop console for the voice assistant."""
from __future__ import annotations

from pathlib import Path
import ctypes
from ctypes import wintypes
import os
import sys

from PySide6.QtCore import Qt, QSettings, QTimer, Slot
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QPushButton,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.hud_widgets import STYLE, HudBackground, VoiceOrb, app_icon
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
    "STANDBY": "Click the core or press Ctrl+Space to talk",
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
    """Native assistant console with voice, conversation, and system controls."""

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
        self.language_mode = self.preferences.value("language_mode", "auto")
        self.ai_provider = "Connecting…"

        self.setWindowTitle(TITLE)
        self.setWindowIcon(app_icon())
        self.resize(1360, 850)
        self.setMinimumSize(1120, 700)
        self.setStyleSheet(STYLE)
        self._build_ui()
        self._place_window()

        self.talk_shortcut = QShortcut(QKeySequence("Ctrl+Space"), self)
        self.talk_shortcut.activated.connect(self._listen)
        self.cancel_shortcut = QShortcut(QKeySequence("Escape"), self)
        self.cancel_shortcut.activated.connect(self._cancel_turn)
        if autostart:
            QTimer.singleShot(0, self.start_assistant)

    def _build_ui(self):
        surface = HudBackground(self)
        surface.setObjectName("surface")
        self.setCentralWidget(surface)
        root = QVBoxLayout(surface)
        root.setContentsMargins(28, 22, 28, 24)
        root.setSpacing(18)

        topbar = QHBoxLayout()
        topbar.setSpacing(14)
        brand_column = QVBoxLayout()
        brand_column.setSpacing(2)
        brand = QLabel("JARVIS")
        brand.setObjectName("brand")
        brand_column.addWidget(brand)
        tagline = QLabel("PERSONAL INTELLIGENCE  /  VOICE CONSOLE")
        tagline.setObjectName("eyebrow")
        brand_column.addWidget(tagline)
        topbar.addLayout(brand_column)
        topbar.addStretch(1)
        self.status_badge = QLabel("●  STARTING SYSTEM")
        self.status_badge.setObjectName("statusBadge")
        topbar.addWidget(self.status_badge)
        root.addLayout(topbar)

        body = QHBoxLayout()
        body.setSpacing(16)
        root.addLayout(body, 1)

        self.system_panel = QFrame()
        self.system_panel.setObjectName("panel")
        self.system_panel.setFixedWidth(252)
        system_layout = QVBoxLayout(self.system_panel)
        system_layout.setContentsMargins(18, 18, 18, 18)
        system_layout.setSpacing(13)
        system_title = QLabel("SYSTEM STATUS")
        system_title.setObjectName("eyebrow")
        system_layout.addWidget(system_title)
        self.provider_value = self._add_status_row(system_layout, "AI LINK", self.ai_provider)
        self.wake_value = self._add_status_row(system_layout, "WAKE WORD", "Loading…")
        self.mic_value = self._add_status_row(system_layout, "MICROPHONE", "Checking…")
        system_layout.addSpacing(8)
        self.voice_toggle = QCheckBox("Spoken replies")
        self.voice_toggle.setChecked(self.voice_enabled)
        self.voice_toggle.toggled.connect(self._toggle_voice)
        system_layout.addWidget(self.voice_toggle)
        self.screen_read_toggle = QCheckBox("Allow screen reading")
        self.screen_read_toggle.setChecked(self.screen_read_enabled)
        self.screen_read_toggle.toggled.connect(self._toggle_screen_read)
        system_layout.addWidget(self.screen_read_toggle)
        system_layout.addWidget(self._small_label("Language"))
        self.language_combo = QComboBox()
        for label, value in (("Auto detect", "auto"), ("English", "en"),
                             ("Hindi", "hi"), ("Hinglish", "hinglish")):
            self.language_combo.addItem(label, value)
        language_index = self.language_combo.findData(self.language_mode)
        self.language_combo.setCurrentIndex(max(0, language_index))
        self.language_combo.currentIndexChanged.connect(self._language_changed)
        system_layout.addWidget(self.language_combo)
        self.pause_button = QPushButton("Pause microphone")
        self.pause_button.clicked.connect(self._toggle_pause)
        system_layout.addWidget(self.pause_button)
        system_layout.addStretch(1)
        capabilities_title = QLabel("READY FOR")
        capabilities_title.setObjectName("eyebrow")
        system_layout.addWidget(capabilities_title)
        for capability in ("Natural conversation", "Reminders & notes", "Safe desktop actions"):
            item = QLabel("◦  " + capability)
            item.setObjectName("muted")
            system_layout.addWidget(item)
        self.logs_button = QPushButton("Open diagnostic logs")
        self.logs_button.setObjectName("quiet")
        self.logs_button.clicked.connect(self._open_logs)
        system_layout.addWidget(self.logs_button)
        body.addWidget(self.system_panel)

        conversation_panel = QFrame()
        conversation_panel.setObjectName("panel")
        conversation_layout = QVBoxLayout(conversation_panel)
        conversation_layout.setContentsMargins(18, 18, 18, 18)
        conversation_layout.setSpacing(12)
        conversation_header = QHBoxLayout()
        conversation_title = QLabel("CONVERSATION")
        conversation_title.setObjectName("eyebrow")
        conversation_header.addWidget(conversation_title)
        conversation_header.addStretch(1)
        clear_button = QPushButton("Clear")
        clear_button.setObjectName("quiet")
        clear_button.clicked.connect(self._clear_conversation)
        conversation_header.addWidget(clear_button)
        conversation_layout.addLayout(conversation_header)
        self.notice_label = QLabel()
        self.notice_label.setObjectName("notice")
        self.notice_label.setWordWrap(True)
        self.notice_label.hide()
        conversation_layout.addWidget(self.notice_label)
        self.message_scroll = QScrollArea()
        self.message_scroll.setWidgetResizable(True)
        self.message_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.message_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.messages_widget = QWidget()
        self.messages_widget.setObjectName("messages")
        self.messages_layout = QVBoxLayout(self.messages_widget)
        self.messages_layout.setContentsMargins(4, 6, 8, 6)
        self.messages_layout.setSpacing(10)
        self.messages_layout.addStretch(1)
        self.message_scroll.setWidget(self.messages_widget)
        conversation_layout.addWidget(self.message_scroll, 1)
        self._append_message(
            "assistant", "I'm online. Ask me anything, or use the voice control to speak."
        )
        input_row = QHBoxLayout()
        input_row.setSpacing(9)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Ask Jarvis anything…")
        self.input.returnPressed.connect(self._send_text)
        input_row.addWidget(self.input, 1)
        self.send_button = QPushButton("Send")
        self.send_button.setObjectName("primary")
        self.send_button.clicked.connect(self._send_text)
        input_row.addWidget(self.send_button)
        conversation_layout.addLayout(input_row)
        body.addWidget(conversation_panel, 1)

        core_panel = QFrame()
        core_panel.setObjectName("panel")
        core_panel.setFixedWidth(310)
        core_layout = QVBoxLayout(core_panel)
        core_layout.setContentsMargins(18, 18, 18, 18)
        core_layout.setSpacing(10)
        core_title = QLabel("ASSISTANT CORE")
        core_title.setObjectName("eyebrow")
        core_layout.addWidget(core_title)
        self.orb = VoiceOrb(self)
        self.orb.setFixedSize(270, 270)
        self.orb.draggable = False
        self.orb.activated.connect(self._listen)
        self.orb.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.orb.customContextMenuRequested.connect(
            lambda point: self._show_menu(self.orb.mapToGlobal(point))
        )
        core_layout.addWidget(self.orb, 0, Qt.AlignmentFlag.AlignHCenter)
        self.core_state_label = QLabel("Starting Jarvis…")
        self.core_state_label.setObjectName("heroTitle")
        self.core_state_label.setWordWrap(True)
        self.core_state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        core_layout.addWidget(self.core_state_label)
        self.core_hint_label = QLabel("VOICE CORE  ·  READY")
        self.core_hint_label.setObjectName("muted")
        self.core_hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        core_layout.addWidget(self.core_hint_label)
        core_layout.addSpacing(6)
        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.talk_button = QPushButton("Start talking")
        self.talk_button.setObjectName("primary")
        self.talk_button.clicked.connect(self._listen)
        actions.addWidget(self.talk_button, 1)
        self.cancel_button = QPushButton("Stop")
        self.cancel_button.setObjectName("quiet")
        self.cancel_button.clicked.connect(self._cancel_turn)
        actions.addWidget(self.cancel_button)
        core_layout.addLayout(actions)
        shortcut = QLabel("CTRL + SPACE  TALK     ·     ESC  STOP")
        shortcut.setObjectName("eyebrow")
        shortcut.setAlignment(Qt.AlignmentFlag.AlignCenter)
        core_layout.addWidget(shortcut)
        core_layout.addStretch(1)
        body.addWidget(core_panel)
        self._refresh_state()

    @staticmethod
    def _small_label(text):
        label = QLabel(text)
        label.setObjectName("muted")
        return label

    @staticmethod
    def _add_status_row(layout, title, value):
        row = QHBoxLayout()
        row.setSpacing(6)
        label = QLabel(title)
        label.setObjectName("eyebrow")
        value_label = QLabel(value)
        value_label.setObjectName("muted")
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(label, 1)
        row.addWidget(value_label)
        layout.addLayout(row)
        return value_label

    def _place_window(self):
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        self.move(area.center() - self.rect().center())

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
            self.mic_value.setText("Connected" if payload else "Disconnected")
            self._refresh_state()
        elif event == "progress":
            self.core_hint_label.setText(str(payload).upper())
        elif event == "notice":
            self.notice_label.setText(str(payload))
            self.notice_label.show()
        elif event == "fatal":
            self.failed = True
            self.current_state = "ERROR"
            self.notice_label.setText(str(payload))
            self.notice_label.show()
            self._refresh_state()
        elif event == "configured":
            self.logs_dir = Path(payload["logs"])
            self.wake_backend = payload["wake"]
            self.ai_provider = payload["provider"]
            self.provider_value.setText(self.ai_provider.upper())
            self.wake_value.setText(self.wake_backend.replace("_", " ").title())
            if self.wake_backend == "disabled":
                self.mic_value.setText("Click-to-talk")
            self._refresh_state()
        elif event == "message":
            self._append_message(payload.get("role", "assistant"), payload.get("text", ""))
        elif event == "confirmation_requested":
            self._confirm_system_action(payload)
        elif event == "clear":
            self._clear_messages()
        elif event == "listening":
            self.paused = not payload
            self.pause_pending = False
            self.pause_button.setText("Resume microphone" if self.paused else "Pause microphone")
            if self.paused:
                self.orb.audio_level = 0
            self._refresh_state()
        elif event == "screen_read":
            self.screen_read_enabled = bool(payload)
            self.preferences.setValue("screen_read_enabled", self.screen_read_enabled)
            self.screen_read_toggle.blockSignals(True)
            self.screen_read_toggle.setChecked(self.screen_read_enabled)
            self.screen_read_toggle.blockSignals(False)

    def _refresh_state(self):
        mode = "SHUTTING_DOWN" if self.closing else self.current_state
        if mode == "STANDBY" and self.paused:
            mode = "PAUSED"
        if mode == "STANDBY" and self.microphone_connected is False:
            hint = "Microphone disconnected · right-click to retry or quit"
        elif mode == "STANDBY" and self.wake_backend == "disabled":
            hint = "Click the core or press Ctrl+Space to talk"
        else:
            hint = STATE_HINTS.get(mode, "Jarvis")
        self.orb.mode = mode
        self.orb.setAccessibleName("Stop current Jarvis turn" if mode in BUSY_STATES else "Talk to Jarvis")
        self.orb.setToolTip(hint)
        self.core_state_label.setText(hint)
        self.core_hint_label.setText(
            "VOICE CORE  ·  " + ("PAUSED" if self.paused else mode.replace("_", " "))
        )
        self.status_badge.setText("●  " + mode.replace("_", " "))
        self.talk_button.setText(
            "Stop this turn" if mode in BUSY_STATES
            else "Resume microphone" if self.paused
            else "Start talking"
        )
        self.talk_button.setEnabled(
            mode in BUSY_STATES or mode in ("STANDBY", "PAUSED")
        )
        self.cancel_button.setEnabled(mode in BUSY_STATES and not self.cancelling)
        self.pause_button.setText("Resume microphone" if self.paused else "Pause microphone")
        self.pause_button.setEnabled(
            mode in ("STANDBY", "PAUSED")
            and not self.pause_pending and not self.closing and not self.failed
        )
        self.screen_read_toggle.setEnabled(
            mode == "STANDBY" and not self.closing and not self.failed
        )
        self.send_button.setEnabled(mode == "STANDBY" and not self.closing and not self.failed)
        self.language_combo.setEnabled(mode == "STANDBY" and not self.closing and not self.failed)
        self.orb.update()

    def _append_message(self, role, text):
        if not text:
            return
        self.messages_layout.takeAt(self.messages_layout.count() - 1)
        card = QFrame()
        card.setObjectName("userBubble" if role == "user" else "assistantBubble")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(13, 9, 13, 10)
        layout.setSpacing(4)
        author = QLabel("YOU" if role == "user" else "JARVIS")
        author.setObjectName("eyebrow")
        layout.addWidget(author)
        message = QLabel(str(text))
        message.setObjectName("message")
        message.setWordWrap(True)
        message.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(message)
        self.messages_layout.addWidget(card)
        self.messages_layout.addStretch(1)
        QTimer.singleShot(
            0,
            lambda: self.message_scroll.verticalScrollBar().setValue(
                self.message_scroll.verticalScrollBar().maximum()
            ),
        )

    def _clear_messages(self):
        while self.messages_layout.count():
            item = self.messages_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.messages_layout.addStretch(1)

    def _send_text(self):
        text = self.input.text().strip()
        if not text:
            return
        if self.worker is not None and self.worker.submit(text):
            self.input.clear()
            self.notice_label.hide()
        else:
            self.notice_label.setText("Jarvis is busy or still starting. Try again when the core is ready.")
            self.notice_label.show()

    def _clear_conversation(self):
        if self.worker is not None and not self.worker.clear():
            self.notice_label.setText("Conversation can be cleared when Jarvis is ready.")
            self.notice_label.show()

    def _confirm_system_action(self, request):
        action = request.get("action")
        descriptions = {
            "shutdown_windows": "Shut down Windows",
            "restart_windows": "Restart Windows",
        }
        title = descriptions.get(action)
        if title is None:
            self.notice_label.setText("That system action is not available.")
            self.notice_label.show()
            return
        answer = QMessageBox.warning(
            self,
            title,
            "Save your work first. If approved, Windows schedules this action "
            "in 60 seconds; you can say “cancel shutdown” to abort it.\n\n"
            + str(request.get("message", "")),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            self.notice_label.setText(f"{title} cancelled. Nothing was changed.")
            self.notice_label.show()
            return
        if self.worker is None:
            result = "Jarvis is not ready to perform that action."
        else:
            result = self.worker.confirm_system_action(action)
        self.notice_label.setText(str(result))
        self.notice_label.show()

    def _language_changed(self, index):
        mode = self.language_combo.itemData(index)
        if mode == self.language_mode:
            return
        if self.worker is not None and self.worker.set_language_mode(mode):
            self.language_mode = mode
            self.preferences.setValue("language_mode", mode)
        else:
            previous = self.language_combo.findData(self.language_mode)
            self.language_combo.blockSignals(True)
            self.language_combo.setCurrentIndex(max(0, previous))
            self.language_combo.blockSignals(False)
            self.notice_label.setText("Language can be changed when Jarvis is ready.")
            self.notice_label.show()
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
        if self.voice_toggle.isChecked() != self.voice_enabled:
            self.voice_toggle.blockSignals(True)
            self.voice_toggle.setChecked(self.voice_enabled)
            self.voice_toggle.blockSignals(False)
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
        self.screen_read_toggle.blockSignals(True)
        self.screen_read_toggle.setChecked(self.screen_read_enabled)
        self.screen_read_toggle.blockSignals(False)

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