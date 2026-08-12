#!/usr/bin/env python3
"""Read-only audit for govern-openspec-context projects and active changes."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence


EXPECTED_SCHEMAS = {"governed-standard", "governed-rapid"}
ALLOWED_STATUSES = {
    "planned",
    "in-progress",
    "blocked",
    "verified",
    "awaiting-merge",
    "awaiting-archive",
}
TERMINAL_WORK_STATUSES = {"verified", "awaiting-merge", "awaiting-archive"}
VERSION_RE = re.compile(r"v?(\d+)\.(\d+)(?:\.(\d+))?")
CHANGE_ID_RE = re.compile(r"^[a-z0-9](?:[a-z0-9]|-(?=[a-z0-9]))*$")
TASK_RE = re.compile(r"^\s*-\s*\[([ xX])\]\s+([0-9]+(?:\.[0-9]+)*)\b", re.MULTILINE)
BULLET_RE = re.compile(r"^\s*-\s*([^:\n]+):\s*(.*?)\s*$", re.MULTILINE)
PLACEHOLDER_RE = re.compile(r"TODO|<!--|<change|<owner|<branch|<commit|<time", re.IGNORECASE)
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(
        r"\b(?:api[_-]?key|access[_-]?token|client[_-]?secret)\s*[:=]\s*[^\s<]{8,}",
        re.IGNORECASE,
    ),
)
ISO_TIMESTAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})$"
)
COMMIT_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")
SNAPSHOT_KEYS = (
    "change",
    "owner",
    "branch",
    "status",
    "current task",
    "last completed task",
    "checkpoint commit",
    "checkpoint time",
    "exact next action",
)
VERIFICATION_KEYS = ("result", "command", "exit code", "verified at", "verification commit")
ALLOWED_POST_CHECKPOINT_SUFFIXES = ("/handoff.md",)


class AuditError(RuntimeError):
    """An error that prevents reliable auditing."""


@dataclass
class Report:
    project_root: str
    changes: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    facts: dict[str, Any] = field(default_factory=dict)

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def payload(self, strict: bool) -> dict[str, Any]:
        return {
            "ok": not self.errors and (not strict or not self.warnings),
            "strict": strict,
            "projectRoot": self.project_root,
            "changes": self.changes,
            "errors": self.errors,
            "warnings": self.warnings,
            "facts": self.facts,
        }


@dataclass(frozen=True)
class GitState:
    root: Path
    branch: str
    head: str
    dirty_paths: frozenset[str]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit OpenSpec context, handoffs, Git checkpoints, tasks, and validation."
    )
    parser.add_argument("--project-root", required=True, type=Path)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--change", help="Audit one active change by exact ID.")
    selection.add_argument("--all", action="store_true", help="Audit all active changes.")
    parser.add_argument("--owner", help="Expected writer identity for ownership conflict checks.")
    parser.add_argument("--openspec-bin", default="openspec")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failure.")
    parser.add_argument("--json", action="store_true", dest="json_output")
    return parser.parse_args(argv)


def command_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "DO_NOT_TRACK": "1",
            "NO_COLOR": "1",
            "OPENSPEC_NO_UPDATE_CHECK": "1",
            "OPENSPEC_TELEMETRY": "0",
        }
    )
    return env


def resolve_executable(value: str) -> str:
    candidate = Path(value).expanduser()
    if candidate.parent != Path(".") or candidate.is_absolute():
        if not candidate.is_file():
            raise AuditError(f"OpenSpec executable not found: {candidate}")
        return str(candidate.resolve())
    resolved = shutil.which(value)
    if not resolved:
        raise AuditError("OpenSpec CLI was not found on PATH.")
    return resolved


def run_process(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=command_env(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def run_json(
    executable: str, arguments: list[str], cwd: Path, allow_nonzero: bool = False
) -> tuple[Any, int]:
    result = run_process([executable, *arguments], cwd)
    raw = result.stdout.strip()
    if not raw:
        details = result.stderr.strip() or "no JSON output"
        raise AuditError(f"{' '.join(arguments)}: {details}")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise AuditError(
            f"{' '.join(arguments)} returned invalid JSON at character {error.pos}."
        ) from error
    if isinstance(payload, dict) and payload.get("error") and result.returncode == 0:
        raise AuditError(f"{' '.join(arguments)} returned structured error JSON.")
    if result.returncode != 0 and not allow_nonzero:
        raise AuditError(f"{' '.join(arguments)} failed with exit {result.returncode}.")
    return payload, result.returncode


def detect_version(executable: str, project_root: Path) -> str:
    result = run_process([executable, "--version"], project_root)
    output = result.stdout.strip() or result.stderr.strip()
    match = VERSION_RE.fullmatch(output)
    if result.returncode != 0 or not match:
        raise AuditError("Unable to determine OpenSpec CLI version from its version surface.")
    if int(match.group(1)) != 1:
        raise AuditError(f"OpenSpec major version 1 is required; found {output}.")
    return output.removeprefix("v")


def active_change_names(payload: Any) -> list[str]:
    entries: Any
    if isinstance(payload, list):
        entries = payload
    elif isinstance(payload, dict):
        entries = next(
            (
                payload[key]
                for key in ("changes", "items", "results")
                if isinstance(payload.get(key), list)
            ),
            None,
        )
    else:
        entries = None
    if entries is None:
        raise AuditError("openspec list --json returned an unrecognized structure.")

    names: list[str] = []
    for entry in entries:
        if isinstance(entry, str):
            name = entry
        elif isinstance(entry, dict):
            name = next(
                (
                    entry[key]
                    for key in ("name", "changeName", "id")
                    if isinstance(entry.get(key), str)
                ),
                None,
            )
        else:
            name = None
        if name and CHANGE_ID_RE.fullmatch(name):
            names.append(name)
        elif name:
            raise AuditError(f"OpenSpec returned an unsafe or invalid change ID: {name!r}")
    return sorted(set(names))


def parse_bullets(text: str, change: str, report: Report) -> dict[str, str]:
    fields: dict[str, str] = {}
    for raw_key, raw_value in BULLET_RE.findall(text):
        key = raw_key.strip().lower()
        value = raw_value.strip().strip("`")
        if key in fields:
            report.error(f"{change}: handoff field {key!r} is duplicated.")
        fields[key] = value
    return fields


def required_value(
    fields: dict[str, str], key: str, change: str, report: Report
) -> str | None:
    value = fields.get(key)
    if not value or PLACEHOLDER_RE.search(value):
        report.error(f"{change}: handoff field {key!r} is missing or still a placeholder.")
        return None
    return value


def read_text(path: Path, change: str, report: Report) -> str | None:
    if not path.is_file():
        report.error(f"{change}: required file is missing: {path.name}")
        return None
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        report.error(f"{change}: required file is not valid UTF-8: {path.name}")
        return None


def find_secrets(change: str, filename: str, text: str, report: Report) -> None:
    if any(pattern.search(text) for pattern in SECRET_PATTERNS):
        report.error(f"{change}: potential secret material detected in {filename}; redact it.")


def section_body(text: str, heading: str) -> str | None:
    match = re.search(
        rf"(?ms)^## {re.escape(heading)}\s*\n(.*?)(?=^## |\Z)", text
    )
    return match.group(1).strip() if match else None


def parse_path_section(text: str, change: str, report: Report) -> set[str]:
    body = section_body(text, "Uncommitted Paths")
    if body is None:
        report.error(f"{change}: handoff lacks Uncommitted Paths section.")
        return set()
    paths: set[str] = set()
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if not stripped.startswith("-"):
            report.error(f"{change}: Uncommitted Paths must be a bullet list.")
            continue
        value = stripped[1:].strip().strip("`")
        if value.lower().rstrip(".") == "none":
            if paths or len([item for item in body.splitlines() if item.strip()]) > 1:
                report.error(f"{change}: Uncommitted Paths cannot mix None with paths.")
            continue
        path = Path(value)
        if path.is_absolute() or ".." in path.parts:
            report.error(f"{change}: unsafe uncommitted path {value!r}.")
            continue
        paths.add(path.as_posix())
    return paths


def section_is_none(text: str, heading: str) -> bool | None:
    body = section_body(text, heading)
    if body is None:
        return None
    normalized = " ".join(body.lower().replace("`", "").split()).rstrip(".")
    return normalized in {"- none", "none"}


def parse_timestamp(value: str, label: str, change: str, report: Report) -> datetime | None:
    if not ISO_TIMESTAMP_RE.fullmatch(value):
        report.error(f"{change}: {label} must be an ISO 8601 timestamp with timezone.")
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        report.error(f"{change}: {label} is not a valid timestamp.")
        return None


def run_git(project_root: Path, arguments: list[str]) -> subprocess.CompletedProcess[str]:
    git = shutil.which("git")
    if not git:
        raise AuditError("Git was not found on PATH.")
    return subprocess.run(
        [git, *arguments],
        cwd=project_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def git_output(project_root: Path, arguments: list[str]) -> str:
    result = run_git(project_root, arguments)
    if result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip() or "unknown Git error"
        raise AuditError(f"git {' '.join(arguments)}: {details}")
    return result.stdout.strip()


def collect_dirty_paths(project_root: Path) -> frozenset[str]:
    paths: set[str] = set()
    commands = (
        ["diff", "--name-only", "-z"],
        ["diff", "--cached", "--name-only", "-z"],
        ["ls-files", "--others", "--exclude-standard", "-z"],
    )
    for command in commands:
        output = git_output(project_root, command)
        paths.update(value for value in output.split("\0") if value)
    return frozenset(paths)


def inspect_git(project_root: Path, report: Report) -> GitState | None:
    try:
        root = Path(git_output(project_root, ["rev-parse", "--show-toplevel"])).resolve()
        if root != project_root:
            report.error(
                f"project: --project-root must be the Git root ({root}), not {project_root}."
            )
        branch = git_output(project_root, ["branch", "--show-current"])
        if not branch:
            report.error("project: detached HEAD cannot establish handoff branch ownership.")
        head = git_output(project_root, ["rev-parse", "HEAD"])
        dirty = collect_dirty_paths(project_root)
        report.facts.update({"gitBranch": branch, "gitHead": head, "dirtyPaths": sorted(dirty)})
        return GitState(root=root, branch=branch, head=head, dirty_paths=dirty)
    except AuditError as error:
        report.error(f"project: Git evidence is unavailable: {error}")
        return None


def resolve_commit(project_root: Path, value: str) -> str | None:
    if not COMMIT_RE.fullmatch(value):
        return None
    result = run_git(project_root, ["rev-parse", "--verify", f"{value}^{{commit}}"])
    return result.stdout.strip() if result.returncode == 0 else None


def commit_is_ancestor(project_root: Path, ancestor: str, descendant: str) -> bool:
    return run_git(project_root, ["merge-base", "--is-ancestor", ancestor, descendant]).returncode == 0


def paths_after_commit(project_root: Path, commit: str, head: str) -> set[str]:
    output = git_output(project_root, ["diff", "--name-only", "-z", f"{commit}..{head}"])
    return {value for value in output.split("\0") if value}


def validate_task_state(
    change: str, tasks_text: str, fields: dict[str, str], report: Report
) -> tuple[bool, list[str], set[str]]:
    matches = TASK_RE.findall(tasks_text)
    if not matches:
        report.error(f"{change}: tasks.md contains no numbered checkbox tasks.")
        return False, [], set()
    task_ids = [task_id for _, task_id in matches]
    if len(task_ids) != len(set(task_ids)):
        report.error(f"{change}: tasks.md contains duplicate task IDs.")
    completed = {task_id for mark, task_id in matches if mark.lower() == "x"}
    all_complete = len(completed) == len(matches)
    current = fields.get("current task", "").strip().strip("`")
    last_completed = fields.get("last completed task", "").strip().strip("`")
    status = fields.get("status", "").strip().strip("`")

    if current.lower() != "none":
        if current not in task_ids:
            report.error(f"{change}: Current task {current!r} is not present in tasks.md.")
        elif current in completed:
            report.error(f"{change}: Current task {current!r} is already checked complete.")
    elif status in {"planned", "in-progress"}:
        report.error(f"{change}: {status} handoff must identify an incomplete current task.")

    if last_completed.lower() != "none":
        if last_completed not in task_ids:
            report.error(
                f"{change}: Last completed task {last_completed!r} is not present in tasks.md."
            )
        elif last_completed not in completed:
            report.error(f"{change}: Last completed task {last_completed!r} is not checked complete.")
    elif completed:
        report.error(f"{change}: completed tasks exist but Last completed task is none.")

    if completed and last_completed in task_ids:
        expected_last = next(task_id for task_id in reversed(task_ids) if task_id in completed)
        if last_completed != expected_last:
            report.error(
                f"{change}: Last completed task must be the latest checked task {expected_last!r}."
            )
    if status in TERMINAL_WORK_STATUSES and not all_complete:
        report.error(f"{change}: status {status!r} requires all task checkboxes complete.")
    if all_complete and status not in TERMINAL_WORK_STATUSES:
        report.warn(f"{change}: all tasks are complete but handoff status is {status!r}.")
    return all_complete, task_ids, completed


def validate_open_spec_result(change: str, payload: Any, code: int, report: Report) -> None:
    if code != 0:
        report.error(f"{change}: OpenSpec strict validation failed with exit {code}.")
        return
    if not isinstance(payload, dict):
        report.error(f"{change}: OpenSpec validate JSON must be an object.")
        return
    explicit: list[bool] = []
    if isinstance(payload.get("valid"), bool):
        explicit.append(payload["valid"])
    items = payload.get("items")
    if isinstance(items, list):
        explicit.extend(item.get("valid") is True for item in items if isinstance(item, dict))
    results = payload.get("results")
    if isinstance(results, dict):
        for value in results.values():
            if isinstance(value, list):
                explicit.extend(
                    item.get("valid") is True for item in value if isinstance(item, dict)
                )
    summary = payload.get("summary")
    if isinstance(summary, dict):
        totals = summary.get("totals", summary)
        if isinstance(totals, dict):
            for key in ("failed", "invalid"):
                if isinstance(totals.get(key), int) and totals[key] != 0:
                    explicit.append(False)
    if not explicit:
        report.error(f"{change}: OpenSpec validate JSON contains no explicit validity result.")
    elif not all(explicit):
        report.error(f"{change}: OpenSpec validate JSON reports invalid items.")


def validate_instruction_state(
    change: str,
    payload: Any,
    local_total: int,
    local_complete: int,
    terminal: bool,
    report: Report,
) -> None:
    if not isinstance(payload, dict) or payload.get("changeName") != change:
        report.error(f"{change}: instructions apply JSON has an invalid change identity.")
        return
    progress = payload.get("progress")
    if not isinstance(progress, dict):
        report.error(f"{change}: instructions apply JSON lacks progress state.")
        return
    if progress.get("total") != local_total or progress.get("complete") != local_complete:
        report.error(f"{change}: OpenSpec task progress disagrees with tasks.md.")
    state = payload.get("state")
    if terminal and state != "all_done":
        report.error(f"{change}: terminal handoff requires OpenSpec apply state all_done.")


def audit_project_files(project_root: Path, report: Report) -> None:
    openspec_root = project_root / "openspec"
    required = (
        openspec_root / "config.yaml",
        openspec_root / "project-context.md",
        openspec_root / "schemas" / "governed-standard" / "schema.yaml",
        openspec_root / "schemas" / "governed-rapid" / "schema.yaml",
    )
    for path in required:
        if not path.is_file():
            report.error(f"project: required governance file is missing: {path}")

    context = openspec_root / "project-context.md"
    if context.is_file():
        try:
            text = context.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            report.error("project: project-context.md is not valid UTF-8.")
        else:
            if "TODO" in text or "<!--" in text:
                report.warn("project: project-context.md still contains template placeholders.")
            if len(text.encode("utf-8")) > 24 * 1024:
                report.warn("project: project-context.md exceeds the recommended 24 KiB budget.")
            find_secrets("project", "project-context.md", text, report)

    config = openspec_root / "config.yaml"
    if config.is_file():
        text = config.read_text(encoding="utf-8")
        if not re.search(r"(?m)^schema:\s*governed-standard\s*$", text):
            report.error("project: config.yaml must default to governed-standard.")
        if "openspec/project-context.md" not in text:
            report.error("project: config.yaml must route agents to project-context.md.")

    for schema in EXPECTED_SCHEMAS:
        schema_file = openspec_root / "schemas" / schema / "schema.yaml"
        if schema_file.is_file():
            text = schema_file.read_text(encoding="utf-8")
            if not re.search(rf"(?m)^name:\s*{re.escape(schema)}\s*$", text):
                report.error(f"project: schema directory {schema!r} has the wrong name.")

    obsolete_manifest = openspec_root / "governance-context.json"
    if obsolete_manifest.exists():
        report.warn(
            "project: governance-context.json is obsolete; remove it to avoid a duplicate authority."
        )


def audit_checkpoint(
    project_root: Path,
    change: str,
    fields: dict[str, str],
    verification: dict[str, str],
    declared_dirty: set[str],
    git_state: GitState | None,
    report: Report,
    compare_current_branch: bool,
) -> None:
    if git_state is None:
        return
    branch = fields.get("branch", "")
    if compare_current_branch and branch != git_state.branch:
        report.error(
            f"{change}: handoff branch {branch!r} does not match current branch {git_state.branch!r}."
        )
    if compare_current_branch and declared_dirty != set(git_state.dirty_paths):
        report.error(
            f"{change}: Uncommitted Paths disagree with Git; declared "
            f"{sorted(declared_dirty)}, actual {sorted(git_state.dirty_paths)}."
        )

    checkpoint = fields.get("checkpoint commit", "")
    resolved = resolve_commit(project_root, checkpoint)
    if not resolved:
        report.error(f"{change}: Checkpoint commit {checkpoint!r} is not a Git commit.")
        return
    if compare_current_branch and not commit_is_ancestor(project_root, resolved, git_state.head):
        report.error(f"{change}: Checkpoint commit is not an ancestor of HEAD.")
        return

    checkpoint_time = parse_timestamp(
        fields.get("checkpoint time", ""), "Checkpoint time", change, report
    )
    try:
        commit_time_text = git_output(project_root, ["show", "-s", "--format=%cI", resolved])
        commit_time = datetime.fromisoformat(commit_time_text.replace("Z", "+00:00"))
        if checkpoint_time and checkpoint_time < commit_time:
            report.error(f"{change}: Checkpoint time predates the checkpoint commit.")
    except (AuditError, ValueError):
        report.error(f"{change}: unable to verify checkpoint commit time.")

    status = fields.get("status", "")
    if status in TERMINAL_WORK_STATUSES:
        allowed = {
            f"openspec/changes/{change}/handoff.md",
            "openspec/project-context.md",
        }
        if compare_current_branch:
            post_checkpoint = paths_after_commit(project_root, resolved, git_state.head)
            stale_paths = sorted(path for path in post_checkpoint if path not in allowed)
            if stale_paths:
                report.error(
                    f"{change}: implementation changed after checkpoint verification: {stale_paths}."
                )
            dirty_implementation = sorted(
                path
                for path in git_state.dirty_paths
                if path not in allowed and not path.endswith(ALLOWED_POST_CHECKPOINT_SUFFIXES)
            )
            if dirty_implementation:
                report.error(
                    f"{change}: terminal status has unverified implementation paths: "
                    f"{dirty_implementation}."
                )

        verification_commit = verification.get("verification commit", "")
        resolved_verification = resolve_commit(project_root, verification_commit)
        if not resolved_verification or resolved_verification != resolved:
            report.error(
                f"{change}: Verification commit must resolve to the checkpoint commit."
            )


def audit_change(
    project_root: Path,
    executable: str,
    change: str,
    report: Report,
    git_state: GitState | None,
    compare_current_branch: bool,
    expected_owner: str | None,
) -> dict[str, str] | None:
    change_root = project_root / "openspec" / "changes" / change
    if not change_root.is_dir():
        report.error(f"{change}: active change directory is missing.")
        return None

    try:
        status_payload, _ = run_json(
            executable, ["status", "--change", change, "--json"], project_root
        )
    except AuditError as error:
        report.error(f"{change}: {error}")
        return None
    if not isinstance(status_payload, dict):
        report.error(f"{change}: status JSON must be an object.")
        return None
    if status_payload.get("changeName") not in {None, change}:
        report.error(f"{change}: status JSON identifies a different change.")
    schema = status_payload.get("schemaName")
    if schema not in EXPECTED_SCHEMAS:
        report.error(f"{change}: unsupported governance schema {schema!r}.")
    planning_complete = status_payload.get(
        "isPlanningComplete", status_payload.get("isComplete")
    )
    if planning_complete is not True:
        report.error(
            f"{change}: planning artifacts are not complete according to OpenSpec status."
        )

    metadata = read_text(change_root / ".openspec.yaml", change, report)
    proposal = read_text(change_root / "proposal.md", change, report)
    tasks = read_text(change_root / "tasks.md", change, report)
    handoff = read_text(change_root / "handoff.md", change, report)
    for name, text in (("proposal.md", proposal), ("tasks.md", tasks), ("handoff.md", handoff)):
        if text is not None:
            find_secrets(change, name, text, report)

    if schema == "governed-rapid" and metadata is not None:
        if not re.search(r"(?m)^skip_specs:\s*true\s*$", metadata):
            report.error(f"{change}: governed-rapid metadata must set skip_specs: true.")
        specs_root = change_root / "specs"
        if specs_root.is_dir() and any(specs_root.rglob("*.md")):
            report.error(f"{change}: governed-rapid must not contain delta specs.")
    if schema == "governed-standard":
        design = read_text(change_root / "design.md", change, report)
        specs_root = change_root / "specs"
        if not specs_root.is_dir() or not any(specs_root.rglob("*.md")):
            report.error(f"{change}: governed-standard requires at least one delta spec.")
        if design is not None:
            find_secrets(change, "design.md", design, report)
    if proposal is not None and schema in EXPECTED_SCHEMAS:
        expected_profile = "rapid" if schema == "governed-rapid" else "standard"
        if not re.search(
            rf"(?im)^\s*-\s*Profile:\s*`?{expected_profile}`?\s*$", proposal
        ):
            report.error(f"{change}: proposal risk profile does not match schema {schema!r}.")

    if handoff is None or tasks is None:
        return None
    if "## Changed Files" in handoff or "## Notes for the Next Session" in handoff:
        report.error(
            f"{change}: handoff contains deprecated diary sections; keep only current evidence."
        )
    fields = parse_bullets(handoff, change, report)
    values = {key: required_value(fields, key, change, report) for key in SNAPSHOT_KEYS}
    verification = {
        key: required_value(fields, key, change, report) for key in VERIFICATION_KEYS
    }
    normalized = {key: value or "" for key, value in values.items()}
    normalized_verification = {key: value or "" for key, value in verification.items()}

    if normalized["change"] and normalized["change"] != change:
        report.error(f"{change}: handoff Change field does not match its directory.")
    status = normalized["status"]
    if status and status not in ALLOWED_STATUSES:
        report.error(f"{change}: unsupported handoff status {status!r}.")
    for identity_key in ("owner", "branch"):
        identity = normalized[identity_key].lower()
        if identity in {"none", "unknown", "unassigned", "n/a", "na"}:
            report.error(f"{change}: handoff {identity_key} must be explicitly assigned.")
    owner = normalized["owner"]
    if re.search(r",|\s+and\s+|\s*&\s*|\s*\+\s*", owner, re.IGNORECASE):
        report.error(f"{change}: handoff Owner must name exactly one writer.")
    if expected_owner and owner != expected_owner:
        report.error(
            f"{change}: ownership conflict; handoff owner is {owner!r}, caller is {expected_owner!r}."
        )

    _, task_ids, completed = validate_task_state(change, tasks, normalized, report)
    declared_dirty = parse_path_section(handoff, change, report)
    blockers_none = section_is_none(handoff, "Blockers and Deviations")
    if blockers_none is None:
        report.error(f"{change}: handoff lacks Blockers and Deviations section.")
    elif status == "blocked" and blockers_none:
        report.error(f"{change}: blocked status must name the blocker or deviation.")
    elif status in TERMINAL_WORK_STATUSES and not blockers_none:
        report.error(f"{change}: terminal status cannot retain blockers or deviations.")

    result = normalized_verification["result"].lower()
    if result not in {"not-run", "pass", "fail"}:
        report.error(f"{change}: verification Result must be not-run, pass, or fail.")
    if status in TERMINAL_WORK_STATUSES:
        if result != "pass":
            report.error(f"{change}: terminal status requires verification Result pass.")
        if normalized_verification["exit code"] != "0":
            report.error(f"{change}: terminal status requires verification Exit code 0.")
        verified_at = parse_timestamp(
            normalized_verification["verified at"], "Verified at", change, report
        )
        checkpoint_time = parse_timestamp(
            normalized["checkpoint time"], "Checkpoint time", change, report
        )
        if verified_at and checkpoint_time and verified_at < checkpoint_time:
            report.error(f"{change}: verification evidence predates the checkpoint.")
    elif result == "fail" and status != "blocked":
        report.warn(f"{change}: failed latest verification should normally use blocked status.")

    if status == "awaiting-merge" and "archive after merge" not in normalized[
        "exact next action"
    ].lower():
        report.error(f"{change}: awaiting-merge must state 'archive after merge' next.")
    if status == "awaiting-archive" and "archive" not in normalized["exact next action"].lower():
        report.error(f"{change}: awaiting-archive must name the archive action next.")

    audit_checkpoint(
        project_root,
        change,
        normalized,
        normalized_verification,
        declared_dirty,
        git_state,
        report,
        compare_current_branch,
    )

    if planning_complete is True:
        try:
            instructions_payload, _ = run_json(
                executable,
                ["instructions", "apply", "--change", change, "--json"],
                project_root,
            )
            validate_instruction_state(
                change,
                instructions_payload,
                len(task_ids),
                len(completed),
                status in TERMINAL_WORK_STATUSES,
                report,
            )
        except AuditError as error:
            report.error(f"{change}: unable to consume apply instructions: {error}")

    try:
        validate_payload, code = run_json(
            executable,
            ["validate", change, "--strict", "--json"],
            project_root,
            allow_nonzero=True,
        )
        validate_open_spec_result(change, validate_payload, code, report)
    except AuditError as error:
        report.error(f"{change}: unable to run strict validation: {error}")

    if status in TERMINAL_WORK_STATUSES:
        try:
            archive_payload, _ = run_json(
                executable,
                ["instructions", "archive", "--change", change, "--json"],
                project_root,
            )
            if not isinstance(archive_payload, dict) or archive_payload.get("changeName") != change:
                report.error(f"{change}: archive instructions JSON has an invalid identity.")
        except AuditError as error:
            report.error(f"{change}: unable to consume archive instructions: {error}")
    return normalized


def audit_ownership(
    handoffs: dict[str, dict[str, str]], git_state: GitState | None, report: Report
) -> None:
    active_by_branch: dict[str, list[str]] = {}
    branch_matches: list[str] = []
    for change, fields in handoffs.items():
        branch = fields.get("branch")
        if branch:
            active_by_branch.setdefault(branch, []).append(change)
            if git_state and branch == git_state.branch:
                branch_matches.append(change)
    for branch, changes in sorted(active_by_branch.items()):
        if len(changes) > 1:
            report.error(
                f"ownership: branch {branch!r} has multiple active changes: "
                + ", ".join(sorted(changes))
            )
    report.facts["branchMatches"] = sorted(branch_matches)
    if len(branch_matches) == 1:
        report.facts["resolvedChange"] = branch_matches[0]
    elif len(branch_matches) > 1:
        report.error("selection: multiple active changes match the current branch; choose explicitly.")
    elif len(handoffs) == 1:
        report.facts["resolvedChange"] = next(iter(handoffs))
    elif len(handoffs) > 1:
        report.facts["selectionRequired"] = True


def render_human(payload: dict[str, Any]) -> str:
    lines = ["PASS" if payload["ok"] else "FAIL"]
    lines.append(f"Project: {payload['projectRoot']}")
    lines.append("Changes: " + (", ".join(payload["changes"]) or "none"))
    for error in payload["errors"]:
        lines.append(f"ERROR: {error}")
    for warning in payload["warnings"]:
        lines.append(f"WARNING: {warning}")
    if payload["ok"]:
        lines.append("OpenSpec context governance audit passed.")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    project_root = args.project_root.expanduser().resolve()
    report = Report(project_root=str(project_root))
    try:
        if not project_root.is_dir():
            raise AuditError(f"Project root is not a directory: {project_root}")
        executable = resolve_executable(args.openspec_bin)
        version = detect_version(executable, project_root)
        report.facts["openspecVersion"] = version
        audit_project_files(project_root, report)
        git_state = inspect_git(project_root, report)

        list_payload, _ = run_json(executable, ["list", "--json"], project_root)
        active = active_change_names(list_payload)
        if args.change:
            if not CHANGE_ID_RE.fullmatch(args.change):
                raise AuditError(f"Invalid change ID: {args.change!r}")
            if args.change not in active:
                report.error(f"{args.change}: change is not active according to OpenSpec list.")
            selected = [args.change]
        else:
            selected = active
        report.changes = selected

        handoffs: dict[str, dict[str, str]] = {}
        for change in selected:
            fields = audit_change(
                project_root,
                executable,
                change,
                report,
                git_state,
                compare_current_branch=bool(args.change),
                expected_owner=args.owner if args.change else None,
            )
            if fields:
                handoffs[change] = fields
        audit_ownership(handoffs, git_state, report)
    except AuditError as error:
        report.error(str(error))

    payload = report.payload(args.strict)
    print(json.dumps(payload, indent=2) if args.json_output else render_human(payload))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
