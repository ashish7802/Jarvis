from __future__ import annotations

import enum


class State(str, enum.Enum):
    STARTING = "STARTING"
    STANDBY = "STANDBY"
    WAKE_DETECTED = "WAKE_DETECTED"
    ACKNOWLEDGING = "ACKNOWLEDGING"
    LISTENING = "LISTENING"
    TRANSCRIBING = "TRANSCRIBING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    ERROR = "ERROR"
    SHUTTING_DOWN = "SHUTTING_DOWN"


# Legal transitions. Anything not listed is invalid.
_ALLOWED: dict[State, set[State]] = {
    State.STARTING: {State.SPEAKING, State.STANDBY, State.ERROR, State.SHUTTING_DOWN},
    State.STANDBY: {
        State.WAKE_DETECTED,
        State.LISTENING,  # direct listen for test/utility paths
        State.ERROR,
        State.SHUTTING_DOWN,
    },
    State.WAKE_DETECTED: {State.ACKNOWLEDGING, State.THINKING, State.ERROR, State.STANDBY, State.SHUTTING_DOWN},
    State.ACKNOWLEDGING: {State.SPEAKING, State.LISTENING, State.ERROR, State.STANDBY, State.SHUTTING_DOWN},
    State.LISTENING: {State.TRANSCRIBING, State.THINKING, State.SPEAKING, State.STANDBY, State.ERROR, State.SHUTTING_DOWN},
    State.TRANSCRIBING: {State.THINKING, State.SPEAKING, State.STANDBY, State.ERROR, State.SHUTTING_DOWN},
    State.THINKING: {State.SPEAKING, State.STANDBY, State.ERROR, State.SHUTTING_DOWN},
    State.SPEAKING: {State.STANDBY, State.LISTENING, State.ERROR, State.SHUTTING_DOWN},
    State.ERROR: {State.STANDBY, State.SHUTTING_DOWN},
    State.SHUTTING_DOWN: set(),
}


class IllegalTransition(RuntimeError):
    pass


def can_transition(src: State, dst: State) -> bool:
    return dst in _ALLOWED.get(src, set())


def assert_transition(src: State, dst: State) -> None:
    if not can_transition(src, dst):
        raise IllegalTransition(f"Illegal state transition: {src.value} -> {dst.value}")


def is_quiet_state(s: State) -> bool:
    """States during which the wake-word detector should be active."""
    return s == State.STANDBY


def is_self_trigger_risky(s: State) -> bool:
    """States during which JARVIS is producing audio (don't listen for wake)."""
    return s in (State.SPEAKING, State.ACKNOWLEDGING, State.STARTING)
