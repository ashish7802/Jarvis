"""Run model loading and the voice loop off the Qt UI thread.

Qt widgets are only touched by queued signals on the main thread. See
https://doc.qt.io/qtforpython-6/overviews/qtdoc-threads-qobject.html
"""
import logging
import threading

from PySide6.QtCore import QThread, Signal

from app.assistant.desktop_actions import DesktopActionError
from app.system.hotkey import EmergencyHotkey

log = logging.getLogger("jarvis.desktop")


class AssistantWorker(QThread):
    event = Signal(str, object)

    def __init__(self, factory, speech_enabled=True, parent=None, hearing_profile=None,
                 language_mode=None, screen_read_enabled=False, input_device=None,
                 continuous_listening=True):
        super().__init__(parent)
        self.factory = factory
        self.engine = None
        self.speech_enabled = speech_enabled
        self.hearing_profile = hearing_profile
        self.language_mode = language_mode
        self.screen_read_enabled = bool(screen_read_enabled)
        self.input_device = input_device
        self.continuous_listening = bool(continuous_listening)
        self.stop_requested = threading.Event()

    def run(self):
        hotkey = None
        try:
            self.engine, settings = self.factory(self.event.emit)
            self.engine.set_speech_enabled(self.speech_enabled)
            self.engine.set_hearing_profile(self.hearing_profile or self.engine.hearing_profile)
            self.engine.set_language_mode(self.language_mode or self.engine.language_mode)
            self.engine.set_screen_read_enabled(self.screen_read_enabled)
            if self.input_device is not None and not self.engine.set_input_device(self.input_device):
                self.event.emit("notice", "The selected microphone couldn't be activated. Choose an available input device.")
            if not self.engine.set_continuous_listening(self.continuous_listening):
                self.continuous_listening = False
            if self.stop_requested.is_set():
                return
            self.event.emit("configured", {
                "provider": self.engine.ai.name,
                "wake": self.engine.wake.name if self.engine.wake else "disabled",
                "hotkey": settings.hotkey_exit,
                "logs": str(settings.logs_dir),
                "input_device": self.engine.input_device or "",
                "hands_free": self.engine.continuous_listening,
            })
            hotkey = EmergencyHotkey(settings.hotkey_exit)
            hotkey.set_callback(self.request_stop)
            if not hotkey.start():
                self.event.emit("notice", "The exit shortcut is unavailable. Use the window's close button to stop Jarvis.")
            self.engine.tts.prewarm([self.engine.acknowledgement])
            if not self.stop_requested.is_set():
                self.engine.run()
        except Exception:
            log.exception("Desktop assistant failed")
            self.event.emit("fatal", "Jarvis couldn't start. Check your configuration, microphone and internet connection, then select Retry. Diagnostic logs have more details.")
        finally:
            if self.engine is not None:
                self.engine.request_shutdown()
                self.engine._shutdown_sequence()
            if hotkey is not None:
                hotkey.stop()

    def request_stop(self):
        self.stop_requested.set()
        if self.engine is not None:
            # Cancellation can wait on a native audio lock; keep that off Qt.
            threading.Thread(target=self.engine.request_shutdown, name="desktop-stop", daemon=True).start()

    def listen(self):
        return self.engine is not None and self.engine.request_listen()

    def cancel_turn(self):
        return self.engine is not None and self.engine.cancel_turn()

    def set_hearing_profile(self, profile):
        return self.engine is not None and self.engine.set_hearing_profile(profile)

    def set_language_mode(self, mode):
        return self.engine is not None and self.engine.set_language_mode(mode)

    def set_screen_read_enabled(self, enabled):
        return self.engine is not None and self.engine.set_screen_read_enabled(enabled)

    def set_continuous_listening(self, enabled):
        return self.engine is not None and self.engine.set_continuous_listening(enabled)

    def set_input_device(self, identifier):
        return self.engine is not None and self.engine.set_input_device(identifier)

    def submit(self, text):
        return self.engine is not None and self.engine.submit_text(text)

    def confirm_system_action(self, action):
        if self.engine is None or self.engine.desktop_actions is None:
            return "System actions are unavailable."
        try:
            return self.engine.desktop_actions.run_confirmed_system_action(action)
        except DesktopActionError as exc:
            return str(exc)

    def save_file_draft(self, user_text, path, content, expected_sha256):
        if self.engine is None or self.engine.desktop_actions is None:
            return "File editing is unavailable."
        try:
            result = self.engine.desktop_actions.write_file_draft(
                path, content, expected_sha256
            )
        except DesktopActionError as exc:
            return str(exc)
        self.engine.record_approved_file_edit(user_text, result)
        return result

    def pause(self, paused):
        return self.engine is not None and self.engine.set_listening_enabled(not paused)

    def clear(self):
        return self.engine is not None and self.engine.clear_conversation()

    def review_memory(self):
        return self.engine is not None and self.engine.review_memory()

    def set_voice(self, enabled):
        self.speech_enabled = enabled
        if self.engine is not None:
            threading.Thread(target=self.engine.set_speech_enabled, args=(enabled,),
                             name="desktop-voice-toggle", daemon=True).start()
