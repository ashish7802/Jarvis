from __future__ import annotations

import logging

from app.ai.base import AIProvider, ChatMessage

log = logging.getLogger("jarvis.ai.gemini")


def _to_gemini(messages: list[ChatMessage]) -> tuple[str, list[dict[str, str]]]:
    system_parts: list[str] = []
    history: list[dict[str, str]] = []
    for m in messages:
        if m.role == "system":
            system_parts.append(m.content)
        elif m.role == "user":
            history.append({"role": "user", "parts": [m.content]})
        elif m.role == "assistant":
            history.append({"role": "model", "parts": [m.content]})
    return "\n\n".join(system_parts), history


class GeminiProvider(AIProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str = "gemini-1.5-flash") -> None:
        try:
            import google.generativeai as genai  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "google-generativeai package not installed. "
                "`pip install google-generativeai` to use GeminiProvider."
            ) from e
        genai.configure(api_key=api_key)
        self._genai = genai
        self._model_name = model
        log.info("GeminiProvider initialised (model=%s)", self._model_name)

    def chat(self, messages: list[ChatMessage]) -> str:
        try:
            system_prompt, history = _to_gemini(messages)
            model = self._genai.GenerativeModel(
                model_name=self._model_name,
                system_instruction=system_prompt or None,
            )
            # Use the last user message as the new prompt; replay history.
            if not history:
                return ""
            last_user = ""
            for h in reversed(history):
                if h["role"] == "user":
                    last_user = h["parts"][0]
                    break
            chat = model.start_chat(history=[h for h in history if h is not history[-1]])
            resp = chat.send_message(last_user)
            return (resp.text or "").strip()
        except Exception as exc:
            log.exception("Gemini chat failed: %s", exc)
            return (
                "I'm sorry, Sir. I'm having trouble reaching my language model. "
                "Please try again in a moment."
            )
