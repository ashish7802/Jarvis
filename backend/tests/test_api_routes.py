from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_chat_endpoint_returns_structured_response() -> None:
    response = client.post("/api/chat", json={"message": "Hello", "stream": False})

    assert response.status_code == 200
    payload = response.json()
    assert payload["content"]
    assert payload["intent"]["intent"] == "conversation"


def test_stream_endpoint_emits_chunks() -> None:
    response = client.post("/api/chat/stream", json={"message": "Hello"})

    assert response.status_code == 200
    assert "data:" in response.text
