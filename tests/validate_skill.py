from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = (
    Path.home()
    / ".codex"
    / "skills"
    / ".system"
    / "skill-creator"
    / "scripts"
    / "quick_validate.py"
)


def main() -> int:
    if VALIDATOR.is_file():
        result = subprocess.run(
            [sys.executable, str(VALIDATOR), str(ROOT)], check=False
        )
        if result.returncode != 0:
            return result.returncode

    frontmatter = (ROOT / "SKILL.md").read_text(encoding="utf-8").split("---", 2)[1]
    metadata = yaml.safe_load(frontmatter)
    if metadata != {
        "name": "govern-openspec-context",
        "description": metadata.get("description"),
    }:
        raise SystemExit("SKILL.md frontmatter must contain only name and description")
    if not metadata["description"]:
        raise SystemExit("SKILL.md description is empty")

    interface = yaml.safe_load((ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8"))
    values = interface.get("interface", {})
    required = {"display_name", "short_description", "default_prompt"}
    if set(values) != required:
        raise SystemExit("agents/openai.yaml interface keys are incomplete or unexpected")
    if "$govern-openspec-context" not in values["default_prompt"]:
        raise SystemExit("default_prompt must mention $govern-openspec-context")
    if not 25 <= len(values["short_description"]) <= 64:
        raise SystemExit("short_description must contain 25-64 characters")
    print("Skill metadata is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
