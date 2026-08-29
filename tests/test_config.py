from __future__ import annotations

import pytest

from app.config import get_settings, reset_settings_cache
from app.logging_config import setup_logging


def test_default_settings():
    reset_settings_cache()
    s = get_settings()
    assert s.jarvis_name == "Jarvis"
    assert s.ai_provider == "mock"
    assert s.wake_word == "jarvis"
    assert s.listen_timeout == 10.0
    assert s.silence_timeout == 1.5
    assert s.tts_voice == "en-US-GuyNeural"
    assert s.hotkey_exit == "Ctrl+Shift+J"


def test_env_override(tmp_path, monkeypatch):
    env = tmp_path / "test.env"
    env.write_text(
        "JARVIS_NAME=Friday\n"
        "AI_PROVIDER=openai\n"
        "OPENAI_API_KEY=sk-test\n"
        "LISTEN_TIMEOUT=3.5\n"
        "STARTUP_GREETING_DELAY=2\n"
    )
    monkeypatch.setenv("JARVIS_ENV_FILE", str(env))
    reset_settings_cache()
    s = get_settings()
    assert s.jarvis_name == "Friday"
    assert s.ai_provider == "openai"
    assert s.openai_api_key == "sk-test"
    assert s.listen_timeout == 3.5
    assert s.startup_greeting_delay == 2.0


def test_invalid_provider_raises(tmp_path, monkeypatch):
    env = tmp_path / "bad.env"
    env.write_text("AI_PROVIDER=nonsense\n")
    monkeypatch.setenv("JARVIS_ENV_FILE", str(env))
    reset_settings_cache()
    with pytest.raises(Exception):
        get_settings()


def test_negative_greeting_delay_clamps(tmp_path, monkeypatch):
    env = tmp_path / "neg.env"
    env.write_text("STARTUP_GREETING_DELAY=-5\n")
    monkeypatch.setenv("JARVIS_ENV_FILE", str(env))
    reset_settings_cache()
    s = get_settings()
    assert s.startup_greeting_delay == 0.0


def test_invalid_listen_timeout_raises(tmp_path, monkeypatch):
    env = tmp_path / "bad2.env"
    env.write_text("LISTEN_TIMEOUT=0\n")
    monkeypatch.setenv("JARVIS_ENV_FILE", str(env))
    reset_settings_cache()
    with pytest.raises(Exception):
        get_settings()


def test_logging_creates_file(tmp_path):
    log_file = setup_logging(tmp_path, level="INFO")
    log_file.info("hello world")
    log_file.info("api_key=sk-should-be-redacted")
    files = list(tmp_path.glob("*.log"))
    assert files, "log file was not created"
    content = files[0].read_text()
    assert "hello world" in content
    assert "<redacted>" in content
    # The token after the '=' sign must be replaced; the key itself
    # remains so operators can see *which* field triggered redaction.
    assert "api_key=<redacted>" in content
    assert "sk-should-be-redacted" not in content
