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
CHECK = SKILL_ROOT / "scripts" / "check_openspec_context.py"
OPENSPEC = os.environ.get("OPENSPEC_BIN") or shutil.which("openspec")
EXPECTED_VERSION = os.environ.get("OPENSPEC_EXPECT_VERSION")

FILLED_CONTEXT = """# Project Context

## Product and scope
- Purpose: Exercise real OpenSpec integration.
- In scope: Temporary integration fixtures.
- Out of scope: Production systems.

## Architecture map
- Entry points: src/.
- Major modules and ownership: temporary fixture.
- Data and control flow: local files only.

## Contracts and invariants
- Public interfaces: fixture text output.
- Data or compatibility invariants: UTF-8 files.
- Security and operational constraints: no external services.

## Verification commands
- Build: not applicable.
- Test: python3 -m unittest.
- Lint or static analysis: not applicable.
- Change-specific verification: each change tasks.md.

## Authoritative sources
- Accepted behavior: openspec/specs/.
- Active changes: openspec/changes/.
- Architecture or operations documentation: none.

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
class RealOpenSpecIntegrationTest(unittest.TestCase):
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
        git(self.root, "commit", "-m", "initialize governed OpenSpec")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def new_change(self, name: str, schema: str) -> Path:
        created = run(
            self.root,
            [str(OPENSPEC), "new", "change", name, "--schema", schema, "--json"],
        )
        payload = json.loads(created.stdout)
        self.assertEqual(payload["change"]["schema"], schema)
        return self.root / "openspec" / "changes" / name

    def commit_with_handoff(
        self, name: str, status: str, next_action: str, *, result: str = "pass"
    ) -> str:
        change = self.root / "openspec" / "changes" / name
        placeholder = git(self.root, "rev-parse", "HEAD")
        (change / "handoff.md").write_text(
            self.handoff(
                name,
                placeholder,
                status=status,
                next_action=next_action,
                result="not-run",
            ),
            encoding="utf-8",
        )
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", f"implement {name}")
        checkpoint = git(self.root, "rev-parse", "HEAD")
        (change / "handoff.md").write_text(
            self.handoff(
                name,
                checkpoint,
                status=status,
                next_action=next_action,
                result=result,
                uncommitted=f"openspec/changes/{name}/handoff.md",
            ),
            encoding="utf-8",
        )
        return checkpoint

    @staticmethod
    def handoff(
        name: str,
        commit: str,
        *,
        status: str,
        next_action: str,
        result: str,
        uncommitted: str | None = None,
    ) -> str:
        passed = result == "pass"
        return f"""# Change Handoff

## Snapshot

- Change: {name}
- Owner: integration-writer
- Branch: main
- Status: `{status}`
- Current task: `none`
- Last completed task: `3.3`
- Checkpoint commit: `{commit}`
- Checkpoint time: 2030-01-01T00:00:00+00:00
- Exact next action: {next_action}

## Latest Verification

- Result: `{result}`
- Command: `python3 -m unittest`
- Exit code: `{'0' if passed else '1' if result == 'fail' else 'none'}`
- Verified at: `{'2030-01-01T00:01:00+00:00' if result != 'not-run' else 'none'}`
- Verification commit: `{commit if passed else 'none'}`

## Uncommitted Paths

{'- `' + uncommitted + '`' if uncommitted else '- None.'}

## Blockers and Deviations

