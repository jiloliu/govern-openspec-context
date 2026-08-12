# Initialization

Use this workflow only for new OpenSpec adoption. It intentionally does not migrate
`DESIGN.md`, `ROADMAP.md`, `STATE.md`, or another governance system.

## Prerequisites

- A Git repository or new project directory that will be placed under Git before the
  strict checker is used. The initializer never runs `git init` for the user.
- Node.js and OpenSpec CLI major version 1 available on `PATH`.
- Authorization to add project-local OpenSpec and agent instruction files.

## Initialize

Resolve this skill directory and preview first:

```bash
python3 <skill-dir>/scripts/init_openspec_context.py \
  --project-root <repo>
```

The preview checks the CLI, reports planned paths, and prints the `AGENTS.md` block.
Apply only after inspecting existing repository conventions:

```bash
python3 <skill-dir>/scripts/init_openspec_context.py \
  --project-root <repo> --apply
```

The initializer runs official OpenSpec initialization when needed, installs the
`governed-standard` and `governed-rapid` schemas without overwriting existing files,
creates the project-context template, and prints (but does not edit) the `AGENTS.md`
block. It does not create another workflow manifest or progress authority.

Merge the printed block into the applicable `AGENTS.md` using `apply_patch`. Preserve
unrelated rules and resolve conflicts explicitly. Then fill project context with
verified facts and validate:

```bash
python3 <skill-dir>/scripts/check_openspec_context.py \
  --project-root <repo> --all --strict
```

If OpenSpec generated skills are missing for Codex, use the installed CLI's documented
update/profile workflow. Do not hand-write copies of generated OpenSpec skills.

## Context quality

Keep `openspec/project-context.md` short enough to read at every startup. It should
route an agent to authoritative sources and stable commands, not reproduce them.

Include verified facts about:

- product purpose and bounded scope;
- architecture and module ownership;
- public contracts and invariants;
- build, test, lint, and verification commands;
- authoritative documentation locations;
- delivery model and archive timing;
- known operational constraints that affect development.

Exclude task progress, conversation summaries, speculative decisions, generated file
inventories, large code samples, logs, secrets, and details already authoritative in
main specs or repository documentation.
