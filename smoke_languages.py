"""Verify real Hindi/English recognition, Gemini language switching and speech."""
import json
import re

from app.config import get_settings
from app.main import build_engine
from smoke_pipeline import as_pcm


def main():
    settings = get_settings()
    settings.startup_greeting_enabled = False
    settings.wake_word_enabled = False
    result = {"passed": False, "checks": []}
    events = []
    engine = build_engine(settings, on_event=lambda *event: events.append(event), desktop=True)
    paths = []
    try:
        engine.set_language_mode("auto")
        engine.startup()
        for lang, question in [("hi", "कंप्यूटर क्या है? एक लाइन में बताओ।"),
                               ("en", "What is a computer? Answer in one sentence.")]:
            engine.tts.language_hint = lang
            path = engine.tts._synthesize_sync(question)
            assert path, "Could not synthesize test question"
            paths.append(path)
            transcript = engine.stt.transcribe(as_pcm(path))
            assert transcript, "Recognition returned no text"
            is_hindi = bool(re.search(r"[\u0900-\u097f]", transcript))
            assert is_hindi == (lang == "hi"), f"Unexpected recognition language: {transcript}"
            if lang == "hi":
                assert "क्या" in transcript and "बताओ" in transcript, "Hindi question or instruction was misheard"
            assert engine.submit_text(transcript)
            engine.process_pending_wake()
            answer = engine.context.last_assistant()
            assert answer, "No Gemini answer"
            assert bool(re.search(r"[\u0900-\u097f]", answer)) == (lang == "hi"), "Gemini replied in the wrong language"
            result["checks"].append({"input_language": lang, "recognized_language": engine.stt.last_language,
                                     "recognized": transcript, "reply": answer})
            print(f"PASS: {lang} recognition, Gemini reply and voice", flush=True)
        engine.submit_text("yaar Python kya hai, ek line mein batao")
        engine.process_pending_wake()
        assert re.search(r"[\u0900-\u097f]", engine.context.last_assistant()), "Roman Hinglish did not get Hindi speech text"
        result["checks"].append({"input_language": "hinglish", "reply": engine.context.last_assistant()})
        assert not any(kind == "notice" and ("playback failed" in text or "Couldn't play" in text)
                       for kind, text in events), "Voice playback failed"
        result["passed"] = True
        print("PASS: Hinglish text, Hindi speech spelling and English switching", flush=True)
    finally:
        for path in paths:
            path.unlink(missing_ok=True)
        engine.request_shutdown()
        engine._shutdown_sequence()
        settings.logs_dir.mkdir(parents=True, exist_ok=True)
        (settings.logs_dir / "language-check.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
