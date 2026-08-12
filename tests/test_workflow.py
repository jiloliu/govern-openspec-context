from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
INIT = SKILL_ROOT / "scripts" / "init_openspec_context.py"

FAKE_OPENSPEC = r'''#!/usr/bin/env python3
import sys
from pathlib import Path

args = sys.argv[1:]

if args == ["--version"]:
    print("1.8.0")
    raise SystemExit(0)

if args and args[0] == "init":
    root = Path(args[1])
    (root / "openspec" / "specs").mkdir(parents=True, exist_ok=True)
    (root / "openspec" / "changes").mkdir(parents=True, exist_ok=True)
    (root / "openspec" / "config.yaml").write_text(
        "schema: spec-driven\n", encoding="utf-8"
    )
    for name in (
        "openspec-propose",
        "openspec-explore",
        "openspec-apply-change",
        "openspec-archive-change",
    ):
        path = root / ".agents" / "skills" / name / "SKILL.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "---\nname: " + name + "\ndescription: generated\n---\n",
            encoding="utf-8",
        )
    print("initialized")
    raise SystemExit(0)

print("unsupported fake command", file=sys.stderr)
raise SystemExit(2)
'''


def git(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr or result.stdout)
    return result.stdout.strip()


class InitializerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "project"
        self.root.mkdir()
        git(self.root, "init", "-b", "main")
        self.fake = Path(self.temp.name) / "openspec"
        self.fake.write_text(FAKE_OPENSPEC, encoding="utf-8")
        self.fake.chmod(0o755)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_init(self, *extra: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run(
            [
                sys.executable,
                str(INIT),
                "--project-root",
                str(self.root),
                "--openspec-bin",
                str(self.fake),
                *extra,
            ],
            cwd=self.root,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_preview_is_read_only(self) -> None:
        result = self.run_init()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Mode: preview", result.stdout)
        self.assertIn("No files were changed", result.stdout)
        self.assertIn("<!-- govern-openspec-context:start -->", result.stdout)
        self.assertFalse((self.root / "openspec").exists())
        self.assertFalse(git(self.root, "status", "--porcelain"))

    def test_apply_uses_native_schema_and_adds_only_context_assets(self) -> None:
        result = self.run_init("--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Initialization completed", result.stdout)

        config = self.root / "openspec" / "config.yaml"
        context = self.root / "openspec" / "project-context.md"
        self.assertIn("schema: spec-driven", config.read_text(encoding="utf-8"))
        self.assertTrue(context.is_file())
        self.assertFalse((self.root / "openspec" / "schemas").exists())
        self.assertFalse(any(self.root.rglob("handoff.md")))
        self.assertFalse((self.root / "AGENTS.md").exists())
        self.assertTrue(
            (self.root / ".agents" / "skills" / "openspec-propose" / "SKILL.md").is_file()
        )

    def test_existing_setup_is_never_overwritten(self) -> None:
        first = self.run_init("--apply")
        self.assertEqual(first.returncode, 0, first.stderr)
        config = self.root / "openspec" / "config.yaml"
        original = config.read_text(encoding="utf-8")

        second = self.run_init("--apply")
        self.assertNotEqual(second.returncode, 0)
        self.assertIn("only for new OpenSpec adoption", second.stderr)
        self.assertEqual(config.read_text(encoding="utf-8"), original)

    def test_missing_and_incompatible_cli_are_rejected_before_writes(self) -> None:
        missing = subprocess.run(
            [
                sys.executable,
                str(INIT),
                "--project-root",
                str(self.root),
                "--openspec-bin",
                str(Path(self.temp.name) / "missing"),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertNotEqual(missing.returncode, 0)
        self.assertFalse((self.root / "openspec").exists())

        incompatible = self.fake.read_text(encoding="utf-8").replace(
            'print("1.8.0")', 'print("2.0.0")'
        )
        self.fake.write_text(incompatible, encoding="utf-8")
        result = self.run_init("--apply")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("major version 1", result.stderr)
        self.assertFalse((self.root / "openspec").exists())


if __name__ == "__main__":
    unittest.main()
