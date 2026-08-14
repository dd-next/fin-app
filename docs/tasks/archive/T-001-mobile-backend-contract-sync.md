---
id: T-001
title: Synchronize the mobile design and backend implementation contracts
status: done
size: M
spec: design/MOBILE-BACKEND-GAP-AUDIT.md
blocked-by: []
branch: task/T-001-mobile-backend-contract-sync
base-commit: 4600266
implementer: Codex
readiness-reviewed-by: not-applicable (owner-requested migration task)
readiness-reviewed-commit: not-applicable (task absent at integration base)
readiness-verdict: exception documented; final reviews clean, owner accepted 2026-08-09
---

## Goal

The repository has one executable workflow and a complete, owner-approved map
from the frozen mobile design to every backend change that must land before
mobile UI implementation starts.

This planning task predates the atomic-claim rule it introduces and is being
prepared on `finapp-v2-develop` at the owner's explicit request. No application
code or design asset is changed.

## Acceptance

- [x] Design authority names `Finapp Screen.dc.html` as the final source,
      `handoff/finapp-design-canvas.html` as the portable canvas, and labels
      earlier canvases/uploads as raw material.
- [x] Every backend capability required by the mobile design is classified as
      supported, missing, frontend-only, desktop-only, or a contract blocker.
- [x] Every missing backend contract has an ordered Phase 14 backlog row and
      Phase 15 is explicitly blocked until Phase 14 closes.
- [x] Desktop behavior is preserved where the mobile design has no equivalent
      and no desktop replacement specification exists.
- [x] Workflow evidence has one detailed home (the task file), while
      `PROGRESS.md` remains a concise state summary.
- [x] Task commits and the owner-only phase-closing commit have distinct roles;
      owner-only acceptance/archive is unambiguous.
- [x] A task may span sequential sessions but has one exact branch and one
      active implementer; initial claim, resume, readiness/base evidence,
      reviewer fallback, and untracked review rules are explicit.
- [x] `CLAUDE.md` is normalized to the documented `AGENTS.md` symlink and is
      included in this workflow task's declared scope.
- [x] T-002 cannot mutate `finapp.db` through its verification command and its
      acceptance criteria no longer contradict its Touches/Out-of-scope lists.
- [x] `uploads/` and raw duplicate design artifacts are excluded from the
      intended Git set without altering the source screen or handoff.
- [x] A separate read-only reviewer finds no unresolved P0–P2 issue in this
      documentation block.

## Touches

- `AGENTS.md`
- `CLAUDE.md` symlink normalization to `AGENTS.md`
- `.gitignore` only for design raw-material exclusions; preserve
  `OPS-RUNBOOK.md`
- `docs/README.md`, `docs/PROGRESS.md`, `docs/BUILD_PLAN-v2.md`,
  `docs/REVIEW_PROTOCOL-v2.md`
- `docs/BACKLOG.md`, `docs/tasks/`, `docs/design/DESIGN-NOTES.md`
- `docs/design/MOBILE-BACKEND-GAP-AUDIT.md`
- `docs/specs/ACCOUNT_PERIODS-v2.1.md`, `docs/decisions/ADR-0007-mobile-design-is-frozen-and-backend-first.md`
- `docs/design/Finnapp mobile specification/AGENTS.md` and written
  `spec/04-sheets.md` through `spec/08-acceptance.md`; no visual source change

## Out of scope

- Application code, migrations, database state, and automated application
  tests.
- Any visual source or token edit inside `docs/design/Finnapp mobile
  specification/`; written specs may record the owner's approved behavioral
  corrections and its nested operational `AGENTS.md` may align authority.
- External daily-rate integration and Owner transfer implementation; both are
  explicitly deferred and represented by disabled Phase 15 placeholders.
- Staging, committing, or pushing files.

## Verification

```bash
git status --short
git diff --check
git diff --cached --check
rg -n "PROGRESS.md|task file|phase-closing|read-only reviewer" \
  AGENTS.md docs/BUILD_PLAN-v2.md docs/REVIEW_PROTOCOL-v2.md docs/tasks/TEMPLATE.md
test -f docs/design/MOBILE-BACKEND-GAP-AUDIT.md
test -f "docs/design/Finnapp mobile specification/Finapp Screen.dc.html"
test -f "docs/design/Finnapp mobile specification/handoff/finapp-design-canvas.html"
git check-ignore -v "docs/design/Finnapp mobile specification/uploads/IMG_4740.PNG"
```

