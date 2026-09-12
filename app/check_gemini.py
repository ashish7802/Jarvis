"""Verify Gemini credentials with one short request; never print the key."""
from app.config import get_settings


def main():
    from google import genai
    settings = get_settings()
    if not settings.gemini_api_key:
        print("Set GEMINI_API_KEY in .env first.")
        return 1
    print("Checking Gemini authentication...", flush=True)
    try:
        with genai.Client(
            api_key=settings.gemini_api_key, http_options={"timeout": 30000}
        ) as client:
            response = client.models.generate_content(
                model=settings.ai_model or "gemini-3.6-flash",
                contents="Reply with exactly: Jarvis is ready.",
            )
            if not response.text:
                raise RuntimeError("Gemini returned an empty response")
            print("Gemini response:", response.text.strip())
        return 0
    except Exception as exc:
        message = str(exc).replace(settings.gemini_api_key, "[redacted]")
        print("Gemini check failed:", message[:1200])
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
