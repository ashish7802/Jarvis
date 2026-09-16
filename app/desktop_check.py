"""Opt-in desktop smoke check with the real services and a visible Qt window.

JARVIS.exe --desktop-check uses synthetic questions only. Results and a
window screenshot are written to the usual logs directory. No mic recording.
"""
import json
import time
import re

from PySide6.QtCore import QSettings, QTimer
from PySide6.QtWidgets import QApplication

from app.config import get_settings
from app.desktop import JarvisWindow


def run_check(factory):
    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    settings = get_settings()
    prefs = QSettings(str(settings.logs_dir / "desktop-check.ini"), QSettings.Format.IniFormat)
    prefs.setValue("spoken_replies", True)
    prefs.setValue("language_mode", "auto")
    result = {"passed": False, "steps": []}
    def check_factory(callback):
        def forward(kind, payload):
            if kind == "notice" and ("playback failed" in payload or "Couldn't play" in payload):
                result["audio_error"] = payload
            callback(kind, payload)
        engine, configured = factory(forward)
        result["wake_backend"] = engine.wake.name if engine.wake else "disabled"
        # Load real wake assets; smoke_pipeline separately tests wake inference.
        # Keep the check deterministic without listening to room audio.
        engine.wake = None
        engine.startup_greeting = None
        return engine, configured
    window = JarvisWindow(check_factory, preferences=prefs)
    stage = 0
    deadline = time.monotonic() + 180
    expected_count = 0
    questions = ["show controls", "hide controls", "What is 12.5 percent of 240?",
                 "In one short sentence, say hello and mention the word ready.",
                 "noisy room mode", "soft voice mode", "Hindi mein baat karo",
                 "कंप्यूटर क्या है? एक वाक्य में बताओ।", "speak English",
                 "What is a computer? Answer in one short English sentence.", "match my language", "hide chat"]
    def finish(error=None):
        timer.stop()
        if error:
            result["error"] = error
        else:
            result["passed"] = True
        (settings.logs_dir / "desktop-check.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        window.close()
    def advance():
        nonlocal stage, expected_count
        if time.monotonic() > deadline:
            finish("Desktop check timed out")
            return
        if window.failed:
            finish("Desktop service initialization failed; see jarvis.log")
            return
        if window.current_state != "STANDBY" or window.worker.engine is None:
            return
        if stage and len(window.message_widgets) < expected_count:
            return
        if stage == 1 and not window.controls_open:
            finish("Show-controls voice command failed")
            return
        if stage == 2 and window.controls_open:
            finish("Hide-controls voice command failed")
            return
        if stage == 1:
            window.grab().save(str(settings.logs_dir / "desktop-controls-check.png"))
        if stage == 3 and "30" not in (window.worker.engine.context.last_assistant() or ""):
            finish("Calculation response failed")
            return
        if stage == 4:
            if "ready" not in (window.worker.engine.context.last_assistant() or "").lower():
                finish("Real AI response failed")
                return
            window.grab().save(str(settings.logs_dir / "desktop-check.png"))
        if stage == 5:
            if window.hearing.currentData() != "noisy":
                finish("Noisy-room hearing control failed")
                return
        if stage == 6:
            if window.hearing.currentData() != "soft":
                finish("Soft-voice hearing control failed")
                return
        if stage == 7:
            if window.language.currentData() != "hi":
                finish("Hindi language control failed")
                return
        if stage == 8:
            if not re.search(r"[\u0900-\u097f]", window.worker.engine.context.last_assistant() or ""):
                finish("Hindi AI response failed")
                return
        if stage == 9:
            if window.language.currentData() != "en":
                finish("English language control failed")
                return
        if stage == 10:
            answer = window.worker.engine.context.last_assistant() or ""
            if not answer or re.search(r"[\u0900-\u097f]", answer):
                finish("English AI response failed")
                return
        if stage == 11:
            if window.language.currentData() != "auto":
                finish("Auto language control failed")
                return
        if stage == 12:
            if window.chat_card.isVisible():
                finish("Hide-chat command failed")
            elif result.get("audio_error"):
                finish(result["audio_error"])
            elif result["wake_backend"] != "openwakeword":
                finish("Real wake-word model did not load")
            else:
                finish()
            return
        text = questions[stage]
        if window.worker.submit(text):
            expected_count = len(window.message_widgets) + 2
            result["steps"].append(text)
            stage += 1
    timer = QTimer()
    timer.setInterval(100)
    timer.timeout.connect(advance)
    timer.start()
    window.show()
    app.exec()
    return 0 if result["passed"] else 1