## Review

### Pass 1

- Reviewer task name/vendor: `/root/workflow_consistency_review`, Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed base/head or working-tree manifest: direct inspection of
  `AGENTS.md`, `docs/REVIEW_PROTOCOL-v2.md`, workflow sections of
  `docs/BUILD_PLAN-v2.md`, `docs/tasks/TEMPLATE.md`, T-001, T-002, and T-003,
  including untracked files from `git status --short`.
- Findings (verbatim, P0–P3):

  > P0: none.
  >
  > P1 — The phase-commit owner still contradicts the normalized workflow.
  > `AGENTS.md:72-75` says only the repository owner accepts the phase and
  > creates `v2 phase N`, and `docs/BUILD_PLAN-v2.md:26-28` says the same. But
  > `docs/REVIEW_PROTOCOL-v2.md:78-81` says “The primary agent may create” that
  > commit. An implementer following the review protocol can therefore perform
  > an owner-only action. Change the latter to an owner gate/owner action.
  >
  > P1 — The initial-claim rules make the advertised multi-session task flow
  > impossible. `AGENTS.md:84-86` explicitly permits several sequential
  > sessions, but every session is told to require `status: todo`
  > (`AGENTS.md:102-106`) and to stop if the task branch already exists
  > (`AGENTS.md:107-108`). After the first session/claim, the status is
  > `in-progress` and the branch necessarily exists (`AGENTS.md:109-111`), so a
  > legitimate resumed session must stop. Split startup into initial claim
  > (`todo`, branch absent) versus resume (`in-progress`, same
  > implementer/branch/base, branch present).
  >
  > P2 — Readiness review is required but not executable/reproducible yet.
  > `AGENTS.md:95` promises a reviewed task and `AGENTS.md:105-106` requires
  > readiness to have passed, while `docs/tasks/TEMPLATE.md:9-11` only provides
  > a free-text `readiness-reviewed-by` field. There is no owner/agent
  > responsibility, review checklist, reviewed revision/manifest, verdict, or
  > rule that populates `base-commit` before branch creation. T-001 demonstrates
  > the ambiguity with `readiness-reviewed-by: pending final documentation
  > review` (`docs/tasks/T-001-mobile-backend-contract-sync.md:9-11`):
  > implementation/final review and pre-code readiness review are being
  > conflated. Define the readiness evidence and transition from `backlog` to
  > `todo`, including who records the base commit.
  >
  > P2 — The mandatory reviewer loop and the worktree exclusivity rule conflict
  > as written. `AGENTS.md:54-63` requires a reviewer sub-agent for every block
  > and the protocol supports inspection of an uncommitted working-tree
  > manifest (`docs/REVIEW_PROTOCOL-v2.md:47-49`), but `AGENTS.md:141-142` says
  > never run two agents in the same worktree. The normal uncommitted-review
  > path necessarily has the implementer and read-only reviewer observing the
  > same worktree unless reviewers are explicitly exempt while the implementer
  > pauses, or a snapshot/dedicated worktree mechanism is required. State the
  > intended exception/mechanism.
  >
  > P2 — Current manifest contains a workflow-related type change outside
  > T-001’s declared Touches: `git status --short` reports `T CLAUDE.md`, while
  > T-001 Touches lists `AGENTS.md`, `.gitignore`, and docs but not `CLAUDE.md`
  > (`docs/tasks/T-001-mobile-backend-contract-sync.md:49-57`). Because the task
  > claims `CLAUDE.md` is the symlink to AGENTS, either add this exact symlink
  > normalization to Touches/acceptance or keep the type change out of the
  > eventual task commit. Other dirty/untracked paths may be pre-existing/user
  > work and should remain outside the task commit unless explicitly included.
  >
  > P3 — The universal ordering text is slightly over-broad.
  > `docs/BUILD_PLAN-v2.md:17-18` mandates schema → domain → API → UI → tests →
  > docs, while Phase 14 intentionally starts with a documentation/contract
  > audit at `docs/BUILD_PLAN-v2.md:202-204`. Clarify that the sequence applies
  > to implementation blocks after task readiness/contract audit; otherwise
  > the explicit Phase 14 order contradicts the universal rule.
