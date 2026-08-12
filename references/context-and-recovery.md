# Context and Recovery

Use this reference after conversation compaction, at the start of a new session that
must resume work, or when a task asks why the project behaves as it does.

## Authority order

Resolve conflicts in this order:

1. system, user, and applicable `AGENTS.md` instructions;
2. accepted main specs under `openspec/specs/`;
3. the selected change proposal, delta specs, and design;
4. change tasks;
5. stable project context and linked ADRs;
6. code, diffs, commits, and fresh tests as evidence of current implementation.

Do not rewrite accepted intent merely because the implementation drifted.

## Recover an active change

Use documented JSON surfaces for automated decisions. Enumerate changes with
`openspec list --json`, then select an explicit valid ID or the only active change. With
multiple changes, inspect the current branch, proposal scope, working diff, and recent
relevant commits. Select only when exactly one candidate remains; otherwise ask the user
for the change ID.

After selection:

1. Read `.openspec.yaml`, proposal, relevant delta and main specs, design, and tasks.
2. Inspect `git status --short`, relevant staged and unstaged diffs, and recent commits.
3. Map every checked task to concrete code or documentation evidence.
4. Run focused checks needed to establish current behavior.
5. Check implemented-but-unchecked tasks only after evidence supports them. Uncheck tasks
   whose implementation or verification no longer satisfies the artifact.
6. Continue from the first dependency-ready incomplete task.

Do not infer progress from recency alone. Do not add a recovery summary or checkpoint
file. `tasks.md`, repository state, and current verification are sufficient evidence.

## Maintain project context

Keep `openspec/project-context.md` compact and stable. Record project purpose and scope,
architecture and dependency direction, public contracts and invariants, verified build
and test commands, durable constraints, delivery policy, and routes to authoritative
specs, ADRs, and detailed documentation.

Exclude current task progress, chat summaries, change inventories, full historical
timelines, speculative decisions, logs, secrets, and details already authoritative
elsewhere. Update it only when stable facts or routing change.

Use the repository's ADR convention for durable architectural decisions. If none exists,
place new ADRs under `docs/adr/` and link only the important entries from project context.

## Look up history on demand

Prefer current facts over historical narration:

1. Read relevant accepted specs and project context.
2. Read linked ADRs for architectural rationale.
3. Search relevant archived OpenSpec changes when a behavior or contract change needs
   provenance.
4. Use focused Git log, blame, and commit inspection only when the preceding sources do
   not answer the question.

Never load every archive or the full Git history at startup.
