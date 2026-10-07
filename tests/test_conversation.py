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
    assert len(msgs) <= 4
    assert msgs[1].role == "user"


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


def test_fast_greetings_local_reply():
    from app.assistant.commands import local_reply
    ctx = ConversationContext(system_prompt="sys")
    assert "Hello" in local_reply("hi", ctx)
    assert "JARVIS" in local_reply("who are you", ctx)
    assert "नमस्ते" in local_reply("namaste", ctx)
    assert "JARVIS" in local_reply("kaise ho", ctx) or "बढ़िया" in local_reply("kaise ho", ctx)


def test_ambiguity_clarification_local_reply():
    from app.assistant.commands import local_reply
    ctx = ConversationContext(system_prompt="sys")
    assert "Which application or website" in local_reply("open", ctx)
    assert "remind you about" in local_reply("remind me", ctx)
    assert "note" in local_reply("take note", ctx)
    assert "कैलकुलेट" in local_reply("ginti karo", ctx)
    assert "सर्च" in local_reply("dhoondo", ctx)


def test_memory_queries_local_reply():
    from app.assistant.commands import local_reply
    ctx = ConversationContext(system_prompt="sys")
    ctx.add_user("What is the capital of France?")
    ctx.add_assistant("Paris")
    ctx.add_user("What did I just ask?")
    query_reply = local_reply("what did i just ask", ctx)
    assert "capital of France" in query_reply

