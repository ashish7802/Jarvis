"""Hindi/Hinglish and English preferences for speech and local responses."""
import re

LANGUAGES = {"auto": "Auto · Hindi / English", "hi": "Hindi", "hinglish": "Hinglish", "en": "English"}
_HINDI_WORDS = set("mujhe mujko mera meri mere tum tumhara aap aapka kaise kaisa kaisi kya kyun kyu batao samjhao samjha dikhao karo karna chahiye caheya chaiye nahi nahin haan han hain hai ho raha rahi mai mein namaste yaar abhi wala wali baat bolo boliye suno".split())
_HINDI_MARKERS = set(
    "mujhe mujko mera meri mere hum humein hume tum tumhe tumhara tumhari "
    "aap aapko aapka aapki kaise kaisa kaisi kya kyun kyu kyunki kyuki "
    "bata batao samjhao samjha samajh dikhao karo karna karlo "
    "chahiye chaiye nahi nahin nhi haan han hain hai ho hua hui hu "
    "raha rahi rahe gaya gayi gaye kholo khol kholna chalao "
    "accha acha achha theek sahi yaar bhai mujhe apna apni iska iski "
    "uska uski isko usko aaj kal abhi thoda zyada kam kaam baat "
    "bol bolo bolna suno dekho dikhana padhna padho likho"
    .split()
)


def reply_language(text, mode="auto", previous="en"):
    if mode in ("hi", "hinglish"):
        return "hi"
    if mode == "en":
        return "en"
    if re.search(r"[\u0900-\u097f]", text):
        return "hi"
    words = set(re.findall(r"[a-z]+", text.casefold()))
    if words & _HINDI_MARKERS or len(words & _HINDI_WORDS) >= 2:
        return "hi"
    if len(words) <= 2 and words <= {
        "yes", "no", "ok", "okay", "sure", "continue", "thanks", "thank", "you",
        "hmm", "right", "got", "it",
    }:
        return previous
    return "en"


def instruction(mode, language):
    casual = (
        " For Hindi/Hinglish, talk like a friend — use everyday spoken Hinglish, NOT textbook Hindi. "
        "Mirror the user's casual vocabulary: laptop, app, settings, issue, ready, mood, simple — keep these in English. "
        "Use 'tum' NOT 'aap'. Use 'bata' NOT 'bataiye'. Use 'bol' NOT 'boliye'. "
        "An occasional yaar is fine, but not in every reply. "
        "Natural examples: 'हाँ बोलो, क्या हुआ?', 'ये app थोड़ा slow है, restart करके देख', 'कोई बात नहीं, anytime!' "
        "FORBIDDEN phrases — never use these: 'कृपया', 'अवश्य', 'प्रतीत होता है', 'सहायता कर सकती हूँ', 'बताइए', "
        "'जी बिल्कुल', 'निश्चित रूप से', 'आपकी सेवा में'. These sound like a textbook or customer service script. "
        "Write Hindi words in Devanagari for spoken pronunciation. Devanagari ≠ formal Hindi. "
        "Keep familiar English words in English and use feminine self-reference: 'समझ गई', 'बता देती हूँ'. "
        "Explicit requests for formal or pure Hindi override this casual default."
    )
    if mode == "auto":
        return (
            " Match the language of the latest user message, not an older turn: "
            "English → relaxed English; Hindi/Hinglish → casual Hinglish. "
            "For very short neutral follow-ups keep the previous language. "
            f"Language hint for this turn: {'Hindi/Hinglish' if language == 'hi' else 'English'}; "
            "use the user's actual wording to resolve ambiguity."
            + casual
        )
    if mode == "en":
        return " The user selected English. Respond in friendly, natural English unless they explicitly request a language change."
    if mode == "hinglish":
        return " The user selected Hinglish: use their everyday Hindi-English mix." + casual
    return " The user selected Hindi: use everyday conversational Hindi with familiar English words." + casual


