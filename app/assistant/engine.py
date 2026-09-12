"""Voice assistant engine. Wake callbacks enqueue; the main thread runs commands."""
from datetime import datetime
import logging
import threading

from app.ai.base import AIProviderError, ChatMessage
from app.assistant.commands import local_reply, is_history_control
from app.assistant.conversation import ConversationContext
from app.assistant.states import IllegalTransition, State, assert_transition

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
                 user_name="", context_messages=21, cooldown_seconds=0.4):
        self.ai, self.stt, self.tts = ai, stt, tts
        self.wake, self.recorder, self.player = wake, recorder, player
        self.startup_greeting = startup_greeting
        self.startup_greeting_delay = startup_greeting_delay
        self.acknowledgement = acknowledgement
        self.on_state_change = on_state_change
        self.cooldown_seconds = cooldown_seconds
        prompt = SYSTEM_PROMPT + (f" The user's preferred name is {user_name}." if user_name else "")
        self.context = ConversationContext(prompt, max_messages=context_messages)
        self._state = State.STARTING
        self._lock = threading.RLock()
        self._wake_event = threading.Event()
        self._shutdown = threading.Event()
        self._cleaned = False
        if self.wake is not None:
            self.wake.set_callback(self._on_wake)

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
        if self.on_state_change is not None:
            try:
                self.on_state_change(new)
            except Exception:
                log.exception("on_state_change failed")

    def _set_wake_enabled(self, enabled):
        if self.wake is not None:
            self.wake.set_enabled(enabled)

    def _speak(self, text):
        if self._shutdown.is_set():
            return False
        try:
            ok = self.tts.speak(text)
            if not ok:
                log.warning("Speech playback did not complete")
            return ok
        except Exception:
            log.exception("Speech playback failed")
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
                if self.wake is None:
                    self._on_wake()
                if self._wake_event.wait(0.5):
                    self.process_pending_wake()
        except Exception:
            self.set_state(State.ERROR)
            raise
        finally:
            self.request_shutdown()
            self._shutdown_sequence()

    def request_shutdown(self):
        self._shutdown.set()
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
        with self._lock:
            if self._shutdown.is_set() or self._state != State.STANDBY:
                return
            self.set_state(State.WAKE_DETECTED)
            self._set_wake_enabled(False)
            self._wake_event.set()

    def process_pending_wake(self):
        self._wake_event.clear()
        if self._shutdown.is_set() or self.state != State.WAKE_DETECTED:
            return
        try:
            self.set_state(State.ACKNOWLEDGING)
            self.set_state(State.SPEAKING)
            self._speak(self.acknowledgement)
            if self._shutdown.wait(self.cooldown_seconds):
                return
            self.set_state(State.LISTENING)
            self.handle_command()
        except Exception:
            log.exception("Command failed; recovering to standby")
        finally:
            self._back_to_standby()

    def handle_command(self):
        if self._shutdown.is_set():
            return
        try:
            audio = self.recorder.record()
            if self._shutdown.is_set():
                return
            if audio is None or audio.size == 0:
                if getattr(self.recorder, "last_error", False):
                    self._listening_feedback("I couldn't access the microphone. Please check its connection.")
                elif self.wake is not None:
                    self._listening_feedback("I didn't hear a question. Say hey Jarvis when you're ready.")
                return
            text = self.stt.transcribe(audio).strip()
            if self._shutdown.is_set():
                return
            if not text:
                self._listening_feedback("I couldn't understand that. Please say hey Jarvis and try again.")
                return
            self.set_state(State.THINKING)
            reply = local_reply(text, self.context)
            if reply is not None and not is_history_control(text):
                self.context.add_turn(text, reply)
            if reply is None:
                messages = self.context.messages()
                if messages and messages[0].role == "system":
                    messages[0].content += " Current local date and time: " + datetime.now().astimezone().isoformat()
                try:
                    reply = self.ai.chat(messages + [ChatMessage("user", text)])
                    if not isinstance(reply, str) or not reply.strip():
                        raise AIProviderError("I didn't get an answer. Please try rephrasing your question.")
                    if self._shutdown.is_set():
                        return
                    self.context.add_turn(text, reply)
                except AIProviderError as exc:
                    reply = str(exc)
                except Exception:
                    log.exception("AI request crashed")
                    reply = "Something went wrong while I was thinking. Please try again."
            if self._shutdown.is_set():
                return
            self.set_state(State.SPEAKING)
            self._speak(reply)
            self._shutdown.wait(self.cooldown_seconds)
        except Exception:
            log.exception("Recording or transcription failed")
            self._listening_feedback("I had trouble hearing that. Please try again.")
        # process_pending_wake owns the single transition back to standby.
        # A second transition here could overwrite a newly queued wake event.

    def _listening_feedback(self, message):
        if not self._shutdown.is_set():
            self.set_state(State.SPEAKING)
            self._speak(message)
            self._shutdown.wait(self.cooldown_seconds)

    def _back_to_standby(self):
        if not self._shutdown.is_set():
            self.set_state(State.STANDBY)
            self._set_wake_enabled(True)
