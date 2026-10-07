"""Groq chat completions provider with bounded retries and turn cancellation."""
from __future__ import annotations

import logging
import threading

import httpx

from app.ai.base import AIProvider, AIProviderError, ChatMessage

log = logging.getLogger("jarvis.ai.groq")
_CHAT_COMPLETIONS_URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqProvider(AIProvider):
    name = "groq"

    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile",
                 request_timeout: float = 15.0, max_attempts: int = 2,
                 max_tokens: int = 350) -> None:
        self._model = model
        self.max_attempts = max_attempts
        self.max_tokens = max_tokens
        self._cancelled = threading.Event()
        self.turn_cancelled = threading.Event()
        self._client = httpx.Client(
            timeout=request_timeout,
            headers={"Authorization": f"Bearer {api_key}"},
        )
        log.info("GroqProvider initialised (model=%s, max_tokens=%s)", self._model, self.max_tokens)

    def chat(self, messages: list[ChatMessage]) -> str:
        max_tokens = getattr(self, "max_tokens", 350)
        payload = {
            "model": self._model,
            "messages": [{"role": message.role, "content": message.content}
                         for message in messages],
            "temperature": 0.7,
            "max_tokens": max_tokens,
        }
        if not any(message.role == "user" for message in messages):
            return ""
        for attempt in range(self.max_attempts):
            if self._cancelled.is_set() or self.turn_cancelled.is_set():
                raise AIProviderError("The request was cancelled.")
            try:
                response = self._client.post(_CHAT_COMPLETIONS_URL, json=payload)
                response.raise_for_status()
                choices = response.json().get("choices", [])
                text = choices[0]["message"]["content"].strip() if choices else ""
                if not text:
                    raise AIProviderError(
                        "I couldn't produce an answer. Please rephrase your question."
                    )
                return text
            except AIProviderError:
                raise
            except httpx.HTTPStatusError as exc:
                code = exc.response.status_code
                transient = code in (408, 429, 500, 502, 503, 504)
                log.warning("Groq request failed: status=%s attempt=%s",
                            code, attempt + 1)
                if transient and attempt + 1 < self.max_attempts:
                    self.turn_cancelled.wait(0.5 * (2 ** attempt))
                    continue
                if code in (401, 403):
                    message = "My Groq access was denied. Please check the API key and its permissions."
                elif code == 404:
                    message = "My configured Groq model is unavailable. Please check the model setting."
                elif code == 429:
                    message = "Groq's usage limit was reached. Please try again later or check your quota."
                else:
                    message = "I'm having trouble reaching Groq. Please check your connection and try again."
                raise AIProviderError(message) from exc
            except httpx.TransportError as exc:
                log.warning("Groq connection failed: type=%s attempt=%s",
                            type(exc).__name__, attempt + 1)
                if attempt + 1 < self.max_attempts:
                    self.turn_cancelled.wait(0.5 * (2 ** attempt))
                    continue
                raise AIProviderError(
                    "I'm having trouble reaching Groq. Please check your connection and try again."
                ) from exc
            except (AttributeError, KeyError, IndexError, TypeError, ValueError) as exc:
                log.exception("Groq returned an invalid response")
                raise AIProviderError(
                    "I couldn't produce an answer. Please rephrase your question."
                ) from exc
            if self._cancelled.is_set() or self.turn_cancelled.is_set():
                raise AIProviderError("The request was cancelled.")
        raise AIProviderError(
            "I'm having trouble reaching Groq. Please check your connection and try again."
        )

    def cancel(self) -> None:
        self._cancelled.set()

    def shutdown(self) -> None:
        self.cancel()
        self._client.close()
