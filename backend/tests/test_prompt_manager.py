from pathlib import Path

from backend.core.prompt_manager import PromptManager


def test_prompt_manager_loads_and_formats_templates(tmp_path: Path) -> None:
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    (prompts_dir / "system.txt").write_text("You are {name}.", encoding="utf-8")
    (prompts_dir / "developer.txt").write_text("Focus on {topic}.", encoding="utf-8")

    manager = PromptManager(prompts_dir)

    system_prompt = manager.get_prompt("system", name="Altron")
    developer_prompt = manager.get_prompt("developer", topic="clarity")

    assert "Altron" in system_prompt
    assert "clarity" in developer_prompt
