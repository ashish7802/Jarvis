"""Exact voice controls; ordinary sentences go to the language model."""
from dataclasses import dataclass
import re
from datetime import datetime
from app.assistant.calculator import calculation_reply
from app.assistant.productivity import duration_from_request

_REPEAT_PHRASES = {"repeat", "repeat that", "say that again", "repeat your answer", "phir se bolo", "dobara bolo", "फिर से बोलो", "दोबारा बोलो"}
_CLEAR_PHRASES = {"clear conversation", "clear our conversation", "forget this conversation", "start a new conversation", "baat bhool jao", "बातचीत भूल जाओ"}


def _normalize(text):
    return " ".join(re.sub(r"[^\w\s]", "", text.casefold()).split())


_REPEAT = {_normalize(x) for x in _REPEAT_PHRASES}
_CLEAR = {_normalize(x) for x in _CLEAR_PHRASES}


def is_history_control(text):
    return _normalize(text) in _REPEAT | _CLEAR


def is_clear_command(text):
    return _normalize(text) in _CLEAR


_DESKTOP_COMMANDS = {
    "language_hi": ("speak hindi", "hindi mode", "hindi mein baat karo", "hindi me baat karo", "ab hindi mein baat karo", "हिंदी में बात करो", "हिन्दी में बात करो", "हिंदी बोलो"),
    "language_en": ("speak english", "english mode", "speak in english", "english mein baat karo", "english me baat karo", "ab english mein baat karo", "इंग्लिश में बात करो", "अंग्रेजी में बात करो", "अंग्रेज़ी में बात करो"),
    "language_hinglish": ("speak hinglish", "hinglish mode", "hinglish mein baat karo", "हिंग्लिश में बात करो"),
    "language_auto": ("auto language", "automatic language", "match my language", "meri language mein baat karo", "मेरी भाषा में बात करो", "मेरी लैंग्वेज में बात करो"),
    "hearing_soft": ("soft voice mode", "enable soft voice", "halki awaz mode", "धीमी आवाज मोड", "सॉफ्ट वॉइस मोड"),
    "hearing_balanced": ("balanced mode", "normal hearing mode", "बैलेंस्ड मोड"),
    "hearing_noisy": ("noisy room mode", "noise mode", "शोर वाला मोड"),
    "show_controls": ("show controls", "show the controls", "open controls", "show settings", "open settings", "show features", "controls dikhao", "settings dikhao", "features dikhao", "कंट्रोल दिखाओ", "कंट्रोल्स दिखाओ", "सेटिंग्स दिखाओ", "सेटिंग दिखाओ", "फीचर्स दिखाओ"),
    "hide_controls": ("hide controls", "hide the controls", "close controls", "hide settings", "close settings", "hide features", "controls chhupao", "controls chupao", "settings band karo", "कंट्रोल छुपाओ", "कंट्रोल्स छुपाओ", "सेटिंग बंद करो", "सेटिंग्स बंद करो", "सेटिंग्स छुपाओ"),
    "show_chat": ("show chat", "show conversation", "show my chat", "chat dikhao", "conversation dikhao", "चैट दिखाओ", "बातचीत दिखाओ"),
    "hide_chat": ("hide chat", "hide conversation", "close chat", "chat chhupao", "chat chupao", "chat band karo", "चैट छुपाओ", "चैट बंद करो"),
    "clear_chat": ("clear chat", "clear the chat", "chat clear karo", "चैट साफ करो", "चैट क्लियर करो"),
}
_DESKTOP_REPLIES = {
    "language_hi": "ठीक है, हिंदी में बात करते हैं।",
    "language_en": "Sure, I'll speak English now.",
    "language_hinglish": "Done, अब अपनी वाली Hindi-English mix में बात करते हैं।",
    "language_auto": "I'll match your language: Hindi, Hinglish or English.",
    "hearing_soft": "Soft voice mode is on. I'm more sensitive to quiet speech.",
    "hearing_balanced": "Balanced hearing is on.",
    "hearing_noisy": "Noisy room mode is on. Speak a little closer to the microphone.",
    "show_controls": "Here are your controls.",
    "hide_controls": "Controls hidden.",
    "show_chat": "Here's our conversation.",
    "hide_chat": "Conversation hidden.",
    "clear_chat": "I've cleared our conversation.",
}


def desktop_command(text):
    """Only exact local UI commands act; discussing a feature is ordinary chat."""
    command = _normalize(text)
    for prefix in ("hey jarvis ", "jarvis ", "जार्विस ", "please "):
        if command.startswith(prefix):
            command = command[len(prefix):]
    if command.endswith(" please"):
        command = command[:-7]
    for action, phrases in _DESKTOP_COMMANDS.items():
        if command in {_normalize(phrase) for phrase in phrases}:
            return action, _DESKTOP_REPLIES[action]
    return None


