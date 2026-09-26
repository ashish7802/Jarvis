"""A visible, native Windows/Qt desktop for the voice assistant. No web view."""
from datetime import datetime
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import sys

from PySide6.QtCore import Qt, QSettings, QTimer, Slot, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget, QComboBox, QProgressBar,
)

from app.hud_widgets import STYLE, VoiceOrb, app_icon, HudBackground, TypedMessage
from app.desktop_worker import AssistantWorker
from app.audio.hearing import PROFILES
from app.assistant.language import LANGUAGES

TITLE = "JARVIS — Voice Assistant"
STATE_COPY = {
    "STARTING": ("Starting up", "Getting ready for you.", "Loading your voice assistant…"),
    "STANDBY": ("Ready", "Ready when you are.", 'Say “Hey Jarvis”, wait for the reply, then ask away.'),
    "WAKE_DETECTED": ("Heard you", "I'm here.", "Wait for the acknowledgement, then speak."),
    "ACKNOWLEDGING": ("Heard you", "I'm here.", "Wait for the acknowledgement, then speak."),
    "LISTENING": ("Listening", "I'm listening…", "Speak naturally. A short pause finishes your question."),
    "TRANSCRIBING": ("Understanding", "Let me catch that…", "Turning your speech into words."),
    "THINKING": ("Thinking", "Thinking it through…", "Your answer is on its way."),
    "SPEAKING": ("Responding", "Here's what I think.", "Follow the reply in your conversation."),
    "PAUSED": ("Mic paused", "A quiet moment.", "Your microphone is paused. Resume it or type a message."),
    "ERROR": ("Needs attention", "Let's reconnect.", "Check the message above, then try again."),
    "SHUTTING_DOWN": ("Stopping", "See you soon.", "Releasing the microphone and closing safely…"),
}


def label(text, name=None, wrap=False):
    item = QLabel(text)
    if name:
        item.setObjectName(name)
    item.setTextFormat(Qt.TextFormat.PlainText)
    item.setWordWrap(wrap)
    return item


def button(text, name=None):
    item = QPushButton(text)
    item.setCursor(Qt.CursorShape.PointingHandCursor)
    if name:
        item.setObjectName(name)
    return item


