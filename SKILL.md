---
name: govern-openspec-context
description: Orchestrate OpenSpec changes with durable project context and cross-session handoffs. Use when Codex needs to initialize a new OpenSpec-governed project, classify and drive a requested code change through planning, implementation, verification, and archive, resume an active change after compaction or in a new session, or coordinate parallel change folders with one writer per change. Do not use for repositories that are not adopting OpenSpec or for migrating legacy governance files.
---

# Govern OpenSpec Context

Use OpenSpec as the change and specification engine. Add only the missing governance
layer: risk-based orchestration, durable project context, a mutable handoff per active
change, and one-writer ownership. Do not duplicate OpenSpec artifacts in a second
roadmap or design system.

Honor applicable `AGENTS.md` files and the user's requested scope first. This skill
does not authorize implementation when the user asked only for analysis or planning.

## Select the operation

- For a new project, read `references/initialization.md`, preview the initializer,
  apply it, and merge the printed block into the applicable `AGENTS.md`.
- For a new change, perform startup, classify risk, and drive the lifecycle below.
- For resumption, read and reconcile the active change before doing new work.
- For verification, archive, ownership questions, or exceptions, read
  `references/orchestration-contract.md` completely before acting.

## Perform startup and reconciliation

1. Locate the repository root and read every applicable `AGENTS.md`.
2. Inspect `git status --short`, the current branch, and relevant existing diffs.
   Preserve work of unknown ownership.
3. Require OpenSpec CLI major version 1 and an initialized `openspec/` directory.
   Use only documented JSON surfaces for automation, never parsed display output.
4. Read `openspec/project-context.md` completely. Treat it as a compact routing map,
   not a place for transient task progress.
5. Run `openspec list --json`. Resolve the target change from an explicit ID, the
   current branch or worktree, and handoff ownership. If more than one candidate
   remains, ask the user instead of guessing.
6. For a resolved change, read its `.openspec.yaml`, proposal, relevant delta specs,
   design, tasks, and `handoff.md`. Read only affected main specs by default.
7. Reconcile those records with code, diffs, task checkboxes, and fresh verification.
   Repair stale handoff facts before continuing; do not rewrite intent to match an
   accidental implementation.

When the target is uncertain, audit all active changes before selecting one:

```bash
python3 <skill-dir>/scripts/check_openspec_context.py \
  --project-root <repo> --all --strict --json
```

After the target is resolved, audit its branch, owner, tasks, verification, and Git
evidence directly:

```bash
python3 <skill-dir>/scripts/check_openspec_context.py \
  --project-root <repo> --change <change-id> --owner <writer-id> --strict --json
```

## Load OpenSpec action skills automatically

The user does not need to invoke each OpenSpec skill. The generated skills are action
contracts, not separate user-facing gates inside this orchestrated workflow. Before an
OpenSpec action:

1. Locate the generated action skill in project skill roots, preferring the current
   cross-agent `.agents/skills/openspec-*` files and accepting legacy tool-specific
   roots such as `.codex/skills/`. Match by frontmatter name and intent, not by
   assumed punctuation. Common aliases include `openspec-explore`,
   `openspec-propose`, `openspec-apply` or `openspec-apply-change`,
   `openspec-verify` or `openspec-verify-change`, and `openspec-archive` or
   `openspec-archive-change`.
2. Read that `SKILL.md` completely immediately before the action. Follow its CLI,
   artifact, validation, and safety mechanics. Do not start it as a separately selected
   top-level workflow: standalone prompts to stop and ask the user to invoke the next
   action are replaced by this skill's lifecycle and approval policy. This skill owns
   sequencing; the generated skill owns the mechanics within its action boundary.
3. If an optional action skill is absent, use the CLI contract in
   `references/orchestration-contract.md`. Never invent undocumented CLI flags.
4. If required generated skills are absent or stale, run the documented OpenSpec
   update flow when repository mutation is authorized. Otherwise report setup needed.

## Classify change risk

Choose the highest matching profile. Ambiguity selects `standard`.

- `direct`: obvious typo, formatting, comment, or mechanically safe single-point
  correction with no behavior, contract, data, dependency, or operational effect.