- Resolution: owner-only phase gate fixed; startup now distinguishes initial
  claim from resume; readiness owner, checklist, reviewed commit, verdict, and
  base are explicit; paused-worktree read-only review is an explicit exception;
  `CLAUDE.md` is declared; implementation ordering excludes readiness/audit.
- Reviewer checks: `git diff --check` and `git diff --cached --check` passed.
- Verdict: changes required; corrected and submitted for a fresh review.

### Pass 2

- Reviewer task name/vendor: `/root/workflow_rereview`, Codex same-vendor
  fallback; cross-vendor reviewer unavailable in this session.
- Reviewed base/head or working-tree manifest: current tracked and untracked
  versions of the workflow files named in Pass 1.
- Findings (verbatim, P0–P3):

  > P0: none.
  >
  > P1 — Readiness/base flow remains non-executable because `base-commit` is
  > self-referential. `AGENTS.md:105-115` and `docs/tasks/TEMPLATE.md:20-23`
  > require the owner to record readiness evidence, promote the task to `todo`,
  > and record the accepted integration `base-commit` before the implementer
  > creates the branch from that commit. But the commit hash cannot be written
  > inside the same commit it identifies. If `base-commit` points to the
  > previous commit, the created branch omits the owner’s readiness evidence
  > and `todo` promotion. Define a non-circular sequence—for example, branch
  > from the owner’s readiness/promotion commit resolved externally at claim
  > time, then record that resolved hash in the first task commit.
  >
  > P2 — T-001’s readiness exception contains impossible provenance.
  > `docs/tasks/T-001-mobile-backend-contract-sync.md:11-13` records
  > `readiness-reviewed-commit: 4600266`, but `git cat-file -e
  > 4600266:docs/tasks/T-001-mobile-backend-contract-sync.md` fails because
  > that task file does not exist in the named commit. The task may legitimately
  > predate the new rule, but the fields should explicitly say
  > `not-applicable`/`exception` rather than presenting the integration base as
  > a reviewed task-file commit.
  >
  > P2 — Task acceptance/archive timing is still contradictory. `AGENTS.md:98`
  > defines task acceptance as “merge, archive the task, update PROGRESS,” while
  > `AGENTS.md:72-75` and `docs/BUILD_PLAN-v2.md:27-29` defer task archival until
  > phase acceptance after all task commits are accepted. Specify whether each
  > accepted task is archived immediately or all closed tasks remain active
  > until the owner closes the phase.
  >
  > P2 — The reviewer protocol hardcodes the baseline specification even though
  > the workflow permits task-specific active specifications. `AGENTS.md:105-110`
  > requires readiness against the named specs and T-001 names
  > `design/MOBILE-BACKEND-GAP-AUDIT.md`, but
  > `docs/REVIEW_PROTOCOL-v2.md:27-29` and `:101-104` instruct reviewers only
  > against `specs/FinnApp-v2.md`. Phase 14 intentionally uses supplementary
  > contracts before merging them into the primary spec, so the protocol should
  > require the task’s named specs plus applicable primary-spec sections.
- Resolution: initial claim now resolves the already-committed owner promotion
  `HEAD` and records it in the first task commit; T-001 uses explicit
  not-applicable readiness provenance; accepted tasks remain unarchived until
  phase close; review tasks name both task-specific and applicable primary
  specifications.
- Reviewer checks: direct tracked/untracked inspection, `git diff --check`, and
  `git diff --cached --check` passed.
- Verdict: changes required; corrected and submitted for a fresh review.

### Pass 3

- Reviewer task name/vendor: `/root/workflow_final_review`, Codex same-vendor
  fallback; cross-vendor reviewer unavailable in this session.
- Reviewed base/head or working-tree manifest: current workflow manifest,
  including all scoped tracked and untracked task files.
- Findings (verbatim, P0–P3):

  > P0: none.
  >
  > P1: none.
  >
  > P2 — The task template still bypasses the readiness lifecycle it documents.
  > `docs/tasks/TEMPLATE.md:4` defaults a newly specified task to `status: todo`,
  > while `AGENTS.md:105-113` requires it to remain `backlog` until an independent
  > readiness review and an owner-committed promotion. In addition, the existing
  > backlog task files `docs/tasks/T-002-period-model-migration.md:9-12` and
  > `docs/tasks/T-003-ledger-derived-balance.md:9-12` omit the new
  > `readiness-reviewed-commit` and `readiness-verdict` fields required by
  > `AGENTS.md:105-111`. Default the template to `backlog` and add the missing
  > blank readiness fields to both prepared tasks.
  >
  > P3: none.
