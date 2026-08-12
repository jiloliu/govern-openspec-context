from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
INIT = SKILL_ROOT / "scripts" / "init_openspec_context.py"
CHECK = SKILL_ROOT / "scripts" / "check_openspec_context.py"

FAKE_OPENSPEC = r'''#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path

args = sys.argv[1:]
cwd = Path.cwd()

if args == ["--version"]:
    print("1.8.0")
    raise SystemExit(0)

if args and args[0] == "init":
    root = Path(args[1])
    (root / "openspec" / "specs").mkdir(parents=True, exist_ok=True)
    (root / "openspec" / "changes").mkdir(parents=True, exist_ok=True)
    (root / "openspec" / "config.yaml").write_text("schema: spec-driven\n", encoding="utf-8")
    for name in (
        "openspec-propose",
        "openspec-explore",
        "openspec-apply-change",
        "openspec-sync-specs",
        "openspec-archive-change",
    ):
        path = root / ".agents" / "skills" / name / "SKILL.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("---\nname: " + name + "\ndescription: generated\n---\n", encoding="utf-8")
    print("initialized")
    raise SystemExit(0)

if args[:2] == ["schema", "validate"]:
    schema = args[2]
    path = cwd / "openspec" / "schemas" / schema / "schema.yaml"
    if (cwd / "SCHEMA_INVALID_JSON").exists():
        print("not-json")
        raise SystemExit(0)
    valid = path.is_file()
    print(json.dumps({"valid": valid, "schema": schema}))
    raise SystemExit(0 if valid else 1)

if args == ["list", "--json"]:
    if (cwd / "LIST_INVALID_JSON").exists():
        print("not-json")
        raise SystemExit(0)
    changes = cwd / "openspec" / "changes"
    names = sorted(p.name for p in changes.iterdir() if p.is_dir() and p.name != "archive")
    print(json.dumps({"changes": [{"name": name} for name in names]}))
    raise SystemExit(0)

if args and args[0] == "status":
    name = args[args.index("--change") + 1]
    root = cwd / "openspec" / "changes" / name
    metadata = (root / ".openspec.yaml").read_text(encoding="utf-8")
    schema_match = re.search(r"(?m)^schema:\s*(\S+)", metadata)
    schema = schema_match.group(1) if schema_match else "spec-driven"
    required = ["proposal.md", "tasks.md", "handoff.md"]
    if schema == "governed-standard":
        required.append("design.md")
    complete = all((root / item).is_file() for item in required)
    if schema == "governed-standard":
        complete = complete and any((root / "specs").rglob("*.md"))
    print(json.dumps({
        "changeName": name,
        "schemaName": schema,
        "isPlanningComplete": complete,
        "isComplete": complete,
        "artifacts": [],
    }))
    raise SystemExit(0)

if args and args[0] == "instructions":
    action = args[1]
    name = args[args.index("--change") + 1]
    root = cwd / "openspec" / "changes" / name
    if action == "archive":
        print(json.dumps({"changeName": name, "operationGuidance": []}))
        raise SystemExit(0)
    if action == "apply":
        text = (root / "tasks.md").read_text(encoding="utf-8")
        tasks = re.findall(r"(?m)^\s*-\s*\[([ xX])\]\s+", text)
        complete = sum(1 for mark in tasks if mark.lower() == "x")
        print(json.dumps({
            "changeName": name,
            "progress": {"total": len(tasks), "complete": complete, "remaining": len(tasks) - complete},
            "state": "all_done" if complete == len(tasks) else "in_progress",
        }))
        raise SystemExit(0)

if args and args[0] == "validate":
    name = args[1]
    if (cwd / "VALIDATE_INVALID_JSON").exists():
        print("not-json")
        raise SystemExit(0)
    fail = (cwd / "openspec" / "changes" / name / "FAIL_VALIDATION").exists()
    print(json.dumps({
        "items": [{"id": name, "type": "change", "valid": not fail, "issues": []}],
        "summary": {"totals": {"items": 1, "passed": 0 if fail else 1, "failed": 1 if fail else 0}},
    }))
    raise SystemExit(1 if fail else 0)

print(json.dumps({"error": "unsupported fake command", "args": args}))
raise SystemExit(2)
'''