- None.
"""

    def check_change(self, name: str) -> dict[str, object]:
        result = run(
            self.root,
            [
                sys.executable,
                str(CHECK),
                "--project-root",
                str(self.root),
                "--openspec-bin",
                str(OPENSPEC),
                "--change",
                name,
                "--owner",
                "integration-writer",
                "--strict",
                "--json",
            ],
        )
        return json.loads(result.stdout)

    def test_rapid_without_specs_validates_and_archives_with_handoff(self) -> None:
        name = "rapid-cleanup"
        change = self.new_change(name, "governed-rapid")
        metadata = change / ".openspec.yaml"
        metadata.write_text(metadata.read_text(encoding="utf-8") + "skip_specs: true\n", encoding="utf-8")
        (change / "proposal.md").write_text(
            "## Why\nClean internal tooling.\n\n## What Changes\nRefactor fixtures.\n\n"
            "## Boundaries\n- In scope: fixtures.\n- Out of scope: behavior.\n\n"
            "## Risk Profile\n- Profile: `rapid`\n- Rationale: Internal only.\n"
            "- Spec handling: `.openspec.yaml` contains `skip_specs: true`.\n\n"
            "## Verification\nRun unit tests.\n",
            encoding="utf-8",
        )
        (change / "tasks.md").write_text(
            "## 1. Implementation\n- [x] 1.1 Refactor fixture.\n\n"
            "## 2. Verification\n- [x] 2.1 Run checks.\n- [x] 2.2 Inspect diff.\n"
            "- [x] 3.3 Update handoff.\n",
            encoding="utf-8",
        )
        (self.root / "src").mkdir()
        (self.root / "src" / "rapid.txt").write_text("rapid\n", encoding="utf-8")
        self.commit_with_handoff(name, "awaiting-archive", "Archive this change.")
        self.assertTrue(self.check_change(name)["ok"])

        archived = run(
            self.root, [str(OPENSPEC), "archive", name, "--yes", "--json"]
        )
        archive_payload = json.loads(archived.stdout)
        archive_dir = Path(archive_payload["archive"]["path"])
        self.assertTrue((archive_dir / "handoff.md").is_file())
        self.assertFalse(change.exists())

    def test_standard_archive_updates_main_specs_and_rejects_incomplete_state(self) -> None:
        name = "add-observable-output"
        change = self.new_change(name, "governed-standard")
        (change / "specs" / "output").mkdir(parents=True)
        (change / "proposal.md").write_text(
            "## Why\nExpose output.\n\n## What Changes\nAdd observable output.\n\n"
            "## Scope\n### In scope\nOutput.\n\n### Out of scope\nNetworking.\n\n"
            "## Risk Profile\n- Profile: `standard`\n- Rationale: User-visible behavior.\n\n"
            "## Impact\nOutput capability.\n",
            encoding="utf-8",
        )
        (change / "specs" / "output" / "spec.md").write_text(
            "## ADDED Requirements\n\n### Requirement: Observable output\n"
            "The system SHALL write an output marker.\n\n#### Scenario: Marker written\n"
            "- **GIVEN** a configured run\n- **WHEN** the run completes\n"
            "- **THEN** an output marker is written\n",
            encoding="utf-8",
        )
        (change / "design.md").write_text(
            "## Context\nLocal fixture.\n\n## Goals / Non-Goals\nAdd marker only.\n\n"
            "## Decisions\nWrite a UTF-8 file.\n\n## Contracts and Data Flow\nLocal write.\n\n"
            "## Compatibility, Migration, and Rollout\nNo migration.\n\n"
            "## Verification Strategy\nInspect file.\n\n## Open Questions\nNone.\n",
            encoding="utf-8",
        )
        (change / "tasks.md").write_text(
            "## 1. Preparation\n- [x] 1.1 Establish baseline.\n\n"
            "## 2. Implementation\n- [x] 2.1 Write marker.\n\n"
            "## 3. Verification\n- [x] 3.1 Verify scenario.\n- [x] 3.2 Inspect diff.\n"
            "- [x] 3.3 Update handoff.\n",
            encoding="utf-8",
        )
        (self.root / "src").mkdir()
        (self.root / "src" / "output.txt").write_text("marker\n", encoding="utf-8")
        self.commit_with_handoff(name, "awaiting-archive", "Archive this change.")
        self.assertTrue(self.check_change(name)["ok"])

        tasks = change / "tasks.md"
        original = tasks.read_text(encoding="utf-8")
        tasks.write_text(original.replace("[x] 3.3", "[ ] 3.3"), encoding="utf-8")
        rejected = run(
            self.root,
            [
                sys.executable,
                str(CHECK),
                "--project-root",
                str(self.root),
                "--openspec-bin",
                str(OPENSPEC),
                "--change",
                name,
                "--strict",
                "--json",
            ],
            check=False,
        )
        self.assertNotEqual(rejected.returncode, 0)
        tasks.write_text(original, encoding="utf-8")

        archived = run(
            self.root, [str(OPENSPEC), "archive", name, "--yes", "--json"]
        )
        archive_payload = json.loads(archived.stdout)
        self.assertTrue((Path(archive_payload["archive"]["path"]) / "handoff.md").is_file())
        main_spec = self.root / "openspec" / "specs" / "output" / "spec.md"
        self.assertTrue(main_spec.is_file())
        self.assertIn("Observable output", main_spec.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
