"""Voice assistant engine. Wake callbacks enqueue; the main thread runs commands."""
from datetime import datetime
import logging
import queue
import threading

from app.ai.base import AIProviderError, ChatMessage
from app.assistant.commands import local_reply, is_history_control, is_clear_command, desktop_command
from app.assistant.conversation import ConversationContext
from app.assistant.states import IllegalTransition, State, assert_transition
from app.audio.hearing import PROFILES
from app.assistant.language import LANGUAGES, reply_language, instruction, localize

log = logging.getLogger("jarvis.engine")
SYSTEM_PROMPT = (
    "You are JARVIS, a thoughtful personal voice assistant. "
    "Give a direct, useful answer, normally in one to three spoken sentences; expand when asked. "
    "Use the conversation to resolve follow-up questions and pronouns. "
    "Reason carefully, check calculations, and distinguish facts from guesses. "
    "Ask one focused clarification when a misheard word or missing detail changes the answer. "
    "Reply in the user's language, including English, Hindi, or Hinglish. "
    "Use natural speech, without Markdown tables, decorative formatting, or long URLs. "
    "Be warm and respectful without repeatedly saying Sir. "
    "You can converse, explain, draft text, tell local time/date, repeat the last answer, "
    "calculate basic arithmetic and percentages locally, and clear this session's conversation. "
    "Use the actual local calculation results in the conversation for follow-up questions. "
    "If a question has a false premise, gently correct it instead of agreeing. "
    "For multi-step requests, cover each requested part and check that your conclusion follows. "
    "You cannot control apps, send messages, "
    "browse live information, or remember across restarts. Never claim you did those things. "
    "If an answer needs current information you cannot verify, say so."
)


