import json
from pathlib import Path

import pytest

from src.formats.latex.validation_utils import (
    find_reasoning_artifacts,
    sanitize_translated_text,
)
from src.agents.tool_agents.validator_agent import ValidatorAgent


@pytest.fixture
def tmp_validator_workspace(tmp_path: Path) -> Path:
    """Create a temporary validator workspace with minimal JSON maps."""

    sections = [
        {
            "section": 1,
            "content": "\\section{Background}",
            "trans_content": (
                "Reasoning: ensure consistency\n"
                "<think>internal thoughts</think>\n"
                " Pre-text that should go away\\section{Hintergrund}\n"
                "The assistant should correct the translation by ensuring that the LaTeX command is properly used."
            ),
        }
    ]
    captions = []
    envs = []

    (tmp_path / "sections_map.json").write_text(
        json.dumps(sections, ensure_ascii=False, indent=4),
        encoding="utf-8",
    )
    (tmp_path / "captions_map.json").write_text(
        json.dumps(captions, ensure_ascii=False, indent=4),
        encoding="utf-8",
    )
    (tmp_path / "envs_map.json").write_text(
        json.dumps(envs, ensure_ascii=False, indent=4),
        encoding="utf-8",
    )

    return tmp_path


def test_sanitize_translated_text_strips_reasoning():
    raw = (
        "<think>analysis</think>\n"
        "Reasoning: translate carefully\n"
        "  % Note: remove this\n"
        "Lead-in text\\begin{proof}Content\\end{proof}"
    )
    sanitized = sanitize_translated_text(raw)

    assert sanitized.startswith("\\begin{proof}")
    assert "Reasoning:" not in sanitized
    assert "<think>" not in sanitized
    assert "%" not in sanitized


def test_sanitize_translated_text_drops_instruction_sentences():
    raw = (
        "\\section{Intro} Text here. The assistant should correct the translation by ensuring that the LaTeX command is properly used."
    )
    sanitized = sanitize_translated_text(raw)

    assert sanitized.strip() == "\\section{Intro} Text here."
    assert "assistant" not in sanitized.lower()


def test_sanitize_translated_text_drops_instruction_lines_anywhere():
    raw = (
        "\\emph{Example} content.\n"
        "Ensure that the LaTeX command is properly used.\n"
        "Another line."
    )
    sanitized = sanitize_translated_text(raw)

    assert "ensure that the latex command" not in sanitized.lower()
    assert sanitized.strip().startswith("\\emph{Example}")
    assert sanitized.strip().endswith("Another line.")


def test_validator_auto_sanitizes_reasoning(tmp_validator_workspace: Path):
    validator = ValidatorAgent(
        config={},
        project_dir=str(tmp_validator_workspace),
        output_dir=str(tmp_validator_workspace),
    )

    errors = validator.execute()

    assert errors == []

    updated_sections = json.loads(
        (tmp_validator_workspace / "sections_map.json").read_text(encoding="utf-8")
    )
    sanitized_text = updated_sections[0]["trans_content"]

    assert sanitized_text == "\\section{Hintergrund}"
    assert not find_reasoning_artifacts(sanitized_text)
    assert not (tmp_validator_workspace / "errors_report.json").exists()
