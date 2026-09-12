"""Exact voice controls; ordinary sentences go to the language model."""
import re
from datetime import datetime
from app.assistant.calculator import calculation_reply

_REPEAT = {"repeat", "repeat that", "say that again", "repeat your answer"}
_CLEAR = {"clear conversation", "clear our conversation", "forget this conversation", "start a new conversation"}


def _normalize(text):
    return " ".join(re.sub(r"[^\w\s]", "", text.casefold()).split())


def is_history_control(text):
    return _normalize(text) in _REPEAT | _CLEAR


def local_reply(text, context, now=None):
    command = _normalize(text)
    if command in _REPEAT:
        return context.last_assistant() or "There isn't an earlier answer to repeat."
    if command in _CLEAR:
        context.clear()
        return "I've cleared this conversation. What would you like to discuss?"
    if command in {"what time is it", "whats the time", "tell me the time"}:
        return f"It's {(now or datetime.now().astimezone()).strftime('%I:%M %p').lstrip('0')}."
    if command in {"what is todays date", "whats todays date", "what day is it", "tell me the date"}:
        return (now or datetime.now().astimezone()).strftime("Today is %A, %d %B %Y.")
    return calculation_reply(text)
