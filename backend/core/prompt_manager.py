from __future__ import annotations

from pathlib import Path


class PromptManager:
    """Load reusable prompt templates from files on disk."""

    def __init__(self, prompts_dir: str | Path | None = None) -> None:
        base_dir = Path(prompts_dir) if prompts_dir is not None else Path(__file__).resolve().parents[1] / "prompts"
        self.prompts_dir = base_dir

    def get_prompt(self, kind: str, **kwargs: str) -> str:
        file_path = self._resolve_path(kind)
        if file_path.exists():
            template = file_path.read_text(encoding="utf-8").strip()
        else:
            template = self._default_prompt(kind)

        if not kwargs:
            return template
        try:
            return template.format(**kwargs)
        except KeyError:
            return template

    def _resolve_path(self, kind: str) -> Path:
        candidates = [
            self.prompts_dir / f"{kind}.txt",
            self.prompts_dir / f"{kind}.md",
            self.prompts_dir / f"{kind}.prompt",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return self.prompts_dir / f"{kind}.txt"

    def _default_prompt(self, kind: str) -> str:
        defaults = {
            "system": "You are a helpful AI assistant.",
            "assistant": "Respond clearly and concisely.",
            "developer": "Focus on correctness and useful guidance.",
            "skill": "Follow the requested skill instructions.",
        }
        return defaults.get(kind, "You are a helpful AI assistant.")