def local_reply(text, context, now=None):
    command = _normalize(text)
    if command in _REPEAT:
        return context.last_assistant() or "There isn't an earlier answer to repeat."
    if command in _CLEAR:
        context.clear()
        return "I've cleared this conversation. What would you like to discuss?"
    if command in {_normalize(x) for x in ("what time is it", "whats the time", "tell me the time", "kitne baje hain", "time kya hai", "abhi kitne baje hain", "कितने बजे हैं", "अभी कितने बजे हैं", "टाइम क्या है")}:
        return f"It's {(now or datetime.now().astimezone()).strftime('%I:%M %p').lstrip('0')}."
    if command in {_normalize(x) for x in ("what is todays date", "whats todays date", "what day is it", "tell me the date", "aaj kya tarikh hai", "aaj ki date kya hai", "आज की तारीख क्या है", "आज कौन सा दिन है")}:
        return (now or datetime.now().astimezone()).strftime("Today is %A, %d %B %Y.")
    return calculation_reply(text)


@dataclass(frozen=True)
class ProductivityRequest:
    action: str
    text: str = ""
    title: str = ""
    query: str = ""
    due_at: datetime | None = None


def _clock_time(value: str, now: datetime) -> datetime | None:
    """Parse a small, unambiguous local-time vocabulary."""
    value = value.casefold().strip()
    tomorrow = value.startswith("tomorrow")
    if tomorrow:
        value = value.removeprefix("tomorrow").strip()
    value = re.sub(r"^(?:at|on)\s+", "", value)
    match = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", value)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    meridiem = match.group(3)
    if meridiem:
        if not 1 <= hour <= 12 or minute > 59:
            return None
        if meridiem == "pm" and hour != 12:
            hour += 12
        if meridiem == "am" and hour == 12:
            hour = 0
    elif hour > 23 or minute > 59:
        return None
    due = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if tomorrow or due <= now:
        from datetime import timedelta
        due += timedelta(days=1)
    return due


def parse_productivity_request(text, now=None):
    """Recognize safe local timer, reminder and note commands.

    The parser deliberately requires explicit phrases. Normal conversation
    continues to the configured AI provider instead of mutating local data.
    """
    now = now or datetime.now().astimezone()
    value = text.strip()
    normalized = _normalize(value)
    if normalized in {"show reminders", "list reminders", "what are my reminders", "pending reminders", "reminders dikhao", "meri reminders batao"}:
        return ProductivityRequest("list_reminders")
    if normalized in {"show notes", "list notes", "what are my notes", "notes dikhao", "meri notes batao"}:
        return ProductivityRequest("list_notes")

    cancel = re.fullmatch(r"(?:cancel|delete|remove)\s+(?:the\s+)?(?:reminder|timer)\s+(.+)", value, re.IGNORECASE)
    if cancel:
        return ProductivityRequest("cancel_reminder", query=cancel.group(1).strip())
    delete_note = re.fullmatch(r"(?:delete|remove)\s+(?:the\s+)?note\s+(.+)", value, re.IGNORECASE)
    if delete_note:
        return ProductivityRequest("delete_note", query=delete_note.group(1).strip())
    read_note = re.fullmatch(r"(?:read|open|show)\s+(?:my\s+)?note\s+(.+)", value, re.IGNORECASE)
    if read_note:
        return ProductivityRequest("read_note", query=read_note.group(1).strip())

    timer = re.fullmatch(
        r"(?:set|start|create)\s+(?:a\s+)?timer\s+(?:for\s+)?(.+?)(?:\s+(?:to|for)\s+(.+))?",
        value,
        re.IGNORECASE,
    )
    if timer:
        due_at = duration_from_request(timer.group(1), now)
        if due_at is not None:
            return ProductivityRequest("set_timer", text=(timer.group(2) or "your timer").strip(), due_at=due_at)

    reminder_in = re.fullmatch(r"remind\s+me\s+in\s+(.+?)\s+(?:to|that|about)\s+(.+)", value, re.IGNORECASE)
    if reminder_in:
        due_at = duration_from_request(reminder_in.group(1), now)
        if due_at is not None:
            return ProductivityRequest("set_reminder", text=reminder_in.group(2).strip(), due_at=due_at)

    reminder_at = re.fullmatch(
        r"remind\s+me\s+(?:(?:at|on)\s+)?(.+?)\s+(?:to|that|about)\s+(.+)",
        value,
        re.IGNORECASE,
    )
    if reminder_at:
        due_at = _clock_time(reminder_at.group(1), now)
        if due_at is not None:
            return ProductivityRequest("set_reminder", text=reminder_at.group(2).strip(), due_at=due_at)

    note = re.fullmatch(r"(?:take|save|write|remember)\s+(?:a\s+)?note(?:\s+(?:that|about|saying))?\s*[:,-]?\s*(.+)", value, re.IGNORECASE)
    if note:
        body = note.group(1).strip()
        return ProductivityRequest("add_note", text=body, title=body[:60])
    remember = re.fullmatch(r"remember\s+this\s*[:,-]?\s*(.+)", value, re.IGNORECASE)
    if remember:
        body = remember.group(1).strip()
        return ProductivityRequest("add_note", text=body, title=body[:60])
    return None
