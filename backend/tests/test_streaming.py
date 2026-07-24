from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_streaming_response_is_text_event_stream() -> None:
    response = client.post("/api/chat/stream", json={"message": "Hello"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