_HINDI = {
    "I'm having trouble reaching Groq. Please check your connection and try again.": "Groq से connect नहीं हो पा रहा। Internet check करके फिर try कर।",
    "Groq's usage limit was reached. Please try again later or check your quota.": "Groq की limit हो गई। थोड़ा बाद try कर, या quota check कर ले।",
    "My Groq access was denied. Please check the API key and its permissions.": "Groq का access नहीं मिला। API key check कर ले।",
    "My configured Groq model is unavailable. Please check the model setting.": "ये Groq model अभी available नहीं है। Model setting देख ले।",
    "I couldn't produce an answer. Please rephrase your question.": "इस बार जवाब नहीं बन पाया। थोड़ा अलग तरह से पूछ।",
    "I didn't get an answer. Please try rephrasing your question.": "जवाब नहीं मिला। थोड़ा अलग तरह से पूछोगे?",
    "I'll match your language: Hindi, Hinglish or English.": "Done, तुम जैसे बोलोगे वैसे ही बात करेंगे।",
    "Yeah, I'm here.": "हाँ, बोलो।",
    "Yes, Sir?": "हाँ, बोलो।",
    "Here are your controls.": "ये रहे controls।",
    "Controls hidden.": "Controls छुपा दिए।",
    "Here's our conversation.": "ये रही हमारी chat।",
    "Conversation hidden.": "चैट छुपा दी।",
    "The controls are in the system panel on the left.": "Controls बाईं तरफ़ system panel में हैं।",
    "I keep the core controls visible in the left panel; you can minimize the window to move it out of the way.": "ज़रूरी controls बाईं तरफ़ दिखते रहेंगे। चाहो तो window minimize कर लो।",
    "Our conversation is in the center panel.": "हमारी बातचीत बीच वाले panel में है।",
    "The conversation stays visible here; use Clear to remove its messages.": "बातचीत यहीं दिखती रहेगी। Messages हटाने के लिए Clear दबा दो।",
    "I've cleared our conversation.": "Chat clear कर दी।",
    "I've cleared this conversation. What would you like to discuss?": "Chat clear कर दी। अब बताओ क्या बात करनी है?",
    "There isn't an earlier answer to repeat.": "अभी दोहराने के लिए कोई पिछला जवाब नहीं है।",
    "Soft voice mode is on. I'm more sensitive to quiet speech.": "Soft voice mode on है। अब धीमी आवाज़ भी पकड़ूँगी।",
    "Balanced hearing is on.": "Balanced mode on है।",
    "Noisy room mode is on. Speak a little closer to the microphone.": "Noisy room mode on है। Mic के थोड़ा पास बोलना।",
    "I couldn't access the microphone. Please check its connection.": "Mic connect नहीं हो रहा। Connection check कर।",
    "I didn't hear anything. Try saying that again when you're ready.": "कुछ सुनाई नहीं दिया। Ready हो तो फिर बोलो।",
    "I didn't catch that. Could you say it another way?": "वो ठीक से समझ नहीं आया। थोड़ा अलग तरह से बोल।",
    "I had trouble hearing that. Please try again.": "आवाज़ clear नहीं आई। एक बार फिर बोल।",
    "Something went wrong while I was thinking. Please try again.": "जवाब बनाते वक्त कुछ गड़बड़ हो गई। फिर try कर।",
    "That calculation is undefined; you can't divide by zero.": "Zero से divide नहीं कर सकते, ये undefined है।",
    "Screen reading is off. Turn on Allow screen reading in the system panel or the orb's right-click menu.": "Screen reading off है। System panel में Allow screen reading on कर दो।",
    "I couldn't read any text from the active window. Open the app and try again.": "Active window में पढ़ने लायक text नहीं मिला। App खोलकर फिर try कर।",
    "I couldn't read the active window. Make sure the app is open and visible.": "Active window पढ़ नहीं पाई। Check कर कि app खुली और visible है।",
    "Screen reading is available in the Windows desktop app only.": "Screen पढ़ना सिर्फ Windows desktop app में है।",
    "Local desktop actions are available in the Windows desktop app only.": "ये desktop actions सिर्फ Windows desktop app में काम करते हैं।",
    "Screen reading needs the optional Windows accessibility component. Reinstall Jarvis with the current requirements.": "Screen पढ़ने के लिए Windows accessibility component चाहिए। Jarvis reinstall कर।",
    "Use a normal website address, like example.com.": "Normal website address दो, जैसे example.com।",
    "I couldn't open your browser.": "Browser नहीं खुल पाया।",
    "I couldn't open that website in your browser.": "Website browser में नहीं खुल पाई।",
    "I couldn't complete that desktop action. Check that the app or browser is available.": "वो desktop action पूरा नहीं हुआ। Check कर कि app या browser available है।",
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
    if text.startswith("Opening ") and text.endswith(" in your browser."):
        target = text.removeprefix("Opening ").removesuffix(" in your browser.")
        return f"Browser में {target} खोल रही हूँ।"
    if text == "Opening your browser.":
        return "Browser खोल रही हूँ।"
    if text.startswith("Opening "):
        return "खोल रही हूँ: " + text.removeprefix("Opening ").rstrip(".") + "।"
    if text.startswith("I couldn't find an installed app named "):
        target = text.removeprefix("I couldn't find an installed app named ").removesuffix(" in the Windows Start menu.")
        return f"Windows Start menu में {target} नाम की app नहीं मिली। उसका exact नाम try करो।"
    if text.startswith("I couldn't open ") and text.endswith(". Check that it is available."):
        target = text.removeprefix("I couldn't open ").removesuffix(". Check that it is available.")
        return f"{target} नहीं खुल पाई। एक बार check करो कि वो available है।"
    return _HINDI.get(text, text)
