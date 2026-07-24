from fastapi.testclient import TestClient

from backend.config.settings import Settings
from backend.main import app


client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"


def test_version_endpoint() -> None:
    response = client.get("/api/version")
    assert response.status_code == 200
    payload = response.json()
    assert payload["app_name"] == "Altron"


def test_root_endpoint() -> None:
    response = client.get("/")
    assert response.status_code == 200
    payload = response.json()
    assert "API is running" in payload["message"]


def test_settings_validation() -> None:
    settings = Settings(app_env="testing", groq_api_key="test-key")
    assert settings.app_env == "testing"
    assert settings.groq_api_key == "test-key"
