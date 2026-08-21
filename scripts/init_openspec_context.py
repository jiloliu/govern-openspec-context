#!/usr/bin/env python3
"""Initialize a new OpenSpec project with durable project context."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence


VERSION_RE = re.compile(r"(?<!\d)(\d+)\.(\d+)(?:\.(\d+))?")


class InitError(RuntimeError):
    """Expected, user-actionable initialization error."""


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preview or initialize durable OpenSpec project context."
    )
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--openspec-bin", default="openspec")
    parser.add_argument(
        "--tools",
        default="codebuddy",
        help="OpenSpec tool IDs passed to non-interactive init (default: codebuddy for WorkBuddy).",
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


def run_command(
    command: list[str], cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
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


def assert_new_adoption(project_root: Path) -> None:
    openspec_root = project_root / "openspec"
    if openspec_root.exists():
        raise InitError(
            f"{openspec_root} already exists. This initializer is only for new "
            "OpenSpec adoption and will not migrate or overwrite an existing setup."
        )
    agents = project_root / "AGENTS.md"
    marker = "<!-- govern-openspec-context:start -->"
    if agents.is_file() and marker in agents.read_text(encoding="utf-8"):
        raise InitError("The govern-openspec-context AGENTS.md block already exists.")


def find_legacy_instruction_files(project_root: Path, tools: str) -> list[Path]:
    tool_ids = {value.strip() for value in tools.split(",") if value.strip()}
    candidates = [
        project_root / ".codex" / "prompts",
        project_root / ".claude" / "commands" / "openspec",
        project_root / ".claude" / "commands" / "opsx",
        project_root / ".cursor" / "commands",
    ]
    if "codebuddy" in tool_ids or "all" in tool_ids:
        candidates.append(project_root / ".codebuddy" / "commands" / "openspec")

    matches: list[Path] = []
    for root in candidates:
        if root.is_file():
            matches.append(root)
        elif root.is_dir():
            matches.extend(
                path
                for path in root.rglob("*")
                if path.is_file()
                and ("openspec" in path.name or "opsx" in path.name or root.name in {"openspec", "opsx"})
            )

    if "codex" in tool_ids or "all" in tool_ids:
        codex_home = Path(
            os.environ.get("CODEX_HOME", Path.home() / ".codex")
        ).expanduser()
        prompt_root = codex_home / "prompts"
        if prompt_root.is_dir():
            matches.extend(prompt_root.glob("opsx-*.md"))
            matches.extend(prompt_root.glob("openspec-*.md"))
    return sorted({path for path in matches if path.is_file()})


def preflight_assets(skill_root: Path) -> None:
    required = (
        skill_root / "assets" / "templates" / "config.yaml.tmpl",
        skill_root / "assets" / "templates" / "project-context.md.tmpl",
        skill_root / "assets" / "templates" / "agents-section.md.tmpl",
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise InitError("Skill assets are incomplete: " + ", ".join(missing))


def planned_paths(project_root: Path, tools: str) -> tuple[Path, ...]:
    tool_ids = {value.strip() for value in tools.split(",") if value.strip()}
    paths = [
        project_root / "openspec" / "config.yaml",
        project_root / "openspec" / "project-context.md",
    ]
    if "codebuddy" in tool_ids or "all" in tool_ids:
        paths.extend(
            (
                project_root / ".codebuddy" / "skills" / "openspec-*",
                project_root / ".codebuddy" / "commands" / "opsx" / "*",
            )
        )
    if {"codex", "agents", "all"} & tool_ids:
        paths.append(project_root / ".agents" / "skills" / "openspec-*")
    return tuple(paths)


def print_agents_block(skill_root: Path) -> None:
    template = skill_root / "assets" / "templates" / "agents-section.md.tmpl"
    print("\nAGENTS.md block to merge with an available file-editing tool:\n")
    print(template.read_text(encoding="utf-8").rstrip())


def apply_initialization(
    project_root: Path, skill_root: Path, executable: str, tools: str
) -> None:
    legacy = find_legacy_instruction_files(project_root, tools)
    if legacy:
        listing = "\n".join(f"- {path}" for path in legacy)
        raise InitError(
            "OpenSpec init may remove legacy instruction files. Review or move these "
            f"before applying:\n{listing}"
        )

    result = run_command(
        [
            executable,
            "init",
            str(project_root),
            "--tools",
            tools,
            "--profile",
            "core",
            "--no-animation",
        ],
        cwd=project_root,
    )
    if result.returncode != 0:
        details = (result.stderr or result.stdout).strip()
        raise InitError(f"OpenSpec initialization failed: {details or 'unknown error'}")

    openspec_root = project_root / "openspec"
    config_target = openspec_root / "config.yaml"
    if not openspec_root.is_dir() or not config_target.is_file():
        raise InitError(
            "OpenSpec reported success but did not create openspec/config.yaml."
        )

    context_target = openspec_root / "project-context.md"
    if context_target.exists():
        raise InitError(
            "OpenSpec initialization created openspec/project-context.md; refusing "
            "to overwrite it."
        )

    config_template = skill_root / "assets" / "templates" / "config.yaml.tmpl"
    context_template = skill_root / "assets" / "templates" / "project-context.md.tmpl"
    config_target.write_text(config_template.read_text(encoding="utf-8"), encoding="utf-8")
    context_target.write_text(
        context_template.read_text(encoding="utf-8"), encoding="utf-8"
    )

    custom_schema_root = openspec_root / "schemas"
    if custom_schema_root.exists():
        raise InitError(
            "OpenSpec initialization unexpectedly created project-local schemas; "
            "review the partial initialization before continuing."
        )

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
        version = detect_version(executable)

        print(f"Project root: {project_root}")
        print(f"OpenSpec: {version} ({executable})")
        print("Mode: " + ("apply" if args.apply else "preview"))
        print(f"OpenSpec tools: {args.tools}")
        print("Planned paths:")
        for path in planned_paths(project_root, args.tools):
            print(f"- {path}")

        if args.apply:
            apply_initialization(project_root, skill_root, executable, args.tools)
            print(
                "\nInitialization completed. Fill project context, merge AGENTS.md, "
                "then validate OpenSpec before starting governed work."
            )
        else:
            print("\nNo files were changed. Re-run with --apply after reviewing the plan.")
        print_agents_block(skill_root)
        return 0
    except (InitError, OSError, UnicodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
