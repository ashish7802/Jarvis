"""The core JARVIS engine: state machine + pipeline glue.

State flow (per spec):
    STARTING -> STANDBY -> WAKE_DETECTED -> ACKNOWLEDGING ->
    LISTENING -> THINKING -> SPEAKING -> STANDBY

Every recoverable error returns to STANDBY. Only initialization
errors fail loudly.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

from app.ai.base import AIProvider
from app.assistant.conversation import ConversationContext
from app.assistant.states import (
    IllegalTransition,
    State,
    assert_transition,
    is_quiet_state,
    is_self_trigger_risky,
)
from app.audio.recorder import Player, Recorder
from app.stt.service import STTService
from app.tts.service import TTSService
from app.wakeword.detector import WakeWordDetector

log = logging.getLogger("jarvis.engine")

SYSTEM_PROMPT = (
    "You are JARVIS, a personal AI voice assistant. "
    "You are calm, intelligent, concise, helpful, and natural. "
    "You are speaking directly with your user. "
    'Use "Sir" naturally when appropriate, but do not overuse it. '
    "Answer clearly and conversationally. "
    "Do not claim to have performed actions you cannot actually perform. "
    "You currently specialize in conversation, information, reasoning, and text generation."
)


class AssistantEngine:
    """Owns the state machine and runs the assistant's main loop.

    The engine is intentionally synchronous in its `run` method — the
    wake-word detector runs in a background thread and calls back into
    `on_wake`. The state variable is protected by a lock so the wake
    callback and the main loop stay in sync.
    """

    def __init__(
        self,
        *,
        ai: AIProvider,
        stt: STTService,
        tts: TTSService,
        wake: Optional[WakeWordDetector],
        recorder: Recorder,
        player: Player,
        startup_greeting: Optional[str] = None,
        startup_greeting_delay: float = 0.0,
        acknowledgement: str = "Yes, Sir?",
        on_state_change: Optional[Callable[[State], None]] = None,
    ) -> None:
        self.ai = ai
        self.stt = stt
        self.tts = tts
        self.wake = wake
        self.recorder = recorder
        self.player = player
        self.startup_greeting = startup_greeting
        self.startup_greeting_delay = startup_greeting_delay
        self.acknowledgement = acknowledgement
        self.on_state_change = on_state_change

        self.context = ConversationContext(system_prompt=SYSTEM_PROMPT)
        self._state: State = State.STARTING
        self._lock = threading.Lock()
        self._wake_event = threading.Event()
        self._shutdown = threading.Event()
        self._greeted = False

        # Wire up callbacks.
        if self.wake is not None:
            self.wake.set_callback(self._on_wake)

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------
    @property
    def state(self) -> State:
        with self._lock:
            return self._state

    def set_state(self, new: State) -> None:
        with self._lock:
            old = self._state
            try:
                assert_transition(old, new)
            except IllegalTransition:
                log.warning("Ignored illegal transition %s -> %s", old.value, new.value)
                return
            self._state = new
        log.info("state %s -> %s", old.value, new.value)
        if self.on_state_change is not None:
            try:
                self.on_state_change(new)
            except Exception:
                log.exception("on_state_change handler failed")

    def _set_wake_enabled(self, enabled: bool) -> None:
        if self.wake is not None:
            self.wake.set_enabled(enabled)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def startup(self) -> None:
        """Initialize all services and play the startup greeting."""
        log.info("engine.startup")
        self.set_state(State.STARTING)
        # Wake detector stays disabled until after the greeting.
        self._set_wake_enabled(False)

        if self.wake is not None:
            self.wake.start()

        if self.startup_greeting:
            if self.startup_greeting_delay > 0:
                log.info(
                    "Waiting %.1fs before startup greeting", self.startup_greeting_delay
                )
                if self._shutdown.wait(self.startup_greeting_delay):
                    return
            self.set_state(State.SPEAKING)
            try:
                self.tts.speak(self.startup_greeting)
            except Exception:
                log.exception("startup greeting failed")
            self._greeted = True
            # Cooldown before wake resumes — avoids self-trigger.
            time.sleep(0.4)
        else:
            self._greeted = True

        self.set_state(State.STANDBY)
        self._set_wake_enabled(True)
        log.info("engine.standby (wake=%s)", self.wake is not None)

    def run(self) -> None:
        """Main blocking loop. Returns when shutdown is requested."""
        try:
            self.startup()
        except Exception as exc:
            log.exception("startup failed: %s", exc)
            self.set_state(State.ERROR)
            return
        # Main loop is event-driven by the wake-word callback. The
        # loop body just waits for shutdown — most work happens in
        # `_on_wake` (on the wake thread) and the inline calls there
        # dispatch back to `handle_command` synchronously.
        while not self._shutdown.is_set():
            self._shutdown.wait(timeout=0.5)
        self._shutdown_sequence()

    def request_shutdown(self) -> None:
        log.warning("engine.shutdown_requested")
        self._shutdown.set()
        self._wake_event.set()
        try:
            self.recorder.stop()
        except Exception:
            pass
        try:
            self.tts.stop()
        except Exception:
            pass
        try:
            self.player.stop()
        except Exception:
            pass

    def _shutdown_sequence(self) -> None:
        log.info("engine.shutdown_sequence")
        self.set_state(State.SHUTTING_DOWN)
        self._set_wake_enabled(False)
        try:
            if self.wake is not None:
                self.wake.stop()
        except Exception:
            log.exception("wake stop failed")
        try:
            self.stt.shutdown()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Wake handling
    # ------------------------------------------------------------------
    def _on_wake(self) -> None:
        """Callback from the wake-word detector thread."""
        if self._shutdown.is_set():
            return
        with self._lock:
            if self._state != State.STANDBY:
                # Self-trigger guard or stale callback.
                return
        # Immediately mark WAKE_DETECTED so the wake detector won't
        # re-fire from the upcoming "Yes, Sir?" audio.
        self.set_state(State.WAKE_DETECTED)
        self._set_wake_enabled(False)
        # Acknowledge on a fresh state to consume legal transitions.
        self.set_state(State.ACKNOWLEDGING)
        self.set_state(State.SPEAKING)
        try:
            self.tts.speak(self.acknowledgement)
        except Exception:
            log.exception("acknowledgement failed")
        # Brief cooldown to avoid catching the tail of our own audio.
        time.sleep(0.4)
        # Then transition into LISTENING and handle the command.
        self.set_state(State.LISTENING)
        self.handle_command()
        # handle_command always returns to STANDBY (or shutdown).

    # ------------------------------------------------------------------
    # Command pipeline
    # ------------------------------------------------------------------
    def handle_command(self) -> None:
        """Record -> STT -> AI -> TTS -> STANDBY. One full cycle."""
        if self._shutdown.is_set():
            return
        try:
            audio = self.recorder.record()
        except Exception as exc:
            log.exception("recorder crashed: %s", exc)
            audio = None

        if audio is None or audio.size == 0:
            log.info("no speech captured; returning to standby")
            self._back_to_standby()
            return

        text = self.stt.transcribe(audio)
        if not text.strip():
            log.info("STT returned empty; returning to standby")
            self._back_to_standby()
            return

        self.set_state(State.THINKING)
        self.context.add_user(text)
        try:
            reply = self.ai.chat(self.context.messages())
        except Exception as exc:
            log.exception("AI chat crashed: %s", exc)
            reply = "I'm sorry, Sir. Something went wrong while I was thinking."
        if not reply.strip():
            reply = "I'm sorry, Sir. I didn't catch a response."
        self.context.add_assistant(reply)
        log.info("ai.reply %r", reply)

        self.set_state(State.SPEAKING)
        try:
            self.tts.speak(reply)
        except Exception:
            log.exception("TTS playback failed")
        # Cooldown before re-enabling wake detection.
        time.sleep(0.4)
        self._back_to_standby()

    def _back_to_standby(self) -> None:
        if self._shutdown.is_set():
            return
        self.set_state(State.STANDBY)
        self._set_wake_enabled(True)
