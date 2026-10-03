"""Conservative local gate for deciding whether hands-free speech is meant for Jarvis."""
import re


_JARVIS = re.compile(r"\bjarvis\b|\bjervis\b|जार्विस|जर्विस", re.IGNORECASE)
_DIRECT_PREFIXES = (
    "can you ", "could you ", "would you ", "will you ",
    "tell me ", "help me ", "do you know ", "what do you think",
    "explain ", "summarize ", "calculate ", "translate ",
    "open ", "find ", "show ", "remember ", "remind me ",
    "what time is it", "what is the time",
    "mujhe batao", "mujhe bata", "tum batao", "aap batao",
    "kya tum ", "suno ", "batao ", "samjhao ", "madad karo",
    "please ", "hey ", "hi ", "hello ",
)


def is_directed_to_jarvis(text: str) -> bool:
    normalized = " ".join(re.sub(r"[^\w\s]", " ", text.casefold()).split())
    if not normalized:
        return False
    if _JARVIS.search(normalized):
        return True
    return normalized.startswith(_DIRECT_PREFIXES)
