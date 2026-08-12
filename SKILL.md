---
name: govern-openspec-context
description: Keep durable project context and orchestrate important changes with OpenSpec. Use when Codex needs to initialize a new OpenSpec-governed project, load stable project background and constraints in a new or compacted session, classify and drive a non-trivial change through planning, implementation, verification, and archive, resume an active change from repository evidence, or trace relevant architecture decisions and change history. Do not use for repositories that are not adopting OpenSpec or for migrating legacy governance files.
---

# Govern OpenSpec Context

Use repository files as durable context and OpenSpec as the specification and change
engine. Do not create a handoff, roadmap, status ledger, ownership registry, verification
log, or second archive system.

Honor applicable `AGENTS.md` files and the user's requested scope first. This skill does
not authorize implementation when the user asked only for analysis or planning.

## Select the operation

- For new adoption, read `references/initialization.md`, preview the initializer, apply
  it when mutation is authorized, and merge the printed block into `AGENTS.md`.
- For a new change, load context, classify it as `direct` or `standard`, and follow the
  lifecycle below.
- For resumption after compaction or in a new session, read
  `references/context-and-recovery.md` completely before acting.
- For architecture history or the reason behind behavior, follow the history lookup
  order in that reference; do not preload every archive or Git commit.

## Load durable context

1. Locate the repository root and read every applicable `AGENTS.md`.
2. Require OpenSpec CLI major version 1 and an initialized `openspec/` directory.
3. Read `openspec/project-context.md` completely. Treat it as a compact routing map for
   stable facts, commands, constraints, specs, ADRs, and detailed documentation.
4. Inspect `git status --short`, the current branch, relevant diffs, and
   `openspec list --json`. Preserve work of unknown ownership.
5. Read only the accepted specs, active change artifacts, ADRs, and source files relevant
   to the request. Query archived changes and Git history only when current sources do
   not explain a relevant decision or behavior.

After conversation compaction, repeat the relevant reads and fresh verification. Do not
write a repository checkpoint merely because compaction occurred.

## Load OpenSpec action skills automatically

Before an OpenSpec action, locate the generated action skill in applicable project skill
roots, preferring `.agents/skills/openspec-*` and accepting legacy tool-specific roots
such as `.codex/skills/`. Match frontmatter name and intent rather than assuming exact
punctuation. Read that `SKILL.md` completely immediately before the action and follow its
action-local CLI, artifact, validation, and safety mechanics.

This skill owns sequencing, so replace standalone prompts to ask the user to invoke the
next action with the lifecycle and approval policy below. If required generated skills
are missing or stale, run the documented OpenSpec update flow when repository mutation
is authorized; otherwise report the setup needed. Never invent undocumented CLI flags.

## Classify the change

Choose the highest matching class. Ambiguity selects `standard`.

- `direct`: an obvious, local, mechanically safe correction with no user-visible
  behavior, public contract, data, dependency, architecture, security, concurrency,
  migration, operational, cross-module, or likely cross-session effect.
- `standard`: every other change, including uncertain requirements or work likely to
  continue after compaction or in a new session.

For `direct`, implement within the user's authorization and run proportionate checks.
Do not create a ceremonial OpenSpec change. Promote to `standard` when evidence reveals
greater scope or risk.

## Drive a standard change

1. Load explore only when requirements or repository behavior need investigation.
2. Load propose and use OpenSpec's native `spec-driven` workflow.
3. Produce proposal, delta specs, design, and dependency-ordered tasks; validate them
   strictly.
4. Present the planning result and request one confirmation before apply. The original
   request does not replace this confirmation for a standard change.
5. After confirmation, load apply, execute tasks, update checkboxes only when repository
   evidence supports completion, and continue through verification without asking the
   user to invoke intermediate skills.
6. Ask again only for a pause condition or a material deviation from approved intent.

## Resume from repository evidence

Resolve the change in this order: an explicit valid change ID; the only active change;
or exactly one change matching the current branch, proposal scope, and working diff. If
multiple candidates remain, ask the user instead of guessing.

Read the selected proposal, relevant delta and main specs, design, and tasks. Reconcile
task checkboxes with code, diffs, recent relevant commits, and fresh tests. A checkbox is
a completion claim, not proof: check it only after verification, and uncheck it when the
implementation or evidence no longer satisfies the task. Continue from the first
dependency-ready incomplete task.

## Verify and archive

1. Run `openspec validate <change-id> --strict --json`.
2. Compare implementation and tests with every applicable scenario and design decision;
   inspect the actual diff.
3. Run repository-required and change-specific checks using current code.
4. Require all tasks complete and no unresolved material deviation before declaring the
   change verified.
5. Synchronize changed stable architecture, commands, constraints, and document routes
   to `openspec/project-context.md` or an ADR before closeout.
6. For direct-to-main or explicitly local delivery, load archive after verification and
   archive. For branch or PR delivery, default to archive after merge unless the user
   explicitly requests branch-local archive.

After archive, confirm standard delta specs updated accepted specs. Do not copy archive
history or test logs into project context; rerun necessary checks when resuming later.

## Pause only when necessary

Pause for unresolved product ambiguity, material scope or public-contract change,
destructive/external/production authorization, ambiguous active-change selection, or a
validation/test failure that cannot be resolved safely in scope. Fix ordinary coding
details and artifact drift when they preserve approved intent. Material behavior, scope,
API, data, security, migration, or rollout changes require renewed confirmation.
