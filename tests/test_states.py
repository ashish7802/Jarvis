from __future__ import annotations

import pytest

from app.assistant.states import (
    IllegalTransition,
    State,
    assert_transition,
    can_transition,
    is_quiet_state,
    is_self_trigger_risky,
)


def test_happy_path_transitions():
    chain = [
        State.STARTING,
        State.SPEAKING,  # startup greeting
        State.STANDBY,
        State.WAKE_DETECTED,
        State.ACKNOWLEDGING,
        State.SPEAKING,  # "Yes, Sir?"
        State.LISTENING,
        State.THINKING,
        State.SPEAKING,
        State.STANDBY,
    ]
    for a, b in zip(chain, chain[1:]):
        assert can_transition(a, b), f"{a} -> {b} should be allowed"


def test_illegal_transitions_rejected():
    with pytest.raises(IllegalTransition):
        assert_transition(State.STANDBY, State.THINKING)
    with pytest.raises(IllegalTransition):
        assert_transition(State.STARTING, State.LISTENING)
    with pytest.raises(IllegalTransition):
        assert_transition(State.SHUTTING_DOWN, State.STANDBY)


def test_error_recovers_to_standby():
    assert can_transition(State.ERROR, State.STANDBY)
    assert can_transition(State.SPEAKING, State.STANDBY)
    assert can_transition(State.LISTENING, State.STANDBY)


def test_quiet_and_self_trigger_states():
    assert is_quiet_state(State.STANDBY)
    assert not is_quiet_state(State.SPEAKING)
    assert is_self_trigger_risky(State.SPEAKING)
    assert is_self_trigger_risky(State.STARTING)
    assert is_self_trigger_risky(State.ACKNOWLEDGING)
    assert not is_self_trigger_risky(State.STANDBY)
    assert not is_self_trigger_risky(State.LISTENING)
