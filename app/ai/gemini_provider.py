from __future__ import annotations

import logging
import threading
import httpx

from app.ai.base import AIProvider, AIProviderError, ChatMessage

log = logging.getLogger("jarvis.ai.gemini")


def _to_gemini(messages: list[ChatMessage]) -> tuple[str, list[dict]]:
    system_parts: list[str] = []
    history: list[dict] = []
    for m in messages:
        if m.role == "system":
            system_parts.append(m.content)
        elif m.role == "user":
            history.append({"role": "user", "parts": [{"text": m.content}]})
        elif m.role == "assistant":
            history.append({"role": "model", "parts": [{"text": m.content}]})
    return "\n\n".join(system_parts), history


class GeminiProvider(AIProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str = "gemini-3.6-flash", request_timeout: float = 15.0, max_attempts: int = 2) -> None:
        try:
            from google import genai
        except ImportError as e:
            raise RuntimeError(
                "google-genai package not installed. "
                "`pip install google-genai` to use GeminiProvider."
            ) from e
        self._client = genai.Client(api_key=api_key, http_options={
            "timeout": int(request_timeout * 1000), "retry_options": {"attempts": 1}
        })
        self.max_attempts = max_attempts
        self._cancelled = threading.Event()
        self.turn_cancelled = threading.Event()
        self._model_name = model
        log.info("GeminiProvider initialised (model=%s)", self._model_name)

    def chat(self, messages: list[ChatMessage]) -> str:
        system_prompt, history = _to_gemini(messages)
        if not history:
            return ""
        for attempt in range(self.max_attempts):
            if self._cancelled.is_set() or self.turn_cancelled.is_set():
                raise AIProviderError("The request was cancelled.")
            try:
                resp = self._client.models.generate_content(
                    model=self._model_name, contents=history,
                    config={"system_instruction": system_prompt or None},
                )
                text = (resp.text or "").strip()
                if not text:
                    raise AIProviderError("I couldn't produce an answer. Please rephrase your question.")
                return text
            except AIProviderError:
                raise
            except Exception as exc:
                code = getattr(exc, "code", None)
                transient = code in (408, 429, 500, 502, 503, 504) or isinstance(exc, httpx.TransportError)
                log.warning("Gemini request failed: type=%s code=%s attempt=%s", type(exc).__name__, code, attempt + 1)
                if transient and attempt + 1 < self.max_attempts:
                    self.turn_cancelled.wait(0.5 * (2 ** attempt))
                    continue
                if code in (401, 403):
                    message = "My Gemini access was denied. Please check the API key and its permissions."
                elif code == 404:
                    message = "My configured Gemini model is unavailable. Please check the model setting."
                elif code == 429:
                    message = "Gemini's usage limit was reached. Please try again later or check your quota."
                else:
                    message = "I'm having trouble reaching Gemini. Please check your connection and try again."
                raise AIProviderError(message) from exc

    def cancel(self):
        self._cancelled.set()

    def shutdown(self):
        self.cancel()
        self._client.close()
