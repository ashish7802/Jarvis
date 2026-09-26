"""Run model loading and the voice loop off the Qt UI thread.

Qt widgets are only touched by queued signals on the main thread. See
https://doc.qt.io/qtforpython-6/overviews/qtdoc-threads-qobject.html
"""
import logging
import threading

from PySide6.QtCore import QThread, Signal

from app.system.hotkey import EmergencyHotkey

log = logging.getLogger("jarvis.desktop")


class AssistantWorker(QThread):
    event = Signal(str, object)

    def __init__(self, factory, speech_enabled=True, parent=None, hearing_profile=None,
                 language_mode=None, screen_read_enabled=False):
        super().__init__(parent)
        self.factory = factory
        self.engine = None
        self.speech_enabled = speech_enabled
        self.hearing_profile = hearing_profile
        self.language_mode = language_mode
        self.screen_read_enabled = bool(screen_read_enabled)
        self.stop_requested = threading.Event()

    def run(self):
        hotkey = None
        try:
            self.engine, settings = self.factory(self.event.emit)
            self.engine.set_speech_enabled(self.speech_enabled)
            self.engine.set_hearing_profile(self.hearing_profile or self.engine.hearing_profile)
            self.engine.set_language_mode(self.language_mode or self.engine.language_mode)
            self.engine.set_screen_read_enabled(self.screen_read_enabled)
            if self.stop_requested.is_set():
                return
            self.event.emit("configured", {
                "provider": self.engine.ai.name,
                "wake": self.engine.wake.name if self.engine.wake else "disabled",
                "hotkey": settings.hotkey_exit,
                "logs": str(settings.logs_dir),
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

    def submit(self, text):
        return self.engine is not None and self.engine.submit_text(text)

    def pause(self, paused):
        return self.engine is not None and self.engine.set_listening_enabled(not paused)

    def clear(self):
        return self.engine is not None and self.engine.clear_conversation()

    def set_voice(self, enabled):
        self.speech_enabled = enabled
        if self.engine is not None:
            threading.Thread(target=self.engine.set_speech_enabled, args=(enabled,),
                             name="desktop-voice-toggle", daemon=True).start()