- Resolution: the template now defaults to `backlog`; T-002 and T-003 include
  all readiness evidence fields.
- Reviewer checks: direct tracked/untracked inspection; valid `CLAUDE.md`
  symlink; `git diff --check` and `git diff --cached --check` passed.
- Verdict: changes required; corrected and submitted for final confirmation.

### Pass 4

- Reviewer task name/vendor: `/root/workflow_confirmation`, Codex same-vendor
  fallback; cross-vendor reviewer unavailable in this session.
- Reviewed base/head or working-tree manifest: final workflow manifest,
  including scoped tracked/untracked files and the `CLAUDE.md` symlink.
- Findings (verbatim, P0–P3):

  > P0–P3: no remaining findings.
- Resolution: none required; Pass 1–3 findings are closed.
- Reviewer checks: `git diff --check`, `git diff --cached --check`, symlink
  target/content validation, tracked and scoped untracked inspection.
- Verdict: clean.

### Pass 5

- Reviewer task name/vendor: `/root/design_backend_gap_review`, Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed base/head or working-tree manifest: final source screen, written
  mobile specs, current backend/schema/routes, account-period v2.1 proposal,
  and all tracked/untracked Phase 14/15 planning artifacts.
- Findings (verbatim, P0–P3):

  > P0: none.
  >
  > P1 — The frozen mobile design has no rollover-policy control, but the
  > planning docs claim mobile users select one. `ACCOUNT_PERIODS-v2.1.md:343-355`
  > requires `rollover_policy` on create/update, while `spec/04-sheets.md:30-32`
  > gives Start/Edit period only Start date and End date. `DESIGN-NOTES.md`
  > nevertheless says “the user picks one of exactly two rollover policies,”
  > and the audit/backlog do not classify this mismatch. Phase 15 cannot satisfy
  > both without changing the frozen sheet geometry. Record an explicit
  > decision: either mobile always uses the backend default while policy
  > selection remains a desktop/API capability, or identify an owner-approved
  > interaction already present in the final design. Do not let Phase 15 invent
  > a control.
  >
  > P1 — Start-period date semantics are missing from the audit. The final
  > source makes Start date an interactive Choose field in both Start period and
  > Edit period (`Finapp Screen.dc.html:649-654`; `spec/04-sheets.md:30-32`), but
  > v2.1 server-fixes Start date to today and excludes scheduled periods
  > (`ACCOUNT_PERIODS-v2.1.md:67-68,345-355`). The audit handles only editing an
  > existing period and even permits a read-only fallback, which contradicts
  > the frozen interactive field. T-007 must cover create-time Start date
  > semantics as well as editing, including allowed past/future bounds, snapshot
  > time, membership, and successor conflicts; otherwise the backend still
  > cannot drive the final design.
  >
  > P1 — T-014 silently changes the specified navigation for Planned rows. The
  > audit says planned projections “route to Plan details”
  > (`MOBILE-BACKEND-GAP-AUDIT.md:36`), but the written tap map says every
  > Transactions row opens Transaction details (`spec/05-interactions.md:8-10`),
  > and the final source binds every feed row, including Planned, to `openTx`
  > (`Finapp Screen.dc.html:92-110`). Because Transaction details also exposes
  > Edit/Delete actions, this is a real contract question, not a harmless
  > adapter choice. Preserve the specified Transaction-details route and define
  > a planned detail/action shape, or record an explicit owner resolution; do
  > not redirect it silently.
  >
  > P1 — The audit incorrectly classifies Plan rule creation/editing as already
  > supported. The frozen shape uses `expectedIncome|requiredExpense`, a `From
  > account` field for the rule shape, and a separate required toggle
  > (`spec/07-data-model.md:60-67`; `spec/04-sheets.md:38-40`). The backend has
  > five different kind values, distinct `default_from_account_id`/
  > `default_to_account_id`, and rejects a source account for income
  > (`app/schemas.py:371-409`; `app/plan.py:145-174`). A mobile Expected income
  > rule therefore cannot be submitted faithfully from the specified sheet. Add
  > a Phase 14 contract task that defines kind mapping, income account direction,
  > category behavior, and required-toggle semantics before treating Plan as
  > frontend-only.
  >
  > P1 — T-018 is not sufficiently specified or ordered for the current
  > workspace model. The design’s Owner option is chosen while creating an
  > account invitation, but the backend stores account ownership separately from
  > the owning workspace, whose owner, categories, rates, transactions, Plan,
  > and authentication context remain workspace-scoped. Changing only
  > `account.owner_user_id` can leave the new owner operating through a different
  > primary workspace while the account and related records remain in the old
  > one. The audit mentions atomic ownership but not workspace binding or
  > invite-acceptance semantics, and the backlog blocks T-018 only on T-001.
  > Mark this as an architecture/product blocker, define what an Owner invitation
  > transfers, and order it after the period/privacy contract it must preserve.
  >
  > P2 — Category merge/delete must define what happens to Plan rules, not only
  > transactions. `PlanRule.category_id` uses a restrictive foreign key, so
  > deleting or merging a category used by an active or archived rule can fail
  > or strand desktop Plan behavior. The T-016 audit row promises transaction
  > reassignment and ledger invariance but omits Plan-rule reassignment, archival,
  > and eligibility semantics. Add these references and tests to T-016 while
  > preserving historical linked transactions.
  >
  > P2 — Mobile handling of backend `adjustment` and `exchange` transactions
  > remains undefined. The final screen visibly includes Opening balance, while
  > its mobile data model exposes only income/expense/transfer. The audit lists
  > adjustment/exchange filters as desktop-only, but T-014 still has to project
  > those real records into All/date groups and T-015 must state whether they are
  > convertible/editable. Define their mobile row/type/detail mapping and keep
  > the richer desktop filters; otherwise opening balances, reconciliations, and
  > exchanges can disappear or be mislabeled.
  >
  > P2 — The nested design instructions still contradict the newly recorded
  > authority hierarchy. `docs/design/Finnapp mobile specification/AGENTS.md:17-19`
  > tells future implementers to open `Finapp Mobile Redesign.dc.html` as the
  > visual reference, while the audit, design notes, ADR, and owner clarification
  > classify it as a raw overview and name `Finapp Screen.dc.html` as final.
  > Because a nested `AGENTS.md` is operational guidance, this can reproduce the
  > exact confusion the handoff is meant to eliminate. Align or explicitly
  > supersede those two lines without altering visual assets.
  >
  > P2 — The audit calls itself “approved planning input” while T-001 remains in
  > review and still has unresolved P1/P2 findings. `PROGRESS.md` correctly says
  > the contract audit is written and T-001 is in review. Keep the audit status
  > as draft/review until owner acceptance and the reviewer gate close; otherwise
  > later agents may start Phase 14 from a document that the workflow says is not
  > accepted.
