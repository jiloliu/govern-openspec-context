from __future__ import annotations

import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def load_frontmatter() -> dict[str, object]:
    content = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    if not content.startswith("---\n"):
        raise SystemExit("SKILL.md must start with YAML frontmatter")
    try:
        frontmatter = content.split("---", 2)[1]
    except IndexError as error:
        raise SystemExit("SKILL.md frontmatter is not closed") from error
    metadata = yaml.safe_load(frontmatter)
    if not isinstance(metadata, dict):
        raise SystemExit("SKILL.md frontmatter must be a mapping")
    return metadata


def main() -> int:
    metadata = load_frontmatter()
    if set(metadata) != {"name", "description", "agent_created"}:
        raise SystemExit(
            "SKILL.md frontmatter must contain name, description, and agent_created"
        )
    if metadata["name"] != "govern-openspec-context":
        raise SystemExit("unexpected skill name")
    if metadata["agent_created"] is not True:
        raise SystemExit("WorkBuddy skills must set agent_created: true")
    description = str(metadata["description"])
    if "WorkBuddy" not in description or "Codex needs" in description:
        raise SystemExit("skill description must be WorkBuddy-oriented")

    workbuddy = json.loads((ROOT / "workbuddy.json").read_text(encoding="utf-8"))
    required = {
        "display_name",
        "display_name_en",
        "description_zh",
        "description_en",
    }
    if set(workbuddy) != required or not all(workbuddy.values()):
        raise SystemExit("workbuddy.json metadata is incomplete or unexpected")
    if (ROOT / "agents" / "openai.yaml").exists():
        raise SystemExit("Codex-only agents/openai.yaml must not be distributed")

    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    agents_template = (
        ROOT / "assets" / "templates" / "agents-section.md.tmpl"
    ).read_text(encoding="utf-8")
    if ".codebuddy/skills/openspec-*" not in skill:
        raise SystemExit("SKILL.md must prefer generated CodeBuddy skills")
    if "/govern-openspec-context" not in agents_template:
        raise SystemExit("AGENTS.md template must use WorkBuddy invocation syntax")
    if "$govern-openspec-context" in agents_template:
        raise SystemExit("AGENTS.md template still contains Codex invocation syntax")

    print("WorkBuddy skill metadata is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
