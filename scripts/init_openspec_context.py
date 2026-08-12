#!/usr/bin/env python3
"""Safely initialize a new OpenSpec project with durable context governance."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence


SCHEMAS = ("governed-standard", "governed-rapid")
VERSION_RE = re.compile(r"(?<!\d)(\d+)\.(\d+)(?:\.(\d+))?")


class InitError(RuntimeError):
    """Expected, user-actionable initialization error."""


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preview or initialize govern-openspec-context in a new project."
    )
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--openspec-bin", default="openspec")
    parser.add_argument(
        "--tools",
        default="codex",
        help="OpenSpec tool IDs passed to non-interactive init (default: codex).",
    )
    parser.add_argument(
        "--apply", action="store_true", help="Create files; preview is the default."
    )
    return parser.parse_args(argv)


def command_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "DO_NOT_TRACK": "1",
            "NO_COLOR": "1",
            "OPENSPEC_NO_ANIMATION": "1",
            "OPENSPEC_NO_UPDATE_CHECK": "1",
            "OPENSPEC_TELEMETRY": "0",
        }
    )
    return env


def resolve_executable(value: str) -> str:
    candidate = Path(value).expanduser()
    if candidate.parent != Path(".") or candidate.is_absolute():
        if not candidate.is_file():
            raise InitError(f"OpenSpec executable not found: {candidate}")
        return str(candidate.resolve())
    resolved = shutil.which(value)
    if not resolved:
        raise InitError(
            "OpenSpec CLI was not found on PATH. Install OpenSpec 1.x before "
            "initializing this workflow."
        )
    return resolved


def run_command(command: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=command_env(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def detect_version(executable: str) -> str:
    result = run_command([executable, "--version"])
    output = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
    if result.returncode != 0:
        raise InitError(f"Unable to run OpenSpec CLI: {output or 'unknown error'}")
    match = VERSION_RE.search(output)
    if not match:
        raise InitError(f"Unable to parse OpenSpec version from: {output!r}")
    if int(match.group(1)) != 1:
        raise InitError(
            f"OpenSpec major version 1 is required; found {match.group(0)}."
        )
    return match.group(0)


def ensure_node_version() -> str:
    node = shutil.which("node")
    if not node:
        raise InitError("Node.js is required by OpenSpec but was not found on PATH.")
    result = run_command([node, "--version"])
    match = VERSION_RE.search(result.stdout.strip())
    if result.returncode != 0 or not match:
        raise InitError("Unable to determine the installed Node.js version.")
    major = int(match.group(1))
    minor = int(match.group(2))
    if (major, minor) < (20, 19):
        raise InitError(
            f"OpenSpec requires Node.js 20.19 or newer; found {match.group(0)}."
        )
    return match.group(0)


def find_legacy_codex_prompts() -> list[Path]:
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
    prompts = codex_home / "prompts"
    if not prompts.is_dir():
        return []
    matches = list(prompts.glob("opsx-*.md"))
    matches.extend(prompts.glob("openspec-*.md"))
    return sorted(path for path in matches if path.is_file())


def find_project_legacy_files(project_root: Path) -> list[Path]:
    candidates = (
        project_root / ".codex" / "prompts",
        project_root / ".claude" / "commands" / "openspec",
        project_root / ".claude" / "commands" / "opsx",
        project_root / ".cursor" / "commands",
    )
    matches: list[Path] = []
    for root in candidates:
        if not root.exists():
            continue
        if root.is_file():
            matches.append(root)
            continue
        for path in root.rglob("*"):
            if path.is_file() and ("openspec" in path.name or "opsx" in path.name or root.name in {"openspec", "opsx"}):
                matches.append(path)
    return sorted(set(matches))


def assert_new_adoption(project_root: Path) -> None:
    openspec_root = project_root / "openspec"
    if openspec_root.exists():
        raise InitError(
            f"{openspec_root} already exists. This initializer is only for new "
            "OpenSpec adoption and will not migrate or overwrite an existing setup."
        )
    managed_start = "<!-- govern-openspec-context:start -->"
    agents = project_root / "AGENTS.md"
    if agents.is_file() and managed_start in agents.read_text(encoding="utf-8"):
        raise InitError("The govern-openspec-context AGENTS.md block already exists.")


def planned_paths(project_root: Path) -> list[Path]:
    paths = [
        project_root / "openspec" / "config.yaml",
        project_root / "openspec" / "project-context.md",
    ]
    for schema in SCHEMAS:
        paths.append(project_root / "openspec" / "schemas" / schema)
    paths.append(project_root / ".agents" / "skills" / "openspec-*")
    return paths


def print_agents_block(skill_root: Path) -> None:
    template = skill_root / "assets" / "templates" / "agents-section.md.tmpl"
    print("\nAGENTS.md block to merge with apply_patch:\n")
    print(template.read_text(encoding="utf-8").rstrip())


def preflight_assets(skill_root: Path) -> None:
    required = [
        skill_root / "assets" / "templates" / "config.yaml.tmpl",
        skill_root / "assets" / "templates" / "project-context.md.tmpl",
        skill_root / "assets" / "templates" / "agents-section.md.tmpl",
    ]
    for schema in SCHEMAS:
        required.append(skill_root / "assets" / "schemas" / schema / "schema.yaml")
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise InitError("Skill assets are incomplete: " + ", ".join(missing))


def apply_initialization(
    project_root: Path, skill_root: Path, executable: str, version: str, tools: str
) -> None:
    legacy = find_project_legacy_files(project_root)
    tool_ids = {value.strip() for value in tools.split(",")}
    if "codex" in tool_ids or "all" in tool_ids:
        legacy.extend(find_legacy_codex_prompts())
        legacy = sorted(set(legacy))
    if legacy:
        listing = "\n".join(f"- {path}" for path in legacy)
        raise InitError(
            "OpenSpec init may remove legacy Codex prompts. Review or move these "
            f"before applying:\n{listing}"
        )

    command = [
        executable,
        "init",
        str(project_root),
        "--tools",
        tools,
        "--profile",
        "core",
        "--no-animation",
    ]
    result = run_command(command, cwd=project_root)
    if result.returncode != 0:
        details = (result.stderr or result.stdout).strip()
        raise InitError(f"OpenSpec initialization failed: {details or 'unknown error'}")

    openspec_root = project_root / "openspec"
    if not openspec_root.is_dir():
        raise InitError("OpenSpec reported success but did not create openspec/.")

    unexpected = [
        path
        for path in (
            openspec_root / "project-context.md",
            *(openspec_root / "schemas" / schema for schema in SCHEMAS),
        )
        if path.exists()
    ]
    if unexpected:
        raise InitError(
            "OpenSpec initialization created paths reserved by this workflow; refusing "
            "to overwrite them: " + ", ".join(str(path) for path in unexpected)
        )

    if "codex" in tool_ids or "all" in tool_ids:
        required_names = (
            "openspec-propose",
            "openspec-apply-change",
            "openspec-archive-change",
        )
        skill_roots = (
            project_root / ".agents" / "skills",
            project_root / ".codex" / "skills",
        )
        resolved = {
            name: next(
                (
                    root / name / "SKILL.md"
                    for root in skill_roots
                    if (root / name / "SKILL.md").is_file()
                ),
                None,
            )
            for name in required_names
        }
        missing = [name for name, path in resolved.items() if path is None]
        if missing:
            raise InitError(
                "OpenSpec init did not generate required Codex core skills: "
                + ", ".join(missing)
            )

    schema_target_root = openspec_root / "schemas"
    schema_target_root.mkdir(parents=True, exist_ok=True)
    for schema in SCHEMAS:
        source = skill_root / "assets" / "schemas" / schema
        target = schema_target_root / schema
        if target.exists():
            raise InitError(f"Refusing to overwrite schema created during init: {target}")
        shutil.copytree(source, target)

    config_target = openspec_root / "config.yaml"
    config_template = skill_root / "assets" / "templates" / "config.yaml.tmpl"
    config_target.write_text(config_template.read_text(encoding="utf-8"), encoding="utf-8")

    context_target = openspec_root / "project-context.md"
    context_template = skill_root / "assets" / "templates" / "project-context.md.tmpl"
    if context_target.exists():
        raise InitError(f"Refusing to overwrite file created during init: {context_target}")
    context_target.write_text(context_template.read_text(encoding="utf-8"), encoding="utf-8")

    for schema in SCHEMAS:
        validation = run_command(
            [executable, "schema", "validate", schema, "--json"], cwd=project_root
        )
        try:
            validation_payload = json.loads(validation.stdout)
        except json.JSONDecodeError as error:
            raise InitError(
                f"Installed schema {schema} validation returned invalid JSON."
            ) from error
        if validation.returncode != 0 or validation_payload.get("valid") is not True:
            details = (validation.stderr or validation.stdout).strip()
            raise InitError(f"Installed schema {schema} failed validation: {details}")

    if result.stdout.strip():
        print("OpenSpec init output:\n" + result.stdout.strip())


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        project_root = args.project_root.expanduser().resolve()
        if not project_root.is_dir():
            raise InitError(f"Project root is not a directory: {project_root}")
        skill_root = Path(__file__).resolve().parents[1]
        preflight_assets(skill_root)
        assert_new_adoption(project_root)
        executable = resolve_executable(args.openspec_bin)
        openspec_version = detect_version(executable)
        node_version = ensure_node_version()

        print(f"Project root: {project_root}")
        print(f"OpenSpec: {openspec_version} ({executable})")
        print(f"Node.js: {node_version}")
        print("Mode: " + ("apply" if args.apply else "preview"))
        print("Planned paths:")
        for path in planned_paths(project_root):
            print(f"- {path}")

        if args.apply:
            apply_initialization(
                project_root, skill_root, executable, openspec_version, args.tools
            )
            print("\nInitialization completed. Fill project context, merge AGENTS.md, then run the checker.")
        else:
            print("\nNo files were changed. Re-run with --apply after reviewing the plan.")
        print_agents_block(skill_root)
        return 0
    except InitError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
