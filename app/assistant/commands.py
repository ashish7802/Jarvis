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
    "show_controls": "The controls are in the system panel on the left.",
    "hide_controls": "I keep the core controls visible in the left panel; you can minimize the window to move it out of the way.",
    "show_chat": "Our conversation is in the center panel.",
    "hide_chat": "The conversation stays visible here; use Clear to remove its messages.",
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


_FAST_GREETINGS = {
    _normalize("hi"): "Hey! Kya scene hai?",
    _normalize("hello"): "Hello! Bol, kya chal raha hai?",
    _normalize("hey"): "Hey! Bolo bolo.",
    _normalize("hey jarvis"): "Haan, bol! Kya chahiye?",
    _normalize("hi jarvis"): "Hey! Haan bolo.",
    _normalize("hello jarvis"): "Hello! Bol, kya kar sakta hoon?",
    _normalize("good morning"): "Good morning! Aaj ka din acha jaaye. 🌅",
    _normalize("good evening"): "Good evening! Kaise chal raha hai sab?",
    _normalize("good night"): "Good night! Achi neend aaye. 🌙",
    _normalize("how are you"): "Badhiya! Tum batao, kya haal hai?",
    _normalize("who are you"): "JARVIS hoon — tumhara personal AI dost. Jo puchna hai pucho.",
    _normalize("what is your name"): "JARVIS — naam toh suna hi hoga. 😄",
    _normalize("whats your name"): "JARVIS naam hai mera. Bolo, kya karna hai?",
    _normalize("thank you"): "Koi baat nahi! Anytime.",
    _normalize("thanks"): "No worries! 👍",
    _normalize("bye"): "Chal phir, baad mein milte hain!",
    _normalize("goodbye"): "Bye bye! Take care. 👋",
    _normalize("are you there"): "Haan haan, idhar hi hoon. Bol.",
    _normalize("are you listening"): "Haan, sun raha hoon. Bolo kya hai.",
    _normalize("namaste"): "नमस्ते! बोलो, क्या चाहिए?",
    _normalize("namaskar"): "नमस्कार! बताओ क्या करना है?",
    _normalize("kaise ho"): "बढ़िया हूँ! तुम बताओ, सब ठीक?",
    _normalize("kaise ho tum"): "एकदम मस्त! तुम सुनाओ, क्या चल रहा है?",
    _normalize("kya haal hai"): "सब बढ़िया! तुम बताओ?",
    _normalize("tum kaun ho"): "JARVIS हूँ — तुम्हारी personal AI दोस्त। बोलो क्या करना है।",
    _normalize("kaun ho tum"): "JARVIS हूँ, तुम्हारी AI दोस्त। पूछो जो पूछना है।",
    _normalize("aap kaun hain"): "JARVIS हूँ — तुम्हारी personal voice assistant।",
    _normalize("tera naam kya hai"): "JARVIS है मेरा नाम।",
    _normalize("tumhara naam kya hai"): "JARVIS — तुम्हारी AI दोस्त। 😊",
    _normalize("shukriya"): "अरे कोई बात नहीं! कभी भी बोलना।",
    _normalize("dhanyawad"): "कोई बात नहीं! और कुछ हो तो बोलो।",
    _normalize("alvida"): "अलविदा! बाद में मिलते हैं। 👋",
    _normalize("phir milenge"): "फिर मिलेंगे! ख्याल रखना।",
    _normalize("kya tum sun rahe ho"): "हाँ हाँ, सुन रही हूँ! बोलो क्या काम है?",
}

_AMBIGUOUS_CLARIFICATIONS = {
    _normalize("open"): "कौन सी app या website खोलनी है?",
    _normalize("open app"): "कौन सी app? नाम बोलो।",
    _normalize("kholo"): "क्या खोलना है बताओ?",
    _normalize("app kholo"): "कौन सी app? नाम बता दो।",
    _normalize("remind me"): "किस बारे में और कब remind करना है?",
    _normalize("set reminder"): "क्या remind करना है और कब?",
    _normalize("reminder"): "किस चीज़ का reminder लगाना है?",
    _normalize("yaad dilao"): "किस बात की और कब याद दिलानी है?",
    _normalize("reminder lagao"): "किस चीज़ का reminder? बताओ।",
    _normalize("take note"): "क्या note लिखना है?",
    _normalize("write note"): "बताओ, क्या लिखूँ?",
    _normalize("note"): "कौन सा note? बोलो क्या लिखना है।",
    _normalize("note likho"): "बोलो, क्या लिखूँ?",
    _normalize("note karo"): "क्या save करना है? बोलो।",
    _normalize("calculate"): "क्या calculate करना है?",
    _normalize("hisab karo"): "बोलो, क्या हिसाब करना है?",
    _normalize("ginti karo"): "क्या calculate करूँ?",
    _normalize("search"): "क्या search करना है?",
    _normalize("dhoondo"): "क्या ढूँढना है? बताओ।",
    _normalize("pata karo"): "क्या पता करना है?",
}

_MEMORY_QUERIES = {
    _normalize("what did i just ask"),
    _normalize("pehle kya pucha tha"),
    _normalize("pichla sawal"),
    _normalize("my last question"),
}


def _get_last_user_query(context):
    msgs = context.messages()
    user_msgs = [m.content for m in msgs if m.role == "user"]
    if len(user_msgs) >= 2:
        return f'Earlier you asked: "{user_msgs[-2]}"'
    elif len(user_msgs) == 1:
        return f'Earlier you asked: "{user_msgs[-1]}"'
    return "You haven't asked an earlier question in this session."


def local_reply(text, context, now=None):
    command = _normalize(text)
    if command in _REPEAT:
        return context.last_assistant() or "There isn't an earlier answer to repeat."
    if command in _CLEAR:
        context.clear()
        return "I've cleared this conversation. What would you like to discuss?"
    if command in _FAST_GREETINGS:
        return _FAST_GREETINGS[command]
    if command in _AMBIGUOUS_CLARIFICATIONS:
        return _AMBIGUOUS_CLARIFICATIONS[command]
    if command in _MEMORY_QUERIES:
        return _get_last_user_query(context)
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
