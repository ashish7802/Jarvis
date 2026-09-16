from types import SimpleNamespace

from app.ai.base import ChatMessage
from app.ai.gemini_provider import GeminiProvider
from app.tts.service import TTSService
from app.wakeword import detector


def test_model_load_failure_uses_energy_fallback(monkeypatch):
    def fail(self):
        raise RuntimeError("missing model assets")
    monkeypatch.setattr(detector.OpenWakeWordDetector, "_load_model", fail)
    assert detector.build_wake_word(enabled=True).name == "energy"


def test_tts_synthesis_failure_is_not_success(monkeypatch, tmp_path):
    tts = TTSService(cache_dir=tmp_path)
    tts.attach_player(SimpleNamespace())
    monkeypatch.setattr(tts, "_synthesize_sync", lambda text: None)
    assert tts.speak("Hello.") is False


def test_gemini_preserves_history_and_system_instruction():
    calls = []
    def generate_content(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(text=" Ready. ")
    provider = GeminiProvider.__new__(GeminiProvider)
    import threading
    provider._cancelled = threading.Event()
    provider.turn_cancelled = threading.Event()
    provider.max_attempts = 2
    provider._client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    provider._model_name = "test-model"
    answer = provider.chat([
        ChatMessage("system", "Be concise."), ChatMessage("user", "Hello"),
        ChatMessage("assistant", "Hi"), ChatMessage("user", "Ready?"),
    ])
    assert answer == "Ready."
    assert calls[0]["config"]["system_instruction"] == "Be concise."
    assert [m["role"] for m in calls[0]["contents"]] == ["user", "model", "user"]
    assert calls[0]["contents"][-1]["parts"] == [{"text": "Ready?"}]


def test_check_fails_when_stt_cannot_load(monkeypatch):
    import app.main as main
    monkeypatch.setattr(main, "_configure", lambda: None)
    monkeypatch.setattr(main, "_build_ai", lambda settings: SimpleNamespace(name="mock"))
    def fail():
        raise RuntimeError("model unavailable")
    monkeypatch.setattr(main, "_build_stt", lambda settings: SimpleNamespace(_ensure_model=fail))
    assert main.main(["--check"]) == 3


def test_packaged_env_is_next_to_executable(monkeypatch, tmp_path):
    from app import config
    monkeypatch.delenv("JARVIS_ENV_FILE")
    monkeypatch.setattr(config.sys, "frozen", True, raising=False)
    monkeypatch.setattr(config.sys, "executable", str(tmp_path / "JARVIS.exe"))
    (tmp_path / ".env").write_text("AI_PROVIDER=gemini\n")
    assert config._resolve_env_file() == str(tmp_path / ".env")
