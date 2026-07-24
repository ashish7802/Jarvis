import pytest

from backend.core.conversation import ConversationManager


@pytest.mark.asyncio
async def test_history_is_trimmed_to_limit() -> None:
    manager = ConversationManager(max_history=2)

    manager.add_user_message("Hello")
    manager.add_assistant_message("Hi there")
    manager.add_user_message("How are you?")

    history = manager.get_history()

    assert len(history) == 2
    assert history[-1]["content"] == "How are you?"
