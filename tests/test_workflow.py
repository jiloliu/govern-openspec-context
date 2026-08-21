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
    tools = args[args.index("--tools") + 1].split(",")
    (root / "openspec" / "specs").mkdir(parents=True, exist_ok=True)
    (root / "openspec" / "changes").mkdir(parents=True, exist_ok=True)
    (root / "openspec" / "config.yaml").write_text(
        "schema: spec-driven\n", encoding="utf-8"
    )
    names = (
        "openspec-propose",
        "openspec-explore",
        "openspec-apply-change",
        "openspec-archive-change",
    )
    if "codebuddy" in tools or "all" in tools:
        for name in names:
            path = root / ".codebuddy" / "skills" / name / "SKILL.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                "---\nname: " + name + "\ndescription: generated\n---\n",
                encoding="utf-8",
            )
        for name in ("propose", "explore", "apply", "archive"):
            path = root / ".codebuddy" / "commands" / "opsx" / (name + ".md")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# generated\n", encoding="utf-8")
    if "codex" in tools or "agents" in tools or "all" in tools:
        for name in names:
            path = root / ".agents" / "skills" / name / "SKILL.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                "---\nname: " + name + "\ndescription: generated\n---\n",
                encoding="utf-8",
            )
    print("initialized tools=" + ",".join(tools))
    raise SystemExit(0)

print("unsupported fake command", file=sys.stderr)
raise SystemExit(2)
'''


class InitializerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.temp_root = Path(self.temp.name)
        self.root = self.temp_root / "project"
        self.root.mkdir()
        self.fake = self.temp_root / "openspec"
        self.fake.write_text(FAKE_OPENSPEC, encoding="utf-8")
        self.fake.chmod(0o755)
        self.codex_home = self.temp_root / "codex-home"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_init(self, *extra: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env.update(
            {
                "CODEX_HOME": str(self.codex_home),
                "PYTHONDONTWRITEBYTECODE": "1",
            }
        )
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

    def test_preview_is_read_only_and_reports_workbuddy_paths(self) -> None:
        result = self.run_init()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Mode: preview", result.stdout)
        self.assertIn("OpenSpec tools: codebuddy", result.stdout)
        self.assertIn(".codebuddy/skills/openspec-*", result.stdout)
        self.assertIn(".codebuddy/commands/opsx/*", result.stdout)
        self.assertNotIn(".agents/skills/openspec-*", result.stdout)
        self.assertIn("/govern-openspec-context", result.stdout)
        self.assertFalse((self.root / "openspec").exists())
        self.assertEqual(list(self.root.iterdir()), [])

    def test_apply_defaults_to_codebuddy_and_adds_context_assets(self) -> None:
        result = self.run_init("--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("initialized tools=codebuddy", result.stdout)

        config = self.root / "openspec" / "config.yaml"
        context = self.root / "openspec" / "project-context.md"
        self.assertIn("schema: spec-driven", config.read_text(encoding="utf-8"))
        self.assertTrue(context.is_file())
        self.assertFalse((self.root / "openspec" / "schemas").exists())
        self.assertFalse(any(self.root.rglob("handoff.md")))
        self.assertFalse((self.root / "AGENTS.md").exists())
        self.assertTrue(
            (
                self.root
                / ".codebuddy"
                / "skills"
                / "openspec-propose"
                / "SKILL.md"
            ).is_file()
        )
        self.assertTrue(
            (
                self.root
                / ".codebuddy"
                / "commands"
                / "opsx"
                / "propose.md"
            ).is_file()
        )
        self.assertFalse((self.root / ".agents").exists())

    def test_explicit_codex_override_uses_agents_tree(self) -> None:
        result = self.run_init("--tools", "codex", "--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OpenSpec tools: codex", result.stdout)
        self.assertIn(".agents/skills/openspec-*", result.stdout)
        self.assertNotIn(".codebuddy/skills/openspec-*", result.stdout)
        self.assertTrue(
            (
                self.root
                / ".agents"
                / "skills"
                / "openspec-propose"
                / "SKILL.md"
            ).is_file()
        )
        self.assertFalse((self.root / ".codebuddy").exists())

    def test_legacy_codebuddy_commands_are_rejected_before_writes(self) -> None:
        legacy = self.root / ".codebuddy" / "commands" / "openspec" / "proposal.md"
        legacy.parent.mkdir(parents=True)
        legacy.write_text("legacy\n", encoding="utf-8")

        result = self.run_init("--apply")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("may remove legacy instruction files", result.stderr)
        self.assertIn(str(legacy), result.stderr)
        self.assertFalse((self.root / "openspec").exists())

    def test_global_codex_prompts_are_checked_only_for_codex(self) -> None:
        prompt = self.codex_home / "prompts" / "openspec-proposal.md"
        prompt.parent.mkdir(parents=True)
        prompt.write_text("legacy\n", encoding="utf-8")

        default_result = self.run_init("--apply")
        self.assertEqual(default_result.returncode, 0, default_result.stderr)

        other_root = self.temp_root / "codex-project"
        other_root.mkdir()
        self.root = other_root
        codex_result = self.run_init("--tools", "codex", "--apply")
        self.assertNotEqual(codex_result.returncode, 0)
        self.assertIn(str(prompt), codex_result.stderr)
        self.assertFalse((other_root / "openspec").exists())

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
                str(self.temp_root / "missing"),
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
