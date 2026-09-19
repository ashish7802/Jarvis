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
    casual = (
        " For Hindi/Hinglish, use everyday spoken Hinglish, not textbook or Sanskritized Hindi. "
        "Mirror the user's casual vocabulary: keep common words such as laptop, app, settings, issue, "
        "ready, mood and simple in English instead of translating everything into formal Hindi. "
        "Use tum rather than aap, unless the user asks for a formal tone. An occasional yaar is fine, not in every reply. "
        "Natural examples: 'हाँ, बोलो। क्या हुआ?' or 'ये app थोड़ा slow है। एक बार restart करके देखो।' "
        "Avoid phrases like 'कृपया', 'अवश्य', 'प्रतीत होता है' or 'सहायता कर सकती हूँ' in casual conversation. "
        "Write Hindi words in Devanagari for spoken pronunciation; that script does not mean formal Hindi. "
        "Keep familiar English words in English and use feminine self-reference, for example 'समझ गई'. "
        "An explicit request for formal or pure Hindi takes precedence over this casual default."
    )
    if mode == "auto":
        return (
            " Match the language of the latest user message, not an older turn: "
            "English questions get relaxed English answers; Hindi or Roman Hindi/Hinglish questions get casual Hinglish answers. "
            "For very short neutral follow-ups keep the previous language. "
            "For spoken pronunciation, write Hindi words in Devanagari and retain familiar English technical words in English. "
            f"The local language hint for this turn is {'Hindi/Hinglish' if language == 'hi' else 'English'}; "
            "use the actual user's wording to resolve ambiguity. Explicit language requests take precedence."
            + casual
        )
    if mode == "en":
        return " The user selected English replies. Respond in friendly, natural English unless they explicitly request a language change."
    if mode == "hinglish":
        return " The user selected casual Hinglish: use their everyday Hindi-English mix." + casual
    return " The user selected Hindi replies. Use everyday conversational Hindi with familiar English words unless they ask for pure Hindi." + casual


_HINDI = {
    "I'm having trouble reaching Gemini. Please check your connection and try again.": "Gemini से connect नहीं हो पा रहा। Internet check करके फिर try करो।",
    "Gemini's usage limit was reached. Please try again later or check your quota.": "Gemini की limit आ गई है। थोड़ा बाद try करो, या अपना quota check कर लो।",
    "My Gemini access was denied. Please check the API key and its permissions.": "Gemini का access नहीं मिला। API key और उसकी permissions check कर लो।",
    "My configured Gemini model is unavailable. Please check the model setting.": "ये Gemini model अभी available नहीं है। Model setting check कर लो।",
    "I couldn't produce an answer. Please rephrase your question.": "इस बार जवाब नहीं बन पाया। थोड़ा अलग तरह से पूछोगे?",
    "I didn't get an answer. Please try rephrasing your question.": "जवाब नहीं मिला। थोड़ा अलग तरह से पूछोगे?",
    "I'll match your language: Hindi, Hinglish or English.": "Done, तुम जैसे बोलोगे वैसे ही बात करेंगे। Hindi-English mix भी चलेगा।",
    "Yeah, I'm here.": "हाँ, बोलो।",
    "Yes, Sir?": "हाँ, बोलो।",
    "Here are your controls.": "ये रहे controls।",
    "Controls hidden.": "Controls छुपा दिए।",
    "Here's our conversation.": "ये रही हमारी chat।",
    "Conversation hidden.": "चैट छुपा दी है।",
    "I've cleared our conversation.": "Chat clear कर दी।",
    "I've cleared this conversation. What would you like to discuss?": "Chat clear कर दी। अब क्या बात करें?",
    "There isn't an earlier answer to repeat.": "अभी दोहराने के लिए कोई पिछला जवाब नहीं है।",
    "Soft voice mode is on. I'm more sensitive to quiet speech.": "Soft voice mode on है। अब धीमी आवाज़ भी पकड़ने की कोशिश करूँगी।",
    "Balanced hearing is on.": "Balanced mode on है।",
    "Noisy room mode is on. Speak a little closer to the microphone.": "Noisy room mode on है। Mic के थोड़ा पास बोलना।",
    "I couldn't access the microphone. Please check its connection.": "Mic connect नहीं हो रहा। उसका connection check कर लो।",
    "I didn't hear a question. Say hey Jarvis when you're ready.": "सुनाई नहीं दिया। Hey Jarvis बोलकर फिर से पूछना।",
    "I couldn't understand that. Please say hey Jarvis and try again.": "ठीक से समझ नहीं आया। Hey Jarvis बोलकर एक बार फिर कहोगे?",
    "I had trouble hearing that. Please try again.": "आवाज़ clear नहीं आई। एक बार फिर बोलना।",
    "Something went wrong while I was thinking. Please try again.": "जवाब बनाते वक्त कुछ गड़बड़ हो गई। एक बार फिर try करो।",
    "That calculation is undefined; you can't divide by zero.": "Zero से divide नहीं कर सकते, इसका result defined नहीं है।",
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
