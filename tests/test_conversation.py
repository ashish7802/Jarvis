from __future__ import annotations

from app.assistant.conversation import ConversationContext


def test_initial_system_prompt_pinned():
    ctx = ConversationContext(system_prompt="You are JARVIS.")
    msgs = ctx.messages()
    assert msgs[0].role == "system"
    assert "You are JARVIS" in msgs[0].content


def test_add_user_and_assistant():
    ctx = ConversationContext(system_prompt="sys", max_messages=10)
    ctx.add_user("hello")
    ctx.add_assistant("hi")
    msgs = ctx.messages()
    assert [m.role for m in msgs] == ["system", "user", "assistant"]


def test_rolling_window_drops_oldest_user_keeps_system():
    ctx = ConversationContext(system_prompt="sys", max_messages=4)
    # system + up to 3 turns
    for i in range(5):
        ctx.add_user(f"u{i}")
        ctx.add_assistant(f"a{i}")
    msgs = ctx.messages()
    assert msgs[0].role == "system"
    assert len(msgs) == 4


def test_clear_resets_with_system_prompt():
    ctx = ConversationContext(system_prompt="sys")
    ctx.add_user("hi")
    ctx.add_assistant("hello")
    ctx.clear()
    msgs = ctx.messages()
    assert len(msgs) == 1
    assert msgs[0].role == "system"


def test_last_assistant_returns_most_recent():
    ctx = ConversationContext(system_prompt="sys")
    ctx.add_user("a?")
    ctx.add_assistant("first")
    ctx.add_user("b?")
    ctx.add_assistant("second")
    assert ctx.last_assistant() == "second"