class AssistantEngine:
    def __init__(self, *, ai, stt, tts, wake, recorder, player,
                 startup_greeting=None, startup_greeting_delay=0.0,
                 acknowledgement="Yes, Sir?", on_state_change=None,
                 user_name="", context_messages=21, cooldown_seconds=0.4,
                 on_event=None, continuous_without_wake=True, language_mode="auto"):
        self.ai, self.stt, self.tts = ai, stt, tts
        self.wake, self.recorder, self.player = wake, recorder, player
        self.startup_greeting = startup_greeting
        self.startup_greeting_delay = startup_greeting_delay
        self.acknowledgement = acknowledgement
        self.on_state_change = on_state_change
        self.on_event = on_event
        self.continuous_without_wake = continuous_without_wake
        self._listening_enabled = True
        self._speech_enabled = True
        self.language_mode = language_mode if language_mode in LANGUAGES else "auto"
        self._reply_language = "hi" if self.language_mode in ("hi", "hinglish") else "en"
        self._pending_text = None
        self._controls = queue.SimpleQueue()
        self.cooldown_seconds = cooldown_seconds
        prompt = SYSTEM_PROMPT + (f" The user's preferred name is {user_name}." if user_name else "")
        self.context = ConversationContext(prompt, max_messages=context_messages)
        self._state = State.STARTING
        self._lock = threading.RLock()
        self._wake_event = threading.Event()
        self._shutdown = threading.Event()
        self._turn_cancelled = threading.Event()
        self._cleaned = False
        for service in (self.recorder, self.player, self.tts, self.ai):
            service.turn_cancelled = self._turn_cancelled
        self.hearing_profile = getattr(self.recorder, "hearing_profile", "soft")
        self.recorder.on_level = lambda payload: self._emit("audio", payload)
        if self.wake is not None:
            self.wake.set_callback(self._on_wake)
            if hasattr(self.wake, "noise_floor"):
                noise_floor = self.wake.noise_floor
                self.recorder.noise_source = lambda: noise_floor.value
                self.wake.on_audio = lambda payload: self._emit("audio", payload)
                self.wake.on_microphone = lambda connected: self._emit("microphone", connected)
                self.wake.set_hearing_profile(self.hearing_profile)

    def _interrupted(self):
        return self._shutdown.is_set() or self._turn_cancelled.is_set()

    def set_language_mode(self, mode):
        with self._lock:
            if mode not in LANGUAGES or self._shutdown.is_set() or self._state not in (State.STARTING, State.STANDBY):
                return False
            self._apply_language_mode(mode)
            return True

    def _apply_language_mode(self, mode):
        self.language_mode = mode
        self.stt.language = "hi" if mode == "hinglish" else None if mode == "auto" else mode
        if mode != "auto":
            self._reply_language = "en" if mode == "en" else "hi"
        self._emit("language", mode)

    def cancel_turn(self):
        """Signal cancellation without touching native locks on the Qt thread."""
        with self._lock:
            if self._shutdown.is_set() or self._state in (State.STARTING, State.STANDBY, State.ERROR, State.SHUTTING_DOWN):
                return False
            self._turn_cancelled.set()
            self._emit("notice", "Stopping this turn… A request already sent may take a moment to finish.")
            return True

    def set_hearing_profile(self, profile):
        with self._lock:
            if profile not in PROFILES or self._shutdown.is_set() or self._state not in (State.STARTING, State.STANDBY):
                return False
            self._apply_hearing_profile(profile)
            return True

    def _apply_hearing_profile(self, profile):
        self.hearing_profile = profile
        for service in (self.recorder, self.wake):
            setter = getattr(service, "set_hearing_profile", None)
            if setter:
                setter(profile)
        self._emit("hearing", profile)

    @property
    def state(self):
        with self._lock:
            return self._state

    def set_state(self, new):
        with self._lock:
            old = self._state
            if new == old:
                return
            try:
                assert_transition(old, new)
            except IllegalTransition:
                log.warning("Ignored illegal transition %s -> %s", old.value, new.value)
                return
            self._state = new
        log.info("state %s -> %s", old.value, new.value)
        self._emit("state", new.value)
        if self.on_state_change is not None:
            try:
                self.on_state_change(new)
            except Exception:
                log.exception("on_state_change failed")

    def _emit(self, event, payload):
        if self.on_event is not None:
            try:
                self.on_event(event, payload)
            except Exception:
                log.exception("Desktop event callback failed")

    def request_listen(self):
        """Queue one recording from the desktop, with the same wake guards."""
        return self._queue_turn()

    def submit_text(self, text):
        text = text.strip()
        if not text or len(text) > 4000:
            return False
        return self._queue_turn(text)

    def _queue_turn(self, text=None):
        with self._lock:
            if self._shutdown.is_set() or self._state != State.STANDBY:
                return False
            if text is None and not self._listening_enabled:
                return False
            self._turn_cancelled.clear()
            self._pending_text = text
            self.set_state(State.WAKE_DETECTED)
            self._set_wake_enabled(False)
            self._wake_event.set()
            return True

    def set_listening_enabled(self, enabled):
        with self._lock:
            if self._shutdown.is_set() or self._state != State.STANDBY:
                return False
            # Block new wakes immediately; release/reopen the stream on the worker.
            self._listening_enabled = False
            self._set_wake_enabled(False)
            self._controls.put(("listening", bool(enabled)))
            self._wake_event.set()
            return True

    def set_speech_enabled(self, enabled):
        self._speech_enabled = bool(enabled)
        if not enabled:
            self.tts.stop()

    def clear_conversation(self):
        with self._lock:
            if self._shutdown.is_set() or self._state != State.STANDBY:
                return False
            self.context.clear()
            self._emit("clear", None)
            return True

    def process_controls(self):
        while not self._controls.empty() and not self._shutdown.is_set():
            kind, enabled = self._controls.get_nowait()
            if kind == "listening":
                if self.wake is not None:
                    self.wake.start() if enabled else self.wake.stop()
                with self._lock:
                    self._listening_enabled = enabled
                    self._set_wake_enabled(enabled and self.state == State.STANDBY)
                self._emit("listening", enabled)

    def _set_wake_enabled(self, enabled):
        if self.wake is not None:
            self.wake.set_enabled(enabled)

    def _speak(self, text, display=True):
        if self._interrupted():
            return False
        text = localize(text, self._reply_language)
        self.tts.language_hint = "hi" if reply_language(text, previous=self._reply_language) == "hi" else "en"
        if display:
            self._emit("message", {"role": "assistant", "text": text})
        if not self._speech_enabled:
            return True
        try:
            ok = self.tts.speak(text)
            if not ok:
                log.warning("Speech playback did not complete")
                if self._speech_enabled and not self._interrupted():
                    self._emit("notice", "Audio playback failed. You can still read the reply here. Check your speakers and internet connection.")
            return ok
        except Exception:
            log.exception("Speech playback failed")
            if not self._interrupted():
                self._emit("notice", "Couldn't play the voice reply. The answer is available in the conversation.")
            return False

    def startup(self):
        log.info("engine.startup")
        self._set_wake_enabled(False)
        if self.wake is not None:
            self.wake.start()
        if self.startup_greeting:
            if self._shutdown.wait(self.startup_greeting_delay):
                return
            self.set_state(State.SPEAKING)
            self._speak(self.startup_greeting)
            self._shutdown.wait(self.cooldown_seconds)
        self._back_to_standby()
        log.info("engine.standby (wake=%s)", self.wake is not None)

    def run(self):
        try:
            self.startup()
            while not self._shutdown.is_set():
                self.process_controls()
                if self.wake is None and self.continuous_without_wake:
                    self._on_wake()
                if self._wake_event.wait(0.2):
                    self.process_controls()
                    self.process_pending_wake()
        except Exception:
            self.set_state(State.ERROR)
            raise
        finally:
            self.request_shutdown()
            self._shutdown_sequence()

    def request_shutdown(self):
        self._shutdown.set()
        self._turn_cancelled.set()
        self._wake_event.set()
        for service, method in ((self.recorder, "stop"), (self.tts, "cancel"),
                                (self.player, "stop"), (self.ai, "cancel")):
            try:
                getattr(service, method, lambda: None)()
            except Exception:
                log.exception("%s during shutdown failed", method)

    def _shutdown_sequence(self):
        if self._cleaned:
            return
        self._cleaned = True
        self.set_state(State.SHUTTING_DOWN)
        self._set_wake_enabled(False)
        for service, method in ((self.wake, "stop"), (self.stt, "shutdown"),
                                (self.tts, "shutdown"), (self.ai, "shutdown")):
            try:
                getattr(service, method, lambda: None)()
            except Exception:
                log.exception("Service cleanup failed")

    def _on_wake(self):
        # Never record, call the AI, or play audio on the microphone thread.
        return self._queue_turn()

    def process_pending_wake(self):
        self._wake_event.clear()
        if self._shutdown.is_set() or self.state != State.WAKE_DETECTED:
            return
        text, self._pending_text = self._pending_text, None
        try:
            if self._interrupted():
                return
            if text is not None:
                self.set_state(State.THINKING)
                self._answer(text)
                return
            self.set_state(State.ACKNOWLEDGING)
            self.set_state(State.SPEAKING)
            self._speak(self.acknowledgement, display=False)
            if self._turn_cancelled.wait(self.cooldown_seconds):
                return
            self.set_state(State.LISTENING)
            self.handle_command()
        except Exception:
            log.exception("Command failed; recovering to standby")
        finally:
            if self._turn_cancelled.is_set() and not self._shutdown.is_set():
                self._emit("notice", "Cancelled. Ready for your next question.")
            self._back_to_standby()

    def handle_command(self):
        if self._interrupted():
            return
        try:
            audio = self.recorder.record()
            if self._interrupted():
                return
            if audio is None or audio.size == 0:
                if getattr(self.recorder, "last_error", False):
                    self._listening_feedback("I couldn't access the microphone. Please check its connection.")
                elif self.wake is not None:
                    self._listening_feedback("I didn't hear a question. Say hey Jarvis when you're ready.")
                return
            self.set_state(State.TRANSCRIBING)
            text = self.stt.transcribe(audio).strip()
            if self._interrupted():
                return
            if not text:
                self._listening_feedback("I couldn't understand that. Please say hey Jarvis and try again.")
                return
            self.set_state(State.THINKING)
            self._answer(text)
        except Exception:
            log.exception("Recording or transcription failed")
            self._listening_feedback("I had trouble hearing that. Please try again.")
        # process_pending_wake owns the single transition back to standby.
        # A second transition here could overwrite a newly queued wake event.

    def _answer(self, text):
        if self._interrupted():
            return
        self._emit("message", {"role": "user", "text": text})
        self._reply_language = reply_language(text, self.language_mode, self._reply_language)
        control = desktop_command(text) if self.on_event is not None else None
        if control is not None:
            action, reply = control
            if action == "clear_chat":
                self.context.clear()
            if action.startswith("hearing_"):
                self._apply_hearing_profile(action.removeprefix("hearing_"))
            if action.startswith("language_"):
                self._apply_language_mode(action.removeprefix("language_"))
            self._emit("ui", {"action": action})
            self.set_state(State.SPEAKING)
            self._speak(reply)
            self._turn_cancelled.wait(self.cooldown_seconds)
            return
        reply = local_reply(text, self.context)
        if reply is not None:
            reply = localize(reply, self._reply_language)
        if is_clear_command(text):
            self._emit("clear", None)
        if reply is not None and not is_history_control(text):
            self.context.add_turn(text, reply)
        if reply is None:
            messages = self.context.messages()
            if messages and messages[0].role == "system":
                messages[0].content += " Current local date and time: " + datetime.now().astimezone().isoformat()
                messages[0].content += instruction(self.language_mode, self._reply_language)
            try:
                reply = self.ai.chat(messages + [ChatMessage("user", text)])
                if not isinstance(reply, str) or not reply.strip():
                    raise AIProviderError("I didn't get an answer. Please try rephrasing your question.")
                if self._interrupted():
                    return
                self.context.add_turn(text, reply)
            except AIProviderError as exc:
                if self._interrupted():
                    return
                reply = str(exc)
                self._emit("notice", reply)
            except Exception:
                if self._interrupted():
                    return
                log.exception("AI request crashed")
                reply = "Something went wrong while I was thinking. Please try again."
                self._emit("notice", reply)
        if self._interrupted():
            return
        self.set_state(State.SPEAKING)
        self._speak(reply)
        self._turn_cancelled.wait(self.cooldown_seconds)

    def _listening_feedback(self, message):
        if not self._interrupted():
            self.set_state(State.SPEAKING)
            self._speak(message)
            self._turn_cancelled.wait(self.cooldown_seconds)

    def _back_to_standby(self):
        if not self._shutdown.is_set():
            self.set_state(State.STANDBY)
            self._set_wake_enabled(self._listening_enabled)