- `rapid`: bounded internal refactor, tooling, tests, or documentation change with no
  user-visible behavior, public contract, migration, security, concurrency, or broad
  cross-module effect.
- `standard`: user-visible behavior; API, schema, protocol, data, security,
  concurrency, migration, dependency, architecture, or cross-module change; uncertain
  requirements; or work likely to cross sessions.

Record the profile and one-sentence rationale in the proposal. Escalate the profile
whenever evidence reveals greater risk; never silently downgrade it.

## Drive the lifecycle

### Direct

Implement within the user's authorization, run proportionate checks, and report the
result. Do not create a ceremonial OpenSpec change or handoff. Promote to `rapid` if
the edit stops being trivial.

### Rapid

1. Load the propose action and create a change with schema `governed-rapid`.
2. Ensure change metadata sets `skip_specs: true`.
3. Produce `proposal.md`, `tasks.md`, and initial `handoff.md`; validate strictly.
4. For an implementation request, the original request authorizes apply. Continue
   without a second planning approval unless a pause condition occurs.
5. Load apply, execute tasks, checkpoint handoff, then verify and close out.

### Standard

1. Load explore only when requirements or repository behavior need investigation.
2. Load propose and create a change with schema `governed-standard`.
3. Produce proposal, delta specs, design, tasks, and initial handoff; validate strictly.
4. Present the planning result and request one user confirmation before apply. After
   confirmation, continue through apply and verification without asking the user to
   invoke intermediate skills.
5. Ask again only for a pause condition or a material deviation from approved intent.

## Checkpoint and hand off

- One active change has exactly one writer and one implementation branch/worktree.
  An implementation branch/worktree may be claimed by only one active change. Record
  both claims in `handoff.md`. Multiple changes may run in parallel only on separate,
  non-overlapping branches/worktrees; split overlapping work instead of sharing either
  a change or an implementation branch.
- Update handoff at task boundaries, before a long-running or risky action, before
  yielding across sessions, and after verification. Keep it factual and compact.
- Commit completed implementation before terminal verification. Record the real
  checkpoint commit and time; after running checks, record one structured result,
  command, exit code, verification time, and the same verification commit.
- Record current task, last completed task, only necessary uncommitted paths, blockers
  or deviations, and one exact next action. Do not add diary or chat-summary sections.
- Never put secrets, tokens, credentials, or unredacted sensitive output in artifacts.
- If the handoff conflicts with repository evidence, preserve the intended change and
  correct the stale progress record.

## Verify and close out

Prefer the generated verify skill. If it is not installed, perform the equivalent:

1. Run `openspec validate <change-id> --strict --json`.
2. Compare implementation and tests with every applicable scenario and design
   decision; inspect the actual diff.
3. Run repository-required and change-specific checks, recording exact outcomes.
4. Require every task checkbox complete and no unresolved blocker before declaring
   the change verified.
5. Synchronize stable architecture, commands, constraints, and document routes to
   `openspec/project-context.md` or an ADR before closeout when they changed.
6. Update handoff last, then run the bundled checker in strict mode. A terminal status
   requires `Result: pass`, exit code `0`, and Git evidence that implementation did not
   change after verification.

For direct-to-main or explicitly local work, load archive after successful verification
and archive automatically. For branch or PR work, default to archive after merge:
leave status `awaiting-merge`, record `archive after merge` as the exact next action,
and do not merge delta specs into main specs prematurely. Archive on the current branch
before merge only when the user explicitly requests that policy.

After archive, confirm the change and handoff moved together and that standard delta
specs updated main specs. Do not copy change history into project context.

## Pause only when necessary

Pause for unresolved product ambiguity, material scope or public-contract change,
destructive/external/production authorization, ambiguous selection among active
changes, ownership conflict, or a validation/test failure that cannot be resolved
safely in scope. Record the blocker and exact decision needed in handoff first only
after the target change is unambiguous and the current writer owns it. Selection or
ownership ambiguity is read-only: do not mutate any candidate handoff before the user
or current owners resolve it.

Fix minor implementation deviations and update artifacts when they preserve approved
intent. Material behavior, scope, API, data, security, or migration changes require
renewed user confirmation.