- Resolution: mobile defaults rollover to `carry_next_day`; T-007 now covers
  create/edit Start date and replay; T-014 preserves Transaction-details
  navigation and maps adjustment/exchange; T-019 adds the Plan adapter contract;
  T-018 is an ordered architecture blocker; T-016 includes Plan-rule references;
  nested operational guidance is aligned; audit status remains review draft.
- Reviewer checks: direct tracked/untracked/source/backend inspection;
  `git diff --check` and `git diff --cached --check` passed.
- Verdict: changes required; corrected and submitted for re-review.

### Pass 6

- Reviewer task name/vendor: `/root/design_backend_gap_rereview`, Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed base/head or working-tree manifest: corrected design/backend audit,
  source/spec/backend evidence, and all Phase 14/15 references through T-031.
- Findings (verbatim, P0–P3):

  > P0–P3: no remaining findings.
- Resolution: none required; all Pass 5 findings are closed.
- Reviewer checks: direct source/spec/backend and scoped tracked/untracked file
  inspection; stale task-reference search; `git diff --check` and
  `git diff --cached --check` passed.
- Verdict: clean.

### Pass 7

- Reviewer task name/vendor: `/root/owner_decisions_review`, Codex same-vendor
  fallback; cross-vendor reviewer unavailable in this session.
- Reviewed base/head or working-tree manifest: owner-decision updates across
  the period contract, mobile written specs, audit, ADR, backlog/build plan,
  progress, and T-001/T-002/T-003.