class JarvisWindow(QMainWindow):
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
        self.wake_backend = "openwakeword"
        self.message_widgets = []
        self.logs_dir = Path(os.environ.get("APPDATA", ".")) / "JARVIS" / "logs"
        self.setWindowTitle(TITLE)
        self.setWindowIcon(app_icon())
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setMinimumSize(760, 580)
        self.resize(1040, 720)
        self.setStyleSheet(STYLE)
        self._build_ui()
        geometry = self.preferences.value("hud_geometry")
        if geometry:
            self.restoreGeometry(geometry)
        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(min(self.width(), screen.width()-20), min(self.height(), screen.height()-45))
        self.voice.setChecked(self.preferences.value("spoken_replies", True, type=bool))
        self._refresh_state()
        self.talk_shortcut = QShortcut(QKeySequence("Ctrl+Space"), self)
        self.talk_shortcut.activated.connect(self._listen)
        self.controls_shortcut = QShortcut(QKeySequence("F2"), self)
        self.controls_shortcut.activated.connect(lambda: self.show_controls(not self.controls_open))
        self.cancel_shortcut = QShortcut(QKeySequence("Escape"), self)
        self.cancel_shortcut.activated.connect(self._cancel_turn)
        if autostart:
            QTimer.singleShot(0, self.start_assistant)

    def _build_ui(self):
        root = HudBackground()
        self.setCentralWidget(root)
        page = QVBoxLayout(root)
        page.setContentsMargins(30, 24, 30, 24)
        page.setSpacing(16)
        header = QHBoxLayout()
        header.addWidget(label("JARVIS", "brand"))
        header.addStretch()
        self.provider = label("", "eyebrow")
        header.addWidget(self.provider)
        header.addSpacing(24)
        self.badge = label("INITIALIZING", "statusBadge")
        header.addWidget(self.badge)
        page.addLayout(header)
        self.notice = label("", "notice", True)
        self.notice.hide()
        page.addWidget(self.notice)
        self.body = QHBoxLayout()
        self.body.setSpacing(18)
        page.addLayout(self.body, 1)
        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(6)
        self.body.addWidget(center, 1)
        self.orb = VoiceOrb()
        self.orb.activated.connect(self._listen)
        center_layout.addWidget(self.orb, 1)
        self.hero_title = label("INITIALIZING", "heroTitle")
        self.hero_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_layout.addWidget(self.hero_title)
        self.hero_hint = label("Loading your assistant...", "muted", True)
        self.hero_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hero_hint.setMinimumHeight(32)
        center_layout.addWidget(self.hero_hint)
        self.retry = button("RETRY CONNECTION")
        self.retry.clicked.connect(self.start_assistant)
        self.retry.hide()
        center_layout.addWidget(self.retry, 0, Qt.AlignmentFlag.AlignCenter)

        self.chat_card = QFrame()
        self.chat_card.setObjectName("chatCard")
        chat = QVBoxLayout(self.chat_card)
        chat.setContentsMargins(18, 10, 18, 10)
        chat.setSpacing(6)
        chat_header = QHBoxLayout()
        chat_header.addWidget(label("CONVERSATION  /  CURRENT SESSION", "eyebrow"))
        chat_header.addStretch()
        hide_chat = button("HIDE", "quiet")
        hide_chat.clicked.connect(lambda: self.show_chat(False))
        chat_header.addWidget(hide_chat)
        chat.addLayout(chat_header)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.messages = QWidget()
        self.messages.setObjectName("messages")
        self.messages_layout = QVBoxLayout(self.messages)
        self.messages_layout.setContentsMargins(0, 0, 5, 0)
        self.messages_layout.setSpacing(12)
        self.empty = label("Conversation appears here when you speak.", "muted")
        self.messages_layout.addWidget(self.empty)
        self.messages_layout.addStretch()
        self.scroll.setWidget(self.messages)
        chat.addWidget(self.scroll, 1)
        self.chat_card.setFixedHeight(228)
        self.chat_card.hide()
        center_layout.addWidget(self.chat_card)

        # Tools stay hidden until a local voice command or the F2 shortcut.
        self.controls = QFrame()
        self.controls.setObjectName("controls")
        self.controls.setMaximumWidth(0)
        self.controls.hide()
        panel_layout = QVBoxLayout(self.controls)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_scroll = QScrollArea()
        panel_scroll.setWidgetResizable(True)
        panel_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        panel_content = QWidget()
        panel_content.setObjectName("messages")
        panel_scroll.setWidget(panel_content)
        panel_layout.addWidget(panel_scroll)
        control_layout = QVBoxLayout(panel_content)
        control_layout.setContentsMargins(18, 18, 18, 18)
        control_layout.setSpacing(9)
        panel_header = QHBoxLayout()
        panel_header.addWidget(label("Controls", "eyebrow"))
        panel_header.addStretch()
        close_panel = button("HIDE", "quiet")
        close_panel.clicked.connect(lambda: self.show_controls(False))
        panel_header.addWidget(close_panel)
        control_layout.addLayout(panel_header)
        self.talk = button("Talk to Jarvis", "primary")
        self.talk.clicked.connect(self._listen)
        control_layout.addWidget(self.talk)
        self.cancel_button = button("Cancel current turn  ·  Esc")
        self.cancel_button.clicked.connect(self._cancel_turn)
        control_layout.addWidget(self.cancel_button)
        control_layout.addWidget(label("Hearing", "eyebrow"))
        self.hearing = QComboBox()
        self.hearing.setAccessibleName("Microphone sensitivity")
        for key, profile in PROFILES.items():
            self.hearing.addItem(profile.label, key)
        saved = self.preferences.value("hearing_profile", "soft")
        self.hearing.setCurrentIndex(max(0, self.hearing.findData(saved)))
        self.hearing.currentIndexChanged.connect(self._change_hearing)
        control_layout.addWidget(self.hearing)
        self.mic_meter = QProgressBar()
        self.mic_meter.setRange(0, 100)
        self.mic_meter.setValue(0)
        self.mic_meter.setTextVisible(False)
        self.mic_meter.setFixedHeight(7)
        self.mic_meter.setAccessibleName("Live microphone input level")
        control_layout.addWidget(self.mic_meter)
        self.mic_status = label("Connecting microphone…", "muted", True)
        control_layout.addWidget(self.mic_status)
        control_layout.addWidget(label("Soft voice helps in quiet rooms. Use Noisy room near fans or traffic.", "muted", True))
        control_layout.addWidget(label("Language / भाषा", "eyebrow"))
        self.language = QComboBox()
        self.language.setAccessibleName("Conversation language")
        for key, name in LANGUAGES.items():
            self.language.addItem(name, key)
        self.language.setCurrentIndex(max(0, self.language.findData(self.preferences.value("language_mode", "auto"))))
        self.language.currentIndexChanged.connect(self._change_language)
        control_layout.addWidget(self.language)
        control_layout.addWidget(label('Say "Hindi mein baat karo", "speak English" or "match my language".', "muted", True))
        self.pause = button("Pause microphone", "toggle")
        self.pause.setCheckable(True)
        self.pause.clicked.connect(self._toggle_pause)
        control_layout.addWidget(self.pause)
        self.voice = button("Voice replies on", "toggle")
        self.voice.setCheckable(True)
        self.voice.toggled.connect(self._toggle_voice)
        control_layout.addWidget(self.voice)
        self.screen_read = QCheckBox("Allow on-demand screen reading")
        self.screen_read.setAccessibleName("Allow on-demand screen reading")
        self.screen_read.setChecked(self.preferences.value("screen_read_enabled", False, type=bool))
        self.screen_read.setToolTip(
            "When enabled, accessible text from the active window is sent to your configured AI provider "
            "only when you ask Jarvis to read the screen. Password fields are skipped and the capture "
            "is not saved by Jarvis."
        )
        self.screen_read.toggled.connect(self._change_screen_read)
        control_layout.addWidget(self.screen_read)
        control_layout.addWidget(label(
            "Active-window text goes to your AI provider only after you ask. "
            "Password fields are skipped; Jarvis doesn't save the capture.",
            "muted", True,
        ))
        self.clear = button("New chat")
        self.clear.clicked.connect(self._clear)
        control_layout.addWidget(self.clear)
        reveal_chat = button("Show conversation")
        reveal_chat.clicked.connect(lambda: self.show_chat(True, pinned=True))
        control_layout.addWidget(reveal_chat)
        control_layout.addSpacing(10)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Type a message...")
        self.input.setAccessibleName("Message Jarvis")
        self.input.setMaxLength(4000)
        self.input.returnPressed.connect(self._send)
        control_layout.addWidget(self.input)
        self.send = button("Send", "primary")
        self.send.clicked.connect(lambda: self._send())
        control_layout.addWidget(self.send)
        control_layout.addStretch()
        control_layout.addWidget(label('Say "hide controls" to return to the main view.\nF2 toggles controls. Ctrl+Space activates the mic.', "muted", True))
        control_layout.addWidget(label("Wake detection is local. Questions go to your AI provider. Chat is kept for this session only.", "muted", True))
        self.logs = button("Open diagnostic logs", "quiet")
        self.logs.clicked.connect(self._open_logs)
        control_layout.addWidget(self.logs)
        self.body.addWidget(self.controls)
        self.controls_animation = QPropertyAnimation(self.controls, b"maximumWidth", self)
        self.controls_animation.setDuration(260)
        self.controls_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.controls_animation.finished.connect(self._finish_controls_animation)
        self.controls_open = False
        self.chat_pinned = False
        self.chat_suppressed = False
        self.chat_idle_timer = QTimer(self)
        self.chat_idle_timer.setSingleShot(True)
        self.chat_idle_timer.setInterval(45000)
        self.chat_idle_timer.timeout.connect(self._idle_chat)
        footer = QHBoxLayout()
        self.footer = label('Voice interface  ·  say "Hey Jarvis"', "eyebrow")
        footer.addWidget(self.footer)
        footer.addStretch()
        footer.addWidget(label('"Show controls"  ·  F2', "eyebrow"))
        page.addLayout(footer)
        self.suggestions = []

    def show_controls(self, visible):
        self.controls_open = bool(visible)
        self.controls_animation.stop()
        self.controls.show()
        self.controls_animation.setStartValue(self.controls.width())
        self.controls_animation.setEndValue(280 if visible else 0)
        self.controls_animation.start()

    def _finish_controls_animation(self):
        if not self.controls_open:
            self.controls.hide()

    def show_chat(self, visible, pinned=False):
        self.chat_pinned = bool(visible and pinned)
        self.chat_suppressed = not visible
        self.chat_card.setVisible(visible)
        self.chat_idle_timer.stop()
        if visible and not pinned and self.current_state == "STANDBY":
            self.chat_idle_timer.start()
        self._scroll_to_end()

    def _idle_chat(self):
        if self.current_state == "STANDBY" and not self.chat_pinned:
            self.chat_card.hide()

    def _scroll_to_end(self):
        QTimer.singleShot(0, lambda: self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum()))

    @Slot()
    def start_assistant(self):
        if self.closing or (self.worker is not None and self.worker.isRunning()):
            return
        if self.worker is not None:
            self.worker.deleteLater()
        self.failed = False
        self.paused = False
        self.pause_pending = False
        self.notice.hide()
        self.retry.hide()
        self.current_state = "STARTING"
        self._refresh_state()
        self.worker = AssistantWorker(self.factory, self.voice.isChecked(), self,
                                      hearing_profile=self.preferences.value("hearing_profile"),
                                      language_mode=self.preferences.value("language_mode"),
                                      screen_read_enabled=self.preferences.value("screen_read_enabled", False, type=bool))
        self.worker.event.connect(self.on_event)
        self.worker.finished.connect(self._worker_finished)
        self.worker.start()

    @Slot(str, object)
    def on_event(self, event, payload):
        if event == "state":
            if not self.failed:
                self.current_state = payload
            if payload in ("WAKE_DETECTED", "LISTENING", "THINKING"):
                self.notice.hide()
            if payload == "STANDBY":
                self.cancelling = False
            if payload != "LISTENING":
                self.orb.audio_level = 0
                self.mic_meter.setValue(0)
            self._refresh_state()
            if payload == "STANDBY" and self.chat_card.isVisible() and not self.chat_pinned:
                self.chat_idle_timer.start()
            else:
                self.chat_idle_timer.stop()
        elif event == "audio":
            if self.paused or self.closing:
                return
            expected = "LISTENING" if payload["source"] == "recording" else "STANDBY"
            if self.current_state != expected:
                return
            self.mic_meter.setValue(payload["level"])
            self.orb.audio_level = payload["level"] / 100
            self.mic_status.setText("Input too loud — move back a little" if payload.get("clipping") else
                                    "Input detected" if payload.get("active") else "Microphone connected")
        elif event == "microphone":
            self.microphone_connected = bool(payload)
            self.mic_status.setText("Microphone connected" if payload else "Microphone disconnected · reconnecting…")
            if not payload:
                self.mic_meter.setValue(0)
            self._refresh_state()
        elif event == "language":
            self.language.blockSignals(True)
            self.language.setCurrentIndex(self.language.findData(payload))
            self.language.blockSignals(False)
            self.preferences.setValue("language_mode", payload)
        elif event == "screen_read":
            self.screen_read.blockSignals(True)
            self.screen_read.setChecked(bool(payload))
            self.screen_read.blockSignals(False)
            self.preferences.setValue("screen_read_enabled", bool(payload))
        elif event == "hearing":
            self.hearing.blockSignals(True)
            self.hearing.setCurrentIndex(self.hearing.findData(payload))
            self.hearing.blockSignals(False)
            self.preferences.setValue("hearing_profile", payload)
        elif event == "progress":
            if not self.closing:
                self.hero_hint.setText(payload)
                self.footer.setText(payload)
        elif event == "message":
            self.add_message(payload["role"], payload["text"])
        elif event == "notice":
            self.notice.setText(payload)
            self.notice.show()
        elif event == "fatal":
            self.failed = True
            self.current_state = "ERROR"
            self.notice.setText(payload)
            self.notice.show()
            self._refresh_state()
        elif event == "clear":
            self._clear_messages()
        elif event == "ui":
            action = payload["action"]
            if action in ("show_controls", "hide_controls"):
                self.show_controls(action == "show_controls")
            elif action in ("show_chat", "hide_chat"):
                self.show_chat(action == "show_chat", pinned=action == "show_chat")
            elif action == "clear_chat":
                self._clear_messages()
        elif event == "listening":
            self.paused = not payload
            self.pause_pending = False
            if self.paused:
                self.mic_meter.setValue(0)
                self.mic_status.setText("Microphone paused")
            self._refresh_state()
        elif event == "configured":
            self.provider.setText(payload["provider"].upper() + "  /  VOICE LINK")
            self.wake_backend = payload["wake"]
            self.logs_dir = Path(payload["logs"])
            self.footer.setText('Voice interface  ·  say "Hey Jarvis"')
            if self.wake_backend == "energy":
                self.on_event("notice", "Wake-word detection is unavailable. Sound-trigger fallback is active; loud sounds may activate Jarvis. You can also use Talk to Jarvis.")

    def _refresh_state(self):
        mode = "SHUTTING_DOWN" if self.closing else self.current_state
        if mode == "STANDBY" and self.paused:
            mode = "PAUSED"
        badge, title, hint = STATE_COPY.get(mode, STATE_COPY["STARTING"])
        if mode == "STANDBY" and self.wake_backend == "disabled":
            hint = "Click Talk to Jarvis to speak, or type a message."
        elif mode == "STANDBY" and self.wake_backend == "energy":
            hint = "Sound-trigger fallback is active. Use Talk to Jarvis for a reliable start."
        elif mode == "STANDBY" and self.microphone_connected is False:
            badge, hint = "Mic disconnected", "Reconnect your microphone. Jarvis will retry automatically; you can still type."
        if self.cancelling and mode not in ("STANDBY", "PAUSED", "SHUTTING_DOWN"):
            badge, hint = "Cancelling", "Finishing the current operation. Your next question will be available shortly."
        self.badge.setText("●  " + badge)
        self.hero_title.setText(badge.upper())
        self.hero_hint.setText(hint)
        self.orb.mode = mode
        self.orb.setAccessibleName("Cancel current turn" if mode not in ("STANDBY", "PAUSED", "STARTING") else "Activate Jarvis microphone")
        ready = self.current_state == "STANDBY" and not self.closing and not self.failed
        self.talk.setEnabled(ready and not self.paused and not self.pause_pending)
        self.talk.setText("Listening…" if mode == "LISTENING" else "Talk to Jarvis")
        self.input.setEnabled(not self.closing and not self.failed)
        self.hearing.setEnabled(ready)
        self.language.setEnabled(ready)
        self.screen_read.setEnabled(ready)
        self.cancel_button.setEnabled(self.current_state in ("WAKE_DETECTED", "ACKNOWLEDGING", "LISTENING", "TRANSCRIBING", "THINKING", "SPEAKING") and not self.closing and not self.cancelling)
        self.send.setEnabled(ready)
        self.clear.setEnabled(ready)
        self.pause.setEnabled(ready and not self.pause_pending)
        self.pause.setChecked(self.paused)
        self.pause.setText("Resume microphone" if self.paused else "Pause microphone")
        self.voice.setEnabled(not self.closing and not self.failed)
        for suggestion in self.suggestions:
            suggestion.setEnabled(ready)

    def _listen(self):
        if self.current_state in ("WAKE_DETECTED", "ACKNOWLEDGING", "LISTENING", "TRANSCRIBING", "THINKING", "SPEAKING"):
            self._cancel_turn()
            return
        if self.paused:
            self._toggle_pause()
            return
        if self.worker is not None and not self.worker.listen():
            self.on_event("notice", "Wait until Jarvis is ready, and resume the microphone if it is paused.")

    def _send(self, text=None):
        text = self.input.text() if text is None else text
        if not text.strip():
            return
        if self.worker is not None and self.worker.submit(text):
            self.input.clear()
        else:
            self.on_event("notice", "Jarvis is still busy. Your message is kept here so you can send it when ready.")

    def _cancel_turn(self):
        if self.worker is not None and self.worker.cancel_turn():
            self.cancelling = True
            self._refresh_state()

    def _change_hearing(self):
        if self.worker is not None and not self.worker.set_hearing_profile(self.hearing.currentData()):
            self.on_event("hearing", self.worker.engine.hearing_profile)

    def _change_language(self):
        if self.worker is not None and not self.worker.set_language_mode(self.language.currentData()):
            self.on_event("language", self.worker.engine.language_mode)

    def _change_screen_read(self, enabled):
        self.preferences.setValue("screen_read_enabled", bool(enabled))
        if self.worker is not None and not self.worker.set_screen_read_enabled(enabled):
            engine = self.worker.engine
            self.on_event("screen_read", bool(engine and engine.screen_read_enabled))

    def _toggle_pause(self):
        if self.worker is not None and self.worker.pause(not self.paused):
            self.pause_pending = True
        self._refresh_state()

    def _toggle_voice(self, enabled):
        self.voice.setText("Voice replies on" if enabled else "Voice replies off")
        self.preferences.setValue("spoken_replies", enabled)
        if self.worker is not None:
            self.worker.set_voice(enabled)

    def _clear(self):
        if self.worker is not None:
            self.worker.clear()

    def _clear_messages(self):
        for widget in self.message_widgets:
            self.messages_layout.removeWidget(widget)
            widget.deleteLater()
        self.message_widgets.clear()
        self.empty.show()
        self.chat_card.hide()
        self.chat_pinned = False

    def add_message(self, role, text):
        if role == "user":
            self.chat_suppressed = False
            self.chat_card.show()
            self.chat_idle_timer.stop()
        self.empty.hide()
        bubble = QFrame()
        bubble.setObjectName("userBubble" if role == "user" else "assistantBubble")
        layout = QVBoxLayout(bubble)
        layout.setContentsMargins(15, 12, 15, 14)
        layout.setSpacing(7)
        row = QHBoxLayout()
        row.addWidget(label("YOU" if role == "user" else "JARVIS", "eyebrow"))
        row.addStretch()
        row.addWidget(label(datetime.now().strftime("%H:%M"), "muted"))
        layout.addLayout(row)
        message = TypedMessage(text, animate=role == "assistant" and self.chat_card.isVisible())
        message.advanced.connect(self._scroll_to_end)
        layout.addWidget(message)
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, bubble)
        self.message_widgets.append(bubble)
        # Keep the desktop bounded even in a long-running session.
        if len(self.message_widgets) > 100:
            old = self.message_widgets.pop(0)
            self.messages_layout.removeWidget(old)
            old.deleteLater()
        self._scroll_to_end()

    def _open_logs(self):
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(str(self.logs_dir))

    @Slot()
    def _worker_finished(self):
        if self.closing:
            self.close()
        elif self.failed:
            self.retry.show()
        else:
            self.close()

    def closeEvent(self, event):
        self.preferences.setValue("hud_geometry", self.saveGeometry())
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
                ctypes.windll.dwmapi.DwmSetWindowAttribute(wintypes.HWND(int(self.winId())), 20,
                                                          ctypes.byref(enabled), ctypes.sizeof(enabled))
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
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Jarvis.Desktop.Assistant")
    app = QApplication(sys.argv[:1])
    app.setApplicationName("JARVIS")
    app.setStyle("Fusion")
    window = JarvisWindow(factory)
    window.show()
    return app.exec()
