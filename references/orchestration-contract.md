# Orchestration Contract

This reference defines deterministic behavior when composing generated OpenSpec skills
or when an optional action skill is unavailable.

## Authority order

Resolve conflicts in this order:

1. system and user instructions;
2. applicable repository `AGENTS.md` files;
3. accepted main specs under `openspec/specs/`;
4. the selected change proposal, delta specs, and design;
5. tasks and handoff progress;
6. this governance skill.

Code and fresh tests are evidence of current implementation, not automatic authority
to rewrite accepted requirements.

## JSON-only automation

Use documented JSON commands for decisions made by scripts or agents:

```bash
openspec list --json
openspec show <change-id> --json
openspec status --change <change-id> --json
openspec instructions <artifact-or-action> --change <change-id> --json
openspec validate <change-id> --strict --json
```

Human-readable output may be shown to the user but must not be parsed to infer state.
Treat a nonzero exit and structured errors as failure. OpenSpec status describes
artifact readiness; task checkbox completion and verification remain separate checks.

## Generated-skill composition

Search applicable project skill roots first. Current OpenSpec emits cross-agent skills
under `.agents/skills/openspec-*/SKILL.md`; accept legacy tool-specific roots such as
`.codex/skills/`. Support generated-name changes by matching frontmatter and described
intent.

Load only the action needed now. Read its complete instructions before acting and use
its action-local mechanics. When this governance skill is the selected top-level
workflow, do not separately trigger the generated action or inherit its standalone
"ask the user to invoke the next action" transition prompt; use the approval policy
below. Preserve every action-local validation, scope, state, and safety guardrail. Do
not copy detailed CLI procedures here because generated behavior changes with OpenSpec.

Risk classification is an explicit governance schema selection. While consuming the
generated propose mechanics, pass `--schema governed-rapid` or
`--schema governed-standard` as selected here even when the user did not spell out a
schema name; do not fall back to the repository default for a classified change.

Core installations normally provide propose, explore, apply, update/sync, and archive.
Expanded profiles may add new, continue, fast-forward, verify, bulk archive, and
onboarding. Missing expanded actions are not an error when the equivalent verification
or sequencing contract is supplied here.

## Change selection

Use an explicit user-supplied change ID when valid. Otherwise:

1. enumerate active changes through `openspec list --json`;
2. compare their handoff branch/worktree with the current repository state;
3. compare proposal scope with files already changed;
4. select only when exactly one candidate remains.

Never select merely because a change was most recently modified. If multiple changes
remain plausible, pause and request the ID.

Use the bundled checker with `--all --strict --json` while selection is unresolved.
After resolving one change, use `--change <change-id> --owner <writer-id> --strict
--json` before implementation. Selection diagnostics are read-only.

## One-writer ownership

Each active change has one owner identity and one implementation branch or worktree.
Each implementation branch/worktree is exclusive to one active change; two active
changes claiming it are an ownership conflict even when they name the same owner. A
writer must not edit a change owned by another active writer. Read-only review and
validation are allowed. To parallelize, create separate non-overlapping changes on
separate branches/worktrees and record their dependencies; if overlap is unavoidable,
serialize ownership transfer and update handoff before the next writer begins.

Do not record an ambiguity blocker in a candidate handoff until target selection and
write ownership are resolved. Otherwise the attempted record would itself choose and
mutate a change without authority.

## Handoff state

Use these status values:

- `planned`: artifacts ready, implementation not started;
- `in-progress`: at least one task started and work remains;
- `blocked`: a named decision, failure, or authorization prevents progress;
- `verified`: implementation and change checks passed locally;
- `awaiting-merge`: verified branch/PR should archive only after merge;
- `awaiting-archive`: verified direct-to-main work is ready to archive.

`Current task` names an incomplete task while planned or in progress and is `none` only
when blocked without an executable task, verified, or awaiting closeout. `Last completed
task` names the latest checked task. `Checkpoint commit` is a real commit on the current
branch and `Checkpoint time` cannot predate it. `Exact next action` must be executable or
name the exact decision needed.

Use one structured latest-verification record: `Result` (`not-run`, `pass`, or `fail`),
`Command`, `Exit code`, `Verified at`, and `Verification commit`. Terminal states require
`pass`, exit code `0`, and a verification commit equal to the checkpoint. List every and
only current dirty path under `Uncommitted Paths`; terminal states may leave handoff and
an already-synchronized project-context update dirty, but no unverified implementation.

## Approval and deviation policy

The user's implementation request authorizes direct and rapid work unless their wording
limits the request to planning/review. Standard work pauses once after planning for
confirmation. That confirmation covers implementation and normal local verification.

Ask again only when actual work would materially change approved behavior, scope,
public API, persisted data, security posture, migration, rollout, or external state.
Correct ordinary coding details and artifact drift automatically when intent remains
unchanged, then record the deviation.

## Archive policy

Archive merges delta specs into the current truth, so timing follows the delivery
model. Direct-to-main changes may archive after verification. Branch/PR changes remain
active and `awaiting-merge` until merged unless the user explicitly chooses branch-
local archive. After merge, re-verify relevant evidence, synchronize stable project
context or ADRs, load the archive skill, and archive exactly that change.

Never archive with incomplete tasks, unresolved blockers, failing strict validation,
or ambiguous ownership. Do not use bulk archive when changes have overlapping deltas
unless the OpenSpec action resolves ordering explicitly.