- Findings (verbatim, P0–P3):

  > P0: none.
  >
  > P1 — The account-period specification still gives two opposite default
  > policies. `docs/specs/ACCOUNT_PERIODS-v2.1.md:235-236` correctly sets
  > `redistribute_remaining_days` as the default, but `:280` says
  > `carry_next_day` “remains the default.” This can produce the wrong backend
  > behavior despite the audit, ADR, mobile specs, backlog, and build plan all
  > recording redistribution. Remove the stale carry-default statement.
  >
  > P1 — Start-date behavior is not an executable contract yet.
  > `ACCOUNT_PERIODS-v2.1.md:67-68,346-358` simultaneously says Start date
  > equals creation day, the server sets it to today, create accepts past/today,
  > current-period editing may change it, and PATCH rejects it. The API examples
  > at `:375-421` also omit `start_date`. More importantly, `:63-64,134-163`
  > keeps an immutable creation-time opening snapshot and a `created_at` replay
  > boundary, while `MOBILE-BACKEND-GAP-AUDIT.md:33` requires changing Start
  > date to recompute the opening snapshot and dated-ledger membership. Normalize
  > create/PATCH fields, past/today/future validation, snapshot/replay semantics,
  > and add matching §12 acceptance cases before T-007 can be specified safely.
  >
  > P2: none.
  >
  > P3: none.
- Resolution: removed the stale carry default; added explicit `snapshot_at`,
  normalized create/PATCH Start-date fields and examples, defined atomic
  current-period repartition/replay semantics, and added acceptance scenarios.
- Reviewer checks: `git diff --check`, `git diff --cached --check`, and direct
  tracked/untracked inspection; no application/UI/source changes.
- Verdict: changes required; corrected and submitted for re-review.

### Pass 8

- Reviewer task name/vendor: `/root/owner_decisions_rereview`, Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed base/head or working-tree manifest: corrected period contract,
  T-002/T-003, audit, owner-corrected mobile specs, backlog/build plan, ADR,
  and status documents.
- Findings (verbatim, P0–P3):

  > P0: none.
  >
  > P1 — The required allowance example is still unresolved inside the
  > implementation contract. `docs/specs/ACCOUNT_PERIODS-v2.1.md:406-423`
  > returns `available_today: "685882"` with no reference date, effective-day
  > movements, or ledger fixture from which that value can be derived under
  > `redistribute_remaining_days`. `docs/design/MOBILE-BACKEND-GAP-AUDIT.md:31`
  > explicitly assigns the missing coherent fixture to T-001, but T-001 is
  > otherwise presented as ready for acceptance. Add a dated
  > ledger/reference-time fixture deriving opening balance, current balance,
  > days remaining, and Available today exactly, or replace the API example
  > with values directly derivable from the included facts.
  >
  > P2 — The audit still describes the repaired Start-date contract as broken.
  > `docs/design/MOBILE-BACKEND-GAP-AUDIT.md:33` says the proposed v2.1 spec
  > fixes create to today and makes Start date immutable, while
  > `docs/specs/ACCOUNT_PERIODS-v2.1.md:72-74,362-375,392-440` now correctly
  > accepts past/today Start date on create and PATCH and rejects future dates.
  > Update the audit’s current/proposed-spec column so the accepted contract and
  > remaining T-007 implementation work are distinguishable.
  >
  > P2 — T-003 weakens the exact snapshot-boundary predicate.
  > `docs/tasks/T-003-ledger-derived-balance.md:33-34` says the window runs
  > “from `snapshot_at` through” `T`, which can be read as inclusive, while the
  > controlling contract at `docs/specs/ACCOUNT_PERIODS-v2.1.md:145-164`
  > requires `snapshot_at < leg.created_at <= T` because equality belongs to
  > `opening_balance`. State the exact predicate in T-003 acceptance to prevent
  > double counting at the replay boundary.
  >
  > P3: none.
- Resolution: added a dated VND ledger fixture deriving `685,882` exactly under
  redistribution; updated the audit to distinguish accepted contract from
  shipped backend; copied the strict snapshot predicate into T-003.
- Reviewer checks: `git diff --check`, `git diff --cached --check`, direct
  tracked/untracked inspection, and no application/UI/source diff.
- Verdict: changes required; corrected and submitted for final confirmation.

### Pass 9

- Reviewer task name/vendor: `/root/owner_decisions_confirmation`, Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed base/head or working-tree manifest: final owner-decision and period
  contract documentation, including the dated allowance fixture.