FILLED_CONTEXT = """# Project Context

## Product and scope
- Purpose: Exercise governance validation.
- In scope: Test fixtures.
- Out of scope: Production work.

## Architecture map
- Entry points: src/.
- Major modules and ownership: test fixture.
- Data and control flow: none.

## Contracts and invariants
- Public interfaces: none.
- Data or compatibility invariants: none.
- Security and operational constraints: no secrets.

## Verification commands
- Build: not applicable.
- Test: python3 -m unittest.
- Lint or static analysis: python3 -m py_compile.
- Change-specific verification: see each change.

## Authoritative sources
- Accepted behavior: openspec/specs/.
- Active changes: openspec/changes/.
- Architecture or operations documentation: none.

## Delivery policy
- Branch/worktree convention: one branch per change.
- Archive timing: after merge.
- Deployment is separate from development completion: yes.

## Durable cautions
- Preserve existing work.
"""


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=False,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr or result.stdout)
    return result.stdout.strip()


def handoff(
    change: str,
    branch: str,
    checkpoint: str,
    *,
    owner: str = "codex-primary",
    status: str = "awaiting-merge",
    current: str = "none",
    last_completed: str = "2.3",
    next_action: str = "Archive after merge.",
    result: str = "pass",
    exit_code: str = "0",
    uncommitted: tuple[str, ...] = (),
    blockers: str = "None.",
) -> str:
    paths = "\n".join(f"- `{path}`" for path in uncommitted) or "- None."
    verification_commit = checkpoint if result == "pass" else "none"
    verified_at = "2030-01-01T00:01:00+00:00" if result != "not-run" else "none"
    command = "python3 -m unittest" if result != "not-run" else "none"
    return f"""# Change Handoff

## Snapshot

- Change: {change}
- Owner: {owner}
- Branch: {branch}
- Status: `{status}`
- Current task: `{current}`
- Last completed task: `{last_completed}`
- Checkpoint commit: `{checkpoint}`
- Checkpoint time: 2030-01-01T00:00:00+00:00
- Exact next action: {next_action}

## Latest Verification

- Result: `{result}`
- Command: `{command}`
- Exit code: `{exit_code}`
- Verified at: `{verified_at}`
- Verification commit: `{verification_commit}`

## Uncommitted Paths

{paths}

## Blockers and Deviations

- {blockers}
"""


class WorkflowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "project"
        self.root.mkdir()
        self.fake = Path(self.temp.name) / "openspec"
        self.fake.write_text(FAKE_OPENSPEC, encoding="utf-8")
        self.fake.chmod(0o755)
        git(self.root, "init", "-b", "main")
        git(self.root, "config", "user.email", "tests@example.invalid")
        git(self.root, "config", "user.name", "Workflow Tests")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_script(self, script: Path, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPYCACHEPREFIX"] = str(Path(self.temp.name) / "pycache")
        return subprocess.run(
            [sys.executable, str(script), *args], text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, check=False,
        )

    def initialize(self) -> str:
        result = self.run_script(
            INIT, "--project-root", str(self.root), "--openspec-bin", str(self.fake), "--apply"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        (self.root / "openspec" / "project-context.md").write_text(FILLED_CONTEXT, encoding="utf-8")
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", "initialize governed OpenSpec")
        return git(self.root, "rev-parse", "HEAD")

    def add_rapid_change(
        self,
        name: str,
        *,
        branch: str = "main",
        owner: str = "codex-primary",
        status: str = "awaiting-merge",
        current: str = "none",
        result: str = "pass",
        exit_code: str = "0",
        next_action: str = "Archive after merge.",
    ) -> str:
        root = self.root / "openspec" / "changes" / name
        root.mkdir(parents=True)
        (root / ".openspec.yaml").write_text(
            "schema: governed-rapid\nskip_specs: true\n", encoding="utf-8"
        )
        (root / "proposal.md").write_text(
            "## Why\nInternal cleanup.\n\n## Risk Profile\n- Profile: `rapid`\n",
            encoding="utf-8",
        )
        complete = status not in {"planned", "in-progress", "blocked"}
        mark = "x" if complete else " "
        (root / "tasks.md").write_text(
            f"## Work\n- [{mark}] 1.1 Refactor.\n- [{mark}] 2.1 Test.\n- [{mark}] 2.3 Handoff.\n",
            encoding="utf-8",
        )
        (self.root / "src").mkdir(exist_ok=True)
        (self.root / "src" / f"{name}.txt").write_text("implemented\n", encoding="utf-8")
        placeholder = git(self.root, "rev-parse", "HEAD")
        (root / "handoff.md").write_text(
            handoff(
                name, branch, placeholder, owner=owner, status=status, current=current,
                last_completed="none" if not complete else "2.3", result="not-run",
                exit_code="none", next_action=next_action,
            ), encoding="utf-8",
        )
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", f"implement {name}")
        checkpoint = git(self.root, "rev-parse", "HEAD")
        dirty_path = f"openspec/changes/{name}/handoff.md"
        (root / "handoff.md").write_text(
            handoff(
                name, branch, checkpoint, owner=owner, status=status, current=current,
                last_completed="none" if not complete else "2.3", result=result,
                exit_code=exit_code, next_action=next_action, uncommitted=(dirty_path,),
            ), encoding="utf-8",
        )
        return checkpoint

    def add_standard_change(self, name: str) -> str:
        root = self.root / "openspec" / "changes" / name
        (root / "specs" / "example").mkdir(parents=True)
        (root / ".openspec.yaml").write_text("schema: governed-standard\n", encoding="utf-8")
        (root / "proposal.md").write_text(
            "## Why\nAdd behavior.\n\n## Risk Profile\n- Profile: `standard`\n", encoding="utf-8"
        )
        (root / "specs" / "example" / "spec.md").write_text(
            "## ADDED Requirements\n\n### Requirement: Example\nThe system SHALL respond.\n\n"
            "#### Scenario: Success\n- **GIVEN** a request\n- **WHEN** handled\n- **THEN** success\n",
            encoding="utf-8",
        )
        (root / "design.md").write_text("## Context\nExisting service.\n", encoding="utf-8")
        (root / "tasks.md").write_text(
            "## Work\n- [x] 1.1 Implement.\n- [x] 2.1 Test.\n- [x] 2.3 Handoff.\n",
            encoding="utf-8",
        )
        placeholder = git(self.root, "rev-parse", "HEAD")
        (root / "handoff.md").write_text(
            handoff(name, "main", placeholder, result="not-run", exit_code="none"),
            encoding="utf-8",
        )
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", f"implement {name}")
        checkpoint = git(self.root, "rev-parse", "HEAD")
        dirty = f"openspec/changes/{name}/handoff.md"
        (root / "handoff.md").write_text(
            handoff(name, "main", checkpoint, uncommitted=(dirty,)), encoding="utf-8"
        )
        return checkpoint

    def check(self, *extra: str) -> subprocess.CompletedProcess[str]:
        return self.run_script(
            CHECK, "--project-root", str(self.root), "--openspec-bin", str(self.fake),
            *extra, "--json",
        )

    def test_preview_is_read_only_and_apply_installs_assets(self) -> None:
        preview = self.run_script(
            INIT, "--project-root", str(self.root), "--openspec-bin", str(self.fake)
        )
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertFalse((self.root / "openspec").exists())
        self.assertFalse(git(self.root, "status", "--porcelain"))

        self.initialize()
        self.assertTrue((self.root / "openspec" / "project-context.md").is_file())
        self.assertFalse((self.root / "openspec" / "governance-context.json").exists())
        self.assertIn(
            "schema: governed-standard",
            (self.root / "openspec" / "config.yaml").read_text(encoding="utf-8"),
        )
        second = self.run_script(
            INIT, "--project-root", str(self.root), "--openspec-bin", str(self.fake), "--apply"
        )
        self.assertNotEqual(second.returncode, 0)
        self.assertIn("only for new OpenSpec adoption", second.stderr)

    def test_initializer_rejects_missing_incompatible_and_invalid_json_cli(self) -> None:
        missing = self.run_script(
            INIT, "--project-root", str(self.root), "--openspec-bin", str(self.root / "missing")
        )
        self.assertNotEqual(missing.returncode, 0)

        text = self.fake.read_text(encoding="utf-8").replace('print("1.8.0")', 'print("2.0.0")')
        self.fake.write_text(text, encoding="utf-8")
        incompatible = self.run_script(
            INIT, "--project-root", str(self.root), "--openspec-bin", str(self.fake)
        )
        self.assertNotEqual(incompatible.returncode, 0)
        self.assertIn("major version 1", incompatible.stderr)

        self.fake.write_text(FAKE_OPENSPEC, encoding="utf-8")
        self.fake.chmod(0o755)
        (self.root / "SCHEMA_INVALID_JSON").touch()
        invalid = self.run_script(
            INIT, "--project-root", str(self.root), "--openspec-bin", str(self.fake), "--apply"
        )
        self.assertNotEqual(invalid.returncode, 0)
        self.assertIn("invalid JSON", invalid.stderr)

    def test_checker_accepts_valid_rapid_and_standard_changes(self) -> None:
        self.initialize()
        self.add_rapid_change("cleanup-tools")
        rapid = self.check(
            "--change", "cleanup-tools", "--owner", "codex-primary", "--strict"
        )
        self.assertEqual(rapid.returncode, 0, rapid.stdout + rapid.stderr)

        git(self.root, "add", ".")
        git(self.root, "commit", "-m", "record rapid handoff")
        self.add_standard_change("add-behavior")
        standard = self.check("--change", "add-behavior", "--strict")
        self.assertEqual(standard.returncode, 0, standard.stdout + standard.stderr)

    def test_checker_rejects_failed_verification_and_stale_git_evidence(self) -> None:
        self.initialize()
        self.add_rapid_change("cleanup-tools", result="fail", exit_code="1")
        failed = self.check("--change", "cleanup-tools", "--strict")
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("terminal status requires verification Result pass", failed.stdout)

        handoff_path = self.root / "openspec" / "changes" / "cleanup-tools" / "handoff.md"
        checkpoint = git(self.root, "rev-parse", "HEAD")
        handoff_path.write_text(
            handoff(
                "cleanup-tools", "main", checkpoint, result="pass", exit_code="0",
                uncommitted=("openspec/changes/cleanup-tools/handoff.md", "src/cleanup-tools.txt"),
            ), encoding="utf-8",
        )
        (self.root / "src" / "cleanup-tools.txt").write_text("changed after verification\n", encoding="utf-8")
        stale = self.check("--change", "cleanup-tools", "--strict")
        self.assertNotEqual(stale.returncode, 0)
        self.assertIn("unverified implementation paths", stale.stdout)

    def test_checker_rejects_ownership_task_and_open_spec_failures(self) -> None:
        self.initialize()
        self.add_rapid_change("cleanup-tools")
        owner = self.check("--change", "cleanup-tools", "--owner", "another-writer")
        self.assertNotEqual(owner.returncode, 0)
        self.assertIn("ownership conflict", owner.stdout)

        tasks = self.root / "openspec" / "changes" / "cleanup-tools" / "tasks.md"
        tasks.write_text(tasks.read_text(encoding="utf-8").replace("[x] 2.3", "[ ] 2.3"), encoding="utf-8")
        task = self.check("--change", "cleanup-tools")
        self.assertNotEqual(task.returncode, 0)
        self.assertIn("not checked complete", task.stdout)

        tasks.write_text(tasks.read_text(encoding="utf-8").replace("[ ] 2.3", "[x] 2.3"), encoding="utf-8")
        (self.root / "openspec" / "changes" / "cleanup-tools" / "FAIL_VALIDATION").touch()
        validation = self.check("--change", "cleanup-tools")
        self.assertNotEqual(validation.returncode, 0)
        self.assertIn("OpenSpec strict validation failed", validation.stdout)

    def test_checker_requires_explicit_selection_for_multiple_changes(self) -> None:
        self.initialize()
        self.add_rapid_change("cleanup-a", branch="feature/a")
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", "record first change")
        self.add_rapid_change("cleanup-b", branch="feature/b")
        result = self.check("--all", "--strict")
        self.assertEqual(result.returncode, 0, result.stdout)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["facts"]["selectionRequired"])
        self.assertNotIn("resolvedChange", payload["facts"])

    def test_checker_resolves_the_unique_current_branch_match(self) -> None:
        self.initialize()
        self.add_rapid_change("cleanup-main", branch="main")
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", "record main change")
        self.add_rapid_change("cleanup-feature", branch="feature/b")
        result = self.check("--all", "--strict")
        self.assertEqual(result.returncode, 0, result.stdout)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["facts"]["branchMatches"], ["cleanup-main"])
        self.assertEqual(payload["facts"]["resolvedChange"], "cleanup-main")
        self.assertNotIn("selectionRequired", payload["facts"])

    def test_checker_rejects_multiple_changes_on_one_branch_and_invalid_json(self) -> None:
        self.initialize()
        self.add_rapid_change("cleanup-a", branch="main")
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", "record first change")
        self.add_rapid_change("cleanup-b", branch="main")
        shared = self.check("--all")
        self.assertNotEqual(shared.returncode, 0)
        self.assertIn("multiple active changes", shared.stdout)

        (self.root / "LIST_INVALID_JSON").touch()
        invalid = self.check("--all")
        self.assertNotEqual(invalid.returncode, 0)
        self.assertIn("invalid JSON", invalid.stdout)


if __name__ == "__main__":
    unittest.main()
