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

FILLED_CONTEXT = """# 项目上下文 / Project Context

## 产品与范围 / Product and scope
- 用途 / Purpose: 验证原生 OpenSpec 集成。 / Exercise native OpenSpec integration.
- 范围内 / In scope: 临时集成测试。 / Temporary integration fixtures.
- 范围外 / Out of scope: 生产系统。 / Production systems.

## 架构图 / Architecture map
- 入口点 / Entry points: `src/`。
- 主要模块与职责 / Major modules and responsibilities: 临时测试夹具。 / Temporary fixture.
- 依赖方向与数据流 / Dependency direction and data flow: 仅本地文件。 / Local files only.

## 契约与不变量 / Contracts and invariants
- 公共接口 / Public interfaces: 测试文本输出。 / Fixture text output.
- 数据或兼容性不变量 / Data or compatibility invariants: UTF-8 文件。 / UTF-8 files.
- 安全与运维约束 / Security and operational constraints: 不使用外部服务。 / No external services.

## 验证命令 / Verification commands
- 构建 / Build: 不适用。 / Not applicable.
- 测试 / Test: `python3 -m unittest`。
- 代码检查或静态分析 / Lint or static analysis: 不适用。 / Not applicable.
- 变更专项验证 / Change-specific verification: 参见活动变更的 `tasks.md`。 / See the active change's `tasks.md`.

## 权威来源 / Authoritative sources
- 已接受行为 / Accepted behavior: `openspec/specs/`。
- 活动变更 / Active changes: `openspec/changes/`。
- 架构决策 / Architecture decisions: `docs/adr/`。
- 详细架构与运维文档 / Detailed architecture and operations documentation: 无。 / None.

## 交付策略 / Delivery policy
- 分支或工作树约定 / Branch/worktree convention: 每个变更一个分支。 / One branch per change.
- 归档时机 / Archive timing: 本地验证后。 / After local verification.
- 部署与开发完成相互独立 / Deployment is separate from development completion: 是。 / Yes.

## 持久注意事项 / Durable cautions
- 保持测试夹具为本地文件。 / Keep fixtures local.
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


@unittest.skipUnless(OPENSPEC, "OpenSpec CLI is not installed")
class NativeOpenSpecIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "project"
        self.root.mkdir()

        version = run(self.root, [str(OPENSPEC), "--version"]).stdout.strip()
        version = version.removeprefix("v")
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
        self.assertIn("OpenSpec tools: codebuddy", initialized.stdout)
        self.assertIn("Initialization completed", initialized.stdout)
        (self.root / "openspec" / "project-context.md").write_text(
            FILLED_CONTEXT, encoding="utf-8"
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_codebuddy_change_validates_and_archives(self) -> None:
        self.assertFalse((self.root / "openspec" / "schemas").exists())
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

        schemas = json.loads(
            run(self.root, [str(OPENSPEC), "schemas", "--json"]).stdout
        )
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
            "## Why\n增加稳定的输出标记。\n\nEnglish: Expose a stable output marker.\n\n"
            "## What Changes\n增加输出文件。\n\nEnglish: Add an output file.\n\n"
            "## Capabilities\n### New Capabilities\n"
            "- `output`: 写入标记。 / Write a marker.\n\n"
            "## Impact\n仅影响本地测试夹具。\n\nEnglish: Local fixture only.\n",
            encoding="utf-8",
        )
        (change / "specs" / "output" / "spec.md").write_text(
            "## ADDED Requirements\n\n"
            "### Requirement: 可观察输出 / Observable output\n"
            "系统 SHALL 写入输出标记。 / The system SHALL write an output marker.\n\n"
            "#### Scenario: 写入标记 / Marker written\n"
            "- **WHEN** 运行完成 / a run completes\n"
            "- **THEN** 写入输出标记 / an output marker is written\n",
            encoding="utf-8",
        )
        (change / "design.md").write_text(
            "## Context\n本地测试夹具。\n\nEnglish: Local fixture.\n\n"
            "## Goals / Non-Goals\n增加一个标记。 / Add one marker.\n\n"
            "## Decisions\n写入 UTF-8 文件。 / Write a UTF-8 file.\n\n"
            "## Risks / Trade-offs\n无。 / None.\n\n"
            "## Migration Plan\n无需迁移。 / No migration.\n\n"
            "## Open Questions\n无。 / None.\n",
            encoding="utf-8",
        )
        (change / "tasks.md").write_text(
            "## 1. 实施 / Implementation\n"
            "- [x] 1.1 写入标记。 / Write the marker.\n\n"
            "## 2. 验证 / Verification\n"
            "- [x] 2.1 验证场景。 / Validate the scenario.\n",
            encoding="utf-8",
        )
        (self.root / "src").mkdir()
        (self.root / "src" / "output.txt").write_text("marker\n", encoding="utf-8")

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
        if not archive_dir.is_absolute():
            archive_dir = self.root / archive_dir
        self.assertTrue(archive_dir.is_dir())
        self.assertFalse(any(archive_dir.rglob("handoff.md")))
        main_spec = self.root / "openspec" / "specs" / "output" / "spec.md"
        self.assertIn("Observable output", main_spec.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