- Findings (verbatim, P0–P3):

  > P0: none.
  >
  > P1: none.
  >
  > P2 — Pass 8 audit wording is still stale.
  > `MOBILE-BACKEND-GAP-AUDIT.md:31` still claims v2.1 lacks a derivable
  > `685882` fixture, although `ACCOUNT_PERIODS-v2.1.md:408` now contains the
  > complete dated derivation. Update this row to distinguish the repaired
  > specification from the shipped backend.
  >
  > P3: none.
- Resolution: the audit now states that the accepted spec contains the exact
  fixture and assigns its implementation/regression proof to T-005/T-006/T-021.
- Reviewer checks: staged set empty; tracked/cached/scoped-untracked checks
  pass; all other owner decisions are consistent; no application/UI/source diff.
- Verdict: one documentation-only P2 corrected; submitted for final confirmation.

### Pass 10

- Reviewer task name/vendor: `/root/owner_decisions_final_clean`, Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed base/head or working-tree manifest: final owner-decision planning
  manifest after the allowance-audit correction.
- Findings (verbatim, P0–P3):

  > Clean verdict: P0–P3 none.
- Resolution: none required; Pass 7–9 findings and all owner decisions closed.
- Reviewer checks: `git diff --check`, cached check, empty staged set, direct
  scoped tracked/untracked inspection; no application/runtime/visual-source diff.
- Verdict: clean.

### Pass 11

- Reviewer task name/vendor: `/root/t001_acceptance_commit_review`, Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed base/head or working-tree manifest: owner-acceptance transition and
  complete intended documentation commit manifest, including scoped root
  workflow support files.
- Findings (verbatim, P0–P3):

  > P0: none.
  >
  > P1 — A `docs/**`-only commit cannot truthfully close T-001 while its
  > acceptance and Touches include `AGENTS.md`, `CLAUDE.md`, and `.gitignore`.
  > Include those exact workflow support files or reopen/narrow the claims.
  >
  > P2 — The portable handoff contains trailing whitespace and the Phase 8–13
  > history has an extra EOF blank line, so a staged diff check would fail.
  >
  > P2 — `BACKLOG.md` still calls the accepted audit a review draft.
  >
  > P2 — `PROGRESS.md` still says the `685882` fixture is missing although it
  > has been added and reviewed.
- Resolution: commit scope includes only `docs/**` plus `AGENTS.md`, the
  `CLAUDE.md` symlink, and `.gitignore`; whitespace is corrected; backlog and
  progress now reflect the accepted audit and exact fixture.
- Reviewer checks: direct tracked/untracked/ignored inspection; T-002 remains
  backlog/unclaimed; no application/migration/test changes; staged set empty.
- Verdict: changes required; corrected and submitted for fresh pre-commit review.

### Pass 12

- Reviewer task name/vendor: `/root/t001_commit_confirmation`, Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed base/head or working-tree manifest: final intended commit scope
  `docs/**`, `AGENTS.md`, `CLAUDE.md`, and `.gitignore`.
- Findings (verbatim, P0–P3):

  > P0–P3: no findings.
- Resolution: none required; all Pass 11 findings are closed.
- Reviewer checks: task/backlog/progress consistency; T-002 unclaimed;
  ignored/raw versus trackable design set; tracked/cached/all intended
  untracked whitespace; exact commit scope and message.
- Verdict: commit-ready.

## Session log

- 2026-08-09 Codex: audited the final mobile source/spec against models,
  schemas, routes, period formulas, permissions, and lifecycle behavior;
  normalised the workflow; split backend synchronization into Phase 14 and
  mobile implementation into Phase 15. Left all work unstaged as requested.
  Review is clean. Remaining: repository-owner acceptance of T-001 and the
  explicit provider, ownership/workspace, and session decisions before their
  blocked Phase 14 tasks are specified.
- 2026-08-09 Codex: recorded the owner's follow-up product decisions without
  changing application code or the visual source: selectable rollover defaults
  to redistribution; Available today is informational; Plan Skip is
  occurrence-scoped and Delete rule archives; account labels are directional;
  Owner/Auto are disabled placeholders; logout keeps server sessions. Moved
  ownership transfer and automatic integrations to the post-redesign Icebox.
- 2026-08-09 repository owner: accepted T-001 by explicitly requesting the
  documentation commit. No Phase 14 application implementation was started.
