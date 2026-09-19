"""Review real Gemini conversational style and play two sample answers.

Uses synthetic text only; no microphone recording or STT model loading.
The JSON preserves the replies for human review; checks alone cannot rate tone.
"""
import json
import re
from types import SimpleNamespace

from app.assistant.engine import AssistantEngine
from app.audio.recorder import Player
from app.config import get_settings
from app.main import _build_ai, _build_tts


def main():
    settings = get_settings()
    events = []
    tts = _build_tts(settings)
    player = Player()
    tts.attach_player(player)
    engine = AssistantEngine(
        ai=_build_ai(settings), stt=SimpleNamespace(language=None), tts=tts,
        wake=None, recorder=SimpleNamespace(), player=player,
        cooldown_seconds=0, continuous_without_wake=False,
        on_event=lambda *event: events.append(event), language_mode="auto",
    )
    result = {"passed": False, "samples": []}
    try:
        engine.set_speech_enabled(False)
        engine.startup()
        prompts = [
            ("hinglish", "yaar laptop slow chal raha hai, ek simple tip de na"),
            ("hinglish", "aaj mood thoda off hai yaar, bas baat karni thi"),
            ("hinglish", "tu sach mein insaan hai ya AI?"),
            ("hindi", "मुझे कंप्यूटर क्या होता है, आसान भाषा में समझाओ"),
            ("english", "Explain why a laptop gets slow in one short English sentence."),
        ]
        for language, prompt in prompts:
            engine.context.clear()
            assert engine.submit_text(prompt)
            engine.process_pending_wake()
            answer = engine.context.last_assistant()
            assert answer, "Gemini returned no answer"
            hindi = bool(re.search(r"[\u0900-\u097f]", answer))
            assert hindi == (language != "english"), "Wrong reply language"
            if language == "hinglish":
                assert not any(word in answer for word in ("कृपया", "प्रतीत", "महोदय", "कीजिए")), "Formal wording in casual sample"
            result["samples"].append({"language": language, "prompt": prompt, "reply": answer})
            print(f"Generated {language} sample", flush=True)
        engine.set_speech_enabled(True)
        for sample in (result["samples"][0], result["samples"][-1]):
            tts.language_hint = "en" if sample["language"] == "english" else "hi"
            assert tts.speak(sample["reply"]), "Sample speech playback failed"
        assert not any(kind == "notice" for kind, _ in events), "Service reported a problem"
        result["passed"] = True
        print("PASS: real conversational samples, language switching and speech", flush=True)
    finally:
        engine.request_shutdown()
        engine._shutdown_sequence()
        settings.logs_dir.mkdir(parents=True, exist_ok=True)
        (settings.logs_dir / "style-check.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
