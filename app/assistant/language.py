"""Hindi/Hinglish and English preferences for speech and local responses."""
import re

LANGUAGES = {"auto": "Auto · Hindi / English", "hi": "Hindi", "hinglish": "Hinglish", "en": "English"}
_HINDI_WORDS = set("mujhe mujko mera meri mere tum tumhara aap aapka kaise kaisa kaisi kya kyun kyu batao samjhao samjha dikhao karo karna chahiye caheya chaiye nahi nahin haan han hain hai ho raha rahi mai mein namaste yaar abhi wala wali baat bolo boliye suno".split())


def reply_language(text, mode="auto", previous="en"):
    if mode in ("hi", "hinglish"):
        return "hi"
    if mode == "en":
        return "en"
    if re.search(r"[\u0900-\u097f]", text):
        return "hi"
    words = set(re.findall(r"[a-z]+", text.casefold()))
    if len(words & _HINDI_WORDS) >= 2 or words & {"namaste", "samjhao", "batao", "dikhao"}:
        return "hi"
    if len(words) <= 2 and words <= {"yes", "no", "ok", "okay", "sure", "continue", "thanks", "hmm"}:
        return previous
    return "en"


def instruction(mode, language):
    if mode == "auto":
        return (
            " Match the language of the latest user message, not an older turn: "
            "English questions get English answers; Hindi or Roman Hindi/Hinglish questions get natural Hindi/Hinglish answers. "
            "For very short neutral follow-ups keep the previous language. "
            "For spoken pronunciation, write Hindi words in Devanagari and retain familiar English technical words in English. "
            f"The local language hint for this turn is {'Hindi/Hinglish' if language == 'hi' else 'English'}; "
            "use the actual user's wording to resolve ambiguity. Explicit language requests take precedence."
        )
    if mode == "en":
        return " The user selected English replies. Respond in natural English unless they explicitly request a language change."
    if mode == "hinglish":
        return " The user selected casual Hinglish: mix everyday Hindi with familiar English words, like a helpful friend. Write Hindi words in Devanagari for natural speech."
    return " The user selected Hindi replies. Respond in clear, natural Hindi in Devanagari, preserving names and necessary English technical terms."


_HINDI = {
    "I'm having trouble reaching Gemini. Please check your connection and try again.": "Gemini से कनेक्ट नहीं हो पा रहा। इंटरनेट देख कर फिर कोशिश कीजिए।",
    "Gemini's usage limit was reached. Please try again later or check your quota.": "Gemini की उपयोग सीमा पूरी हो गई है। थोड़ी देर बाद कोशिश कीजिए या अपना quota देखिए।",
    "My Gemini access was denied. Please check the API key and its permissions.": "Gemini का access नहीं मिला। API key और उसकी permissions देखिए।",
    "My configured Gemini model is unavailable. Please check the model setting.": "चुना हुआ Gemini model उपलब्ध नहीं है। उसकी setting देखिए।",
    "I couldn't produce an answer. Please rephrase your question.": "इस बार जवाब नहीं बन पाया। सवाल थोड़ा अलग तरह से पूछिए।",
    "I didn't get an answer. Please try rephrasing your question.": "जवाब नहीं मिला। सवाल थोड़ा अलग तरह से पूछिए।",
    "I'll match your language: Hindi, Hinglish or English.": "आप जिस भाषा में बोलेंगे, मैं उसी में जवाब दूँगा — हिंदी, Hinglish या English।",
    "Yes, Sir?": "हाँ, बोलिए।",
    "Here are your controls.": "ये रहे आपके कंट्रोल।",
    "Controls hidden.": "कंट्रोल छुपा दिए हैं।",
    "Here's our conversation.": "ये रही हमारी बातचीत।",
    "Conversation hidden.": "चैट छुपा दी है।",
    "I've cleared our conversation.": "हमारी बातचीत साफ कर दी है।",
    "I've cleared this conversation. What would you like to discuss?": "बातचीत साफ कर दी है। अब किस बारे में बात करें?",
    "There isn't an earlier answer to repeat.": "अभी दोहराने के लिए कोई पिछला जवाब नहीं है।",
    "Soft voice mode is on. I'm more sensitive to quiet speech.": "Soft voice mode चालू है। अब धीमी आवाज़ के लिए संवेदनशीलता बढ़ गई है।",
    "Balanced hearing is on.": "Balanced hearing चालू है।",
    "Noisy room mode is on. Speak a little closer to the microphone.": "Noisy room mode चालू है। माइक्रोफ़ोन के थोड़ा पास बोलिए।",
    "I couldn't access the microphone. Please check its connection.": "माइक्रोफ़ोन नहीं मिल रहा। उसका कनेक्शन देख लीजिए।",
    "I didn't hear a question. Say hey Jarvis when you're ready.": "आपका सवाल सुनाई नहीं दिया। तैयार हों तो Hey Jarvis कहिए।",
    "I couldn't understand that. Please say hey Jarvis and try again.": "ठीक से समझ नहीं आया। Hey Jarvis कहकर फिर से बोलिए।",
    "I had trouble hearing that. Please try again.": "सुनने में परेशानी हुई। एक बार फिर बोलिए।",
    "Something went wrong while I was thinking. Please try again.": "जवाब बनाते समय समस्या हुई। एक बार फिर कोशिश कीजिए।",
    "That calculation is undefined; you can't divide by zero.": "शून्य से भाग नहीं कर सकते। इस गणना का परिणाम परिभाषित नहीं है।",
}


def localize(text, language):
    if language != "hi":
        return text
    if text.startswith("The result is "):
        return "जवाब है " + text.removeprefix("The result is ").replace("approximately ", "लगभग ")
    if text.startswith("It's "):
        return "अभी " + text.removeprefix("It's ").rstrip(".") + " बजे हैं।"
    if text.startswith("Today is "):
        return "आज " + text.removeprefix("Today is ").rstrip(".") + " है।"
    return _HINDI.get(text, text)
