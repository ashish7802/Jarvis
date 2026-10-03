from types import SimpleNamespace

from app.ai.base import ChatMessage
from app.ai.groq_provider import GroqProvider
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


def test_groq_preserves_history_and_system_instruction(monkeypatch):
    calls = []
    import threading

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": " Ready. "}}]}

    class Client:
        def __init__(self, **kwargs):
            pass

        def post(self, url, *, json):
            calls.append(json)
            return Response()

        def close(self):
            pass

    monkeypatch.setattr("app.ai.groq_provider.httpx.Client", Client)
    provider = GroqProvider.__new__(GroqProvider)
    provider._cancelled = threading.Event()
    provider.turn_cancelled = threading.Event()
    provider.max_attempts = 2
    provider._client = Client()
    provider._model = "test-model"
    answer = provider.chat([
        ChatMessage("system", "Be concise."), ChatMessage("user", "Hello"),
        ChatMessage("assistant", "Hi"), ChatMessage("user", "Ready?"),
    ])
    assert answer == "Ready."
    assert calls[0]["messages"] == [
        {"role": "system", "content": "Be concise."},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
        {"role": "user", "content": "Ready?"},
    ]


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
    (tmp_path / ".env").write_text("AI_PROVIDER=groq\n")
    assert config._resolve_env_file() == str(tmp_path / ".env")
