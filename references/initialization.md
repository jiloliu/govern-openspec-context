# Initialization

Use this workflow only for new OpenSpec adoption. Do not migrate or overwrite an existing
`openspec/` setup, `DESIGN.md`, `ROADMAP.md`, `STATE.md`, or another governance system.

## Prerequisites

- A project directory that is or will become a Git repository.
- OpenSpec CLI major version 1 available on `PATH`.
- Authorization to add project-local OpenSpec and agent instruction files.

Resolve this skill directory and preview first:

```bash
python3 <skill-dir>/scripts/init_openspec_context.py --project-root <repo>
```

Preview validates prerequisites, reports the WorkBuddy/CodeBuddy paths that OpenSpec will
manage, and prints the `AGENTS.md` block without changing the project. Apply only after
reviewing existing conventions:

```bash
python3 <skill-dir>/scripts/init_openspec_context.py \
  --project-root <repo> --apply
```

Apply runs official OpenSpec initialization with the native `spec-driven` workflow,
uses OpenSpec's `codebuddy` adapter by default, creates `openspec/project-context.md`, and
prints but does not edit `AGENTS.md`. It does not install OpenSpec, create custom schemas,
or add a task-progress authority.

To initialize for another supported OpenSpec tool explicitly, pass its tool ID, for example
`--tools codex`. The preview reports the selected tools and known generated paths without
changing the project.

Merge the printed block into the applicable `AGENTS.md` with an available file-editing
mechanism. Preserve unrelated rules and resolve conflicts explicitly. Fill project context
from verified repository facts, then run a normal OpenSpec validation before starting
governed work.

If generated OpenSpec skills are missing or stale, use the installed CLI's documented
update/profile workflow. Do not hand-write copies of generated action skills.

## Context quality

Use `project-context.md` as a routing map, not a substitute for specs, ADRs, source code,
or repository documentation. Include verified stable facts and link to authoritative
detail. Exclude task progress, conversation summaries, speculative decisions, generated
file inventories, large code samples, complete change history, logs, secrets, and
information already authoritative elsewhere.
