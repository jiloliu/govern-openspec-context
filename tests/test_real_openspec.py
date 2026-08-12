from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
INIT = SKILL_ROOT / "scripts" / "init_openspec_context.py"
OPENSPEC = os.environ.get("OPENSPEC_BIN") or shutil.which("openspec")
EXPECTED_VERSION = os.environ.get("OPENSPEC_EXPECT_VERSION")

FILLED_CONTEXT = """# Project Context

## Product and scope
- Purpose: Exercise native OpenSpec integration.
- In scope: Temporary integration fixtures.
- Out of scope: Production systems.

## Architecture map
- Entry points: src/.
- Major modules and responsibilities: temporary fixture.
- Dependency direction and data flow: local files only.

## Contracts and invariants
- Public interfaces: fixture text output.
- Data or compatibility invariants: UTF-8 files.
- Security and operational constraints: no external services.

## Verification commands
- Build: not applicable.
- Test: python3 -m unittest.
- Lint or static analysis: not applicable.
- Change-specific verification: each active change tasks.md.

## Authoritative sources
- Accepted behavior: openspec/specs/.
- Active changes: openspec/changes/.
- Architecture decisions: docs/adr/.
- Detailed architecture and operations documentation: none.

## Delivery policy
- Branch/worktree convention: one branch per change.
- Archive timing: after local verification.
- Deployment is separate from development completion: yes.

## Durable cautions
- Keep fixtures local.
"""


def run(
    cwd: Path, command: list[str], *, check: bool = True
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(
        {
            "DO_NOT_TRACK": "1",
            "NO_COLOR": "1",
            "OPENSPEC_NO_ANIMATION": "1",
            "OPENSPEC_NO_UPDATE_CHECK": "1",
            "OPENSPEC_TELEMETRY": "0",
            "PYTHONPYCACHEPREFIX": str(cwd.parent / "pycache"),
        }
    )
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"command failed ({result.returncode}): {' '.join(command)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def git(root: Path, *arguments: str) -> str:
    return run(root, ["git", *arguments]).stdout.strip()


@unittest.skipUnless(OPENSPEC, "OpenSpec CLI is not installed")
class NativeOpenSpecIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "project"
        self.root.mkdir()
        git(self.root, "init", "-b", "main")
        git(self.root, "config", "user.email", "integration@example.invalid")
        git(self.root, "config", "user.name", "OpenSpec Integration")

        version = run(self.root, [str(OPENSPEC), "--version"]).stdout.strip().removeprefix("v")
        self.assertEqual(version.split(".")[0], "1")
        if EXPECTED_VERSION:
            self.assertEqual(version, EXPECTED_VERSION)

        initialized = run(
            self.root,
            [
                sys.executable,
                str(INIT),
                "--project-root",
                str(self.root),
                "--openspec-bin",
                str(OPENSPEC),
                "--apply",
            ],
        )
        self.assertIn("Initialization completed", initialized.stdout)
        (self.root / "openspec" / "project-context.md").write_text(
            FILLED_CONTEXT, encoding="utf-8"
        )
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", "initialize durable OpenSpec context")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_native_spec_driven_change_validates_and_archives(self) -> None:
        self.assertFalse((self.root / "openspec" / "schemas").exists())
        schemas = json.loads(run(self.root, [str(OPENSPEC), "schemas", "--json"]).stdout)
        self.assertEqual([entry["name"] for entry in schemas], ["spec-driven"])

        name = "add-observable-output"
        created = run(
            self.root,
            [str(OPENSPEC), "new", "change", name, "--schema", "spec-driven", "--json"],
        )
        payload = json.loads(created.stdout)
        self.assertEqual(payload["change"]["schema"], "spec-driven")

        change = self.root / "openspec" / "changes" / name
        (change / "specs" / "output").mkdir(parents=True)
        (change / "proposal.md").write_text(
            "## Why\nExpose a stable output marker.\n\n## What Changes\nAdd output.\n\n"
            "## Capabilities\n### New Capabilities\n- `output`: writes a marker.\n\n"
            "## Impact\nLocal fixture only.\n",
            encoding="utf-8",
        )
        (change / "specs" / "output" / "spec.md").write_text(
            "## ADDED Requirements\n\n### Requirement: Observable output\n"
            "The system SHALL write an output marker.\n\n#### Scenario: Marker written\n"
            "- **WHEN** a run completes\n- **THEN** an output marker is written\n",
            encoding="utf-8",
        )
        (change / "design.md").write_text(
            "## Context\nLocal fixture.\n\n## Goals / Non-Goals\nAdd one marker.\n\n"
            "## Decisions\nWrite a UTF-8 file.\n\n## Risks / Trade-offs\nNone.\n\n"
            "## Migration Plan\nNo migration.\n\n## Open Questions\nNone.\n",
            encoding="utf-8",
        )
        (change / "tasks.md").write_text(
            "## 1. Implementation\n- [x] 1.1 Write the marker.\n\n"
            "## 2. Verification\n- [x] 2.1 Validate the scenario.\n",
            encoding="utf-8",
        )
        (self.root / "src").mkdir()
        (self.root / "src" / "output.txt").write_text("marker\n", encoding="utf-8")

        self.assertFalse(any(change.rglob("handoff.md")))
        validation = run(
            self.root,
            [str(OPENSPEC), "validate", name, "--strict", "--json"],
        )
        validation_payload = json.loads(validation.stdout)
        self.assertTrue(validation_payload["items"][0]["valid"])

        archived = run(
            self.root, [str(OPENSPEC), "archive", name, "--yes", "--json"]
        )
        archive_payload = json.loads(archived.stdout)
        archive_dir = Path(archive_payload["archive"]["path"])
        self.assertTrue(archive_dir.is_dir())
        self.assertFalse(any(archive_dir.rglob("handoff.md")))
        main_spec = self.root / "openspec" / "specs" / "output" / "spec.md"
        self.assertIn("Observable output", main_spec.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
