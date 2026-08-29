"""JARVIS entrypoint.

Usage:
    python -m app.main           # dev mode (console visible)
    python -m app.main --dev     # explicit dev mode
    python -m app.main --check   # verify config & services init, then exit

In production the app is launched as `JARVIS.exe` (PyInstaller
`--noconsole` build) so no console window is shown.
"""

from __future__ import annotations

import logging
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Optional

from app.ai.base import AIProvider, build_provider
from app.assistant.engine import AssistantEngine
from app.audio.recorder import Player, Recorder
from app.config import get_settings
from app.logging_config import get_logger, setup_logging
from app.stt.service import STTService
from app.system.hotkey import EmergencyHotkey
from app.tts.service import TTSService
from app.wakeword.detector import build_wake_word


def _configure() -> None:
    s = get_settings()
    setup_logging(s.logs_dir, s.log_level)
    log = get_logger("jarvis.main")
    log.info("== JARVIS starting (Python %s) ==", sys.version.split()[0])
    log.info("logs_dir=%s tts_cache=%s", s.logs_dir, s.tts_cache_dir)
    log.info(
        "ai_provider=%s tts=%s wake=%s startup_greeting=%s delay=%.1fs",
        s.ai_provider,
        s.tts_provider,
        "enabled" if s.wake_word_enabled else "disabled",
        "yes" if s.startup_greeting_enabled else "no",
        s.startup_greeting_delay,
    )


def _build_ai(settings) -> AIProvider:
    return build_provider(
        settings.ai_provider,
        openai_key=settings.openai_api_key,
        gemini_key=settings.gemini_api_key,
        model=settings.ai_model,
    )


def _build_stt(settings) -> STTService:
    return STTService(model_size="base", device="cpu", compute_type="int8")


def _build_tts(settings) -> TTSService:
    tts = TTSService(voice=settings.tts_voice, cache_dir=settings.tts_cache_dir)
    return tts


def _build_wake(settings):
    if not settings.wake_word_enabled:
        return None
    return build_wake_word(
        enabled=settings.wake_word_enabled,
        keyword=settings.wake_word,
        wakeword_backend=settings.wakeword_backend,
        openwakeword_model=settings.openwakeword_model,
        openwakeword_threshold=settings.openwakeword_threshold,
        porcupine_access_key=settings.porcupine_access_key,
        porcupine_keyword_path=settings.porcupine_keyword_path,
        porcupine_sensitivity=settings.porcupine_sensitivity,
    )


def main(argv: Optional[list[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    check_only = "--check" in args

    try:
        _configure()
    except Exception as exc:
        print(f"failed to configure: {exc}", file=sys.stderr)
        return 2

    log = get_logger("jarvis.main")
    settings = get_settings()

    # Construct all services. Catch *initialization* errors here so we
    # don't loop a broken assistant.
    try:
        ai = _build_ai(settings)
        log.info("ai ready: %s", ai.name)
        stt = _build_stt(settings)
        # Touch STT to load the model once now, not in the middle of
        # the first user command.
        try:
            stt._ensure_model()  # noqa: SLF001
            log.info("stt ready")
        except Exception as exc:
            log.exception("STT warmup failed: %s", exc)
        tts = _build_tts(settings)
        recorder = Recorder(
            max_seconds=settings.listen_timeout,
            silence_timeout=settings.silence_timeout,
        )
        player = Player()
        tts.attach_player(player)
        wake = _build_wake(settings)
        log.info("wake ready: %s", wake.name if wake else "disabled")
    except Exception as exc:
        log.exception("FATAL: initialization failed: %s", exc)
        return 3

    if check_only:
        log.info("--check: all services initialised. exiting.")
        return 0

    engine = AssistantEngine(
        ai=ai,
        stt=stt,
        tts=tts,
        wake=wake,
        recorder=recorder,
        player=player,
        startup_greeting=settings.startup_greeting if settings.startup_greeting_enabled else None,
        startup_greeting_delay=settings.startup_greeting_delay,
        acknowledgement="Yes, Sir?",
    )

    hotkey = EmergencyHotkey(settings.hotkey_exit)
    hotkey.set_callback(engine.request_shutdown)
    hotkey.start()

    # Install a SIGINT/SIGTERM handler for graceful shutdown in dev
    # mode (PyInstaller-built GUI app won't receive these on Windows).
    def _signal_handler(signum, frame):  # noqa: ARG001
        log.warning("signal %s received", signum)
        engine.request_shutdown()

    try:
        signal.signal(signal.SIGINT, _signal_handler)
    except Exception:
        pass
    try:
        signal.signal(signal.SIGTERM, _signal_handler)
    except Exception:
        pass

    try:
        engine.run()
    except KeyboardInterrupt:
        engine.request_shutdown()
    except Exception as exc:
        log.exception("engine crashed: %s", exc)
        return 1
    finally:
        hotkey.stop()
        log.info("== JARVIS exited cleanly ==")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
