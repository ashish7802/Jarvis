"""Verify real Gemini follow-up context with synthetic, non-personal text."""
from app.config import get_settings
from app.main import _build_ai
from app.assistant.conversation import ConversationContext
from app.assistant.engine import SYSTEM_PROMPT
from app.ai.base import ChatMessage


def main():
    ai = _build_ai(get_settings())
    context = ConversationContext(SYSTEM_PROMPT)
    try:
        prompt = "For this test, the project codename is Blue Lantern. Acknowledge in five words or fewer."
        reply = ai.chat(context.messages() + [ChatMessage("user", prompt)])
        context.add_turn(prompt, reply)
        answer = ai.chat(context.messages() + [ChatMessage("user", "What codename did I just give you? Reply with only the codename.")])
        assert "blue lantern" in answer.casefold(), "Gemini did not recall the supplied conversation context"
        print("PASS: real Gemini recalls the prior turn.")
    finally:
        ai.shutdown()


if __name__ == "__main__":
    main()
