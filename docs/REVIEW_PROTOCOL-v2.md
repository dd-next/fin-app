# FinApp v2 — reviewer-subagent protocol

This protocol is mandatory for every implementation phase in
[`BUILD_PLAN-v2.md`](BUILD_PLAN-v2.md). It exists so that the agent writing a
change is not the only agent deciding whether the change meets the release
requirements.

## Unit of review

A logical block is one bounded change from this sequence:

```text
schema/migration → domain service → API → UI → tests → documentation
```

Split a broad item further whenever it combines unrelated financial behavior.
For example, manual-rate precedence and account-period replay are separate
domain blocks even if they happen in the same phase.

## Required loop

For **every written logical block**, the primary agent must do all of the
following before continuing to the next block:

1. Run targeted tests for the changed behavior.
2. Create a fresh, separate reviewer sub-agent with a read-only task.
3. Give the reviewer the phase, block name, the task's named specification and
   applicable sections of `specs/FinnApp-v2.md`, files/diff to inspect, exact
   test commands already run, and the invariants that can fail.
4. The reviewer inspects the diff and may run read-only checks or tests. It
   must not edit code, docs, migrations, or test fixtures.
5. The primary agent fixes every finding. If a finding changes logic or test
   coverage, send the resulting limited diff to a fresh reviewer agent.
6. The reviewer returns findings and remains read-only. The implementer copies
   the response verbatim into the task file together with reviewer
   vendor/model, exact reviewed base/head or working-tree manifest, resolution,
   and test evidence. `PROGRESS.md` contains only the phase summary and links
   to those task records.

Do not reuse the implementation agent as the reviewer. A reviewer is an
independent critic, not a co-author.

Prefer the other agent vendor. When it is unavailable, a fresh independent
reviewer from the same vendor is an allowed fallback, but the task file must
say that the cross-vendor review was unavailable.

For an uncommitted review, the manifest includes `git status --short`, the
tracked diff, and direct inspection of every untracked file in scope. A clean
`git diff` alone is never evidence that untracked work was reviewed.

## Reviewer checklist

The reviewer must assess the block against the applicable requirements, with
special attention to:

- Decimal-only money/rates, explicit asset precision, and `ROUND_HALF_UP`;
- posted-ledger derivation, soft void behavior, root/child transaction effects,
  and no accidental hard deletion;
- workspace and account permission isolation, including shared-account
  redaction and owner-private periods/Plan data;
- account-period snapshot boundary and signed-leg replay rules;
- API validation, stale/reload behavior, error states, and backward route
  removal where required;
- edge cases, migrations from a clean database, and sufficient regression
  tests;
- English UI copy, responsive/accessibility impact, and absence of unrelated
  changes.

Findings use these priorities:

| Priority | Meaning | Required action |
| --- | --- | --- |
| P0 | Data loss, security/permission leak, or financial corruption | Fix and re-review. |
| P1 | Requirement or core behavior is wrong/missing | Fix and re-review. |
| P2 | Edge case, regression risk, or missing meaningful test | Fix and re-review unless the user explicitly accepts the risk. |
| P3 | Small clarity or maintainability concern | Fix when reasonable; record any deferral. |

## Phase commit gate

The repository owner may create `v2 phase N: <short summary>` only when all of
these are true; an implementer or reviewer cannot accept or close a phase:

1. Every block in the phase has a recorded reviewer-subagent pass and all P0–P2
   findings are closed.
2. Targeted tests, complete `pytest`, `node --check app/static/app.js`, and
   `git diff --check` pass.
3. The phase-specific migration/browser/Docker checks in the build plan pass.
4. Task files contain detailed work/reviewer/test evidence and
   `docs/PROGRESS.md` contains a concise phase summary linking to them.
5. The worktree contains no unrelated user changes in the commit.

If blocked, record the blocker, attempted fixes, reviewer evidence, and clean
runnable checkpoint in the task file. Update `docs/PROGRESS.md` only if the
release state changed; stop rather than skipping a phase.

## Reviewer task template

```text
Read-only review for FinApp Phase <N>, task <T-NNN>, block <name>.

Do not edit files. Inspect only this bounded diff: <base/head or working-tree
manifest, including untracked files>.
Check it against the task's named spec <path/sections>, applicable
docs/specs/FinnApp-v2.md sections <...>, and these invariants: <financial,
permission, migration, UI invariants>.

Targeted tests already run: <commands and outcome>.
Run any additional read-only checks you need. Return findings ordered P0–P3,
with file/line evidence, missing tests, and an explicit “no findings” if clean.
```
