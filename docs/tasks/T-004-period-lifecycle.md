---
id: T-004
title: Enforce account-period close, expiry, and successor lifecycle
status: in-progress
size: M
spec: specs/ACCOUNT_PERIODS-v2.1.md §4–§5
blocked-by: [T-002]
branch: task/T-004-period-lifecycle
base-commit: 74556f7e7859f4d65d5c5004e971456a517d21a3
implementer: Codex
readiness-reviewed-by: /root/t004_final_scope_review (Codex same-vendor fallback)
readiness-reviewed-commit: 7f9e146
readiness-verdict: ready
---

## Goal

Account periods transition deterministically from current to manually closed or
naturally ended history, and either historical state permits an exact-boundary
same-account successor without mutating the predecessor.

## Acceptance

- [ ] `period_status` uses the account workspace's local calendar date:
      `current` is an unclosed period whose inclusive range contains that date,
      `ended` is an unclosed period after `end_date`, and `closed` is any period
      with `closed_at`; no read lazily writes expiry state or invents a natural
      `closing_balance`.
- [ ] An ended period has `closed_at=null` and `closing_balance=null`, remains
      immutable, and rejects both edit and manual-close attempts; a manually
      closed period likewise rejects subsequent edits and repeated close.
- [ ] Manual close is allowed only for a current period and commits
      `closed_at` plus the exact posted-ledger `closing_balance` captured through
      that same UTC instant in one transaction.
- [ ] Closing never creates, edits, deletes, or voids a ledger movement. A
      focused test compares the complete ledger row identities, amounts, and
      statuses before/after close while the stored `closing_balance` preserves
      exact high-precision Decimal value.
- [ ] After manual close, Correction, Delete, and Undo remain allowed and
      change the live account ledger/balance according to their normal rules,
      while the period's `snapshot_at`, `opening_balance`, `closed_at`, and
      `closing_balance` remain byte-for-byte unchanged.
- [ ] Period lifecycle state never disables an otherwise authorized Financial
      Operation or transaction account assignment: new Spend/Add
      funds/Transfer/Exchange/Adjustment flows continue to apply their normal
      ledger and permission rules after natural expiry or manual close without
      mutating historical period snapshots.
- [ ] One creation transaction rejects a second current period on the same
      account, selects the latest eligible historical predecessor boundary,
      derives the exact Decimal posted balance through that boundary, and
      persists the successor. Closed and naturally ended predecessors do not
      block the successor even when their original calendar ranges overlap;
      periods on different accounts remain independent.
- [ ] A same-workspace-day successor is valid immediately after close. Its
      `snapshot_at` is the later of its workspace-local `start_boundary` and
      the latest eligible predecessor close/end boundary, and its
      `opening_balance` is the exact posted balance through that instant.
- [ ] A leg exactly at the predecessor close/successor snapshot boundary is
      included in the predecessor's closed window and successor opening
      snapshot, but excluded from the successor replay window.
- [ ] Natural expiry remains read-only and permits a successor without a
      write-on-read finalization; GET and list leave the persisted predecessor
      byte-for-byte unchanged with both closing fields null. The ended period's
      replay window stays strictly before its workspace-local end boundary and
      cannot absorb successor-era activity.
- [ ] Focused tests cover workspace-local midnight status; ended close/edit
      rejection; GET/list natural-expiry persistence; exact high-precision
      manual-close cutoff with an unchanged ledger; post-close Correction,
      Delete, Undo, new Operations, exchange, and account reassignment with
      immutable snapshots; same-day closed successor boundary partitioning;
      same-account current-period rejection; and different-account
      independence.
- [ ] A non-UTC natural-expiry test uses at least two historical same-account
      predecessors and legs immediately before and exactly at the latest end
      boundary. It proves latest-boundary selection, strict equality exclusion
      from ended replay, equality inclusion in successor opening, and exclusion
      from successor replay.

## Touches

- `app/periods.py`
- `tests/test_period_lifecycle_v2.py`
- `tests/test_periods_v2.py` — replace lifecycle assertions that encode the
  superseded closed-period transaction guard
- `tests/test_operations_undo_v2.py` — replace the superseded closed-period
  Undo rejection assertion
- `docs/tasks/T-004-period-lifecycle.md`
- `docs/BACKLOG.md` and `docs/PROGRESS.md` for task lifecycle state only

## Out of scope

- Start-date edit replay and successor-crossing edit validation — T-007.
- Rollover-policy allowance formulas — T-005 and T-006.
- Final period response/request schemas, route inventory, list filters, and
  removal of legacy fields — T-008 and T-009.
- Shared-account period permissions — T-010.
- Schema or Alembic changes; T-002 already supplied the lifecycle columns and
  constraints.
- Phase 15 UI work or changes to `app/static/`.

## Verification

```bash
.venv/bin/python -m pytest tests/test_period_lifecycle_v2.py -q
.venv/bin/python -m pytest tests/test_periods_v2.py tests/test_operations_undo_v2.py -q
.venv/bin/python -m pytest tests/test_operations_v2.py -k "without_a_period or period" -q
.venv/bin/python -m pytest -q
node --check app/static/app.js
git diff --check
git status --short
```

Database-backed tests must use their isolated pytest database fixture. Any
manual migration or application check must set an explicit scratch
`DATABASE_URL`; `finapp.db` is never opened or replaced by this task.

## Readiness review

Append-only readiness passes. The reviewer checks this definition against
`specs/ACCOUNT_PERIODS-v2.1.md` §§4–5, the applicable lifecycle baseline in
`specs/FinnApp-v2.md` §§5 and §7, and
`decisions/ADR-0005-periods-are-optional-and-ledger-derived.md`.

### Pass 1

- Reviewer task name/vendor: `/root/t004_readiness_review`, Codex same-vendor
  fallback; cross-vendor reviewer unavailable in this session.
- Reviewed task-file commit: `e89b7ce`.
- Findings (verbatim, P0–P3):

  > P0: None.
  >
  > P1 — Post-close ledger editing is underspecified and can pass vacuously by continuing to reject every edit. The task only says later Correction, Delete, or Undo “cannot rewrite” stored snapshots (`docs/tasks/T-004-period-lifecycle.md:35-37`), but §5 requires those operations to remain allowed, change the live ledger normally, and leave snapshots unchanged (`docs/specs/ACCOUNT_PERIODS-v2.1.md:182-186`). This ambiguity is material because the current guard explicitly rejects transaction changes affecting a closed period (`app/periods.py:223-235`). Add a checkable acceptance criterion and focused tests proving Correction, Delete, and Undo after manual close update the live ledger according to normal rules while `snapshot_at`, `opening_balance`, `closed_at`, and `closing_balance` remain byte-for-byte unchanged. This belongs in T-004, not the T-008 response/route-surface task.
  >
  > P1 — Successor creation does not require the atomic snapshot reconstruction mandated by §5. The task separately requires current-period blocking (`docs/tasks/T-004-period-lifecycle.md:38-41`) and an exact successor `snapshot_at`/`opening_balance` (`docs/tasks/T-004-period-lifecycle.md:42-45`), but only manual close is explicitly required to use one transaction (`docs/tasks/T-004-period-lifecycle.md:32-34`). The specification says period creation must atomically reconstruct `opening_balance` from posted legs through the selected snapshot boundary (`docs/specs/ACCOUNT_PERIODS-v2.1.md:160-164`), while the lifecycle invariant permits at most one current period (`docs/specs/ACCOUNT_PERIODS-v2.1.md:90-97`, `docs/specs/ACCOUNT_PERIODS-v2.1.md:134-136`). Require one creation transaction to enforce the same-account current-period guard, select the latest eligible predecessor boundary, derive the exact Decimal posted balance through that boundary, and persist the successor. Otherwise a check-then-create implementation can satisfy the written bullets sequentially while violating the atomic financial boundary or admitting concurrent current periods.
  >
  > P2 — The required focused-test list does not prove either no-write lifecycle path. Acceptance prohibits lazy expiry writes and any close-time ledger mutation (`docs/tasks/T-004-period-lifecycle.md:24-28`, `docs/tasks/T-004-period-lifecycle.md:35-37`), but the listed tests mention only midnight status, successor creation, close cutoff, and snapshot immutability (`docs/tasks/T-004-period-lifecycle.md:53-57`). Add assertions that GET/list across natural expiry leaves the persisted predecessor unchanged with both closing fields null, and that manual close leaves the complete ledger row set and statuses unchanged while storing the exact high-precision Decimal balance. These directly cover §4’s no-finalization rule (`docs/specs/ACCOUNT_PERIODS-v2.1.md:105-109`) and §5’s snapshot-only close semantics (`docs/specs/ACCOUNT_PERIODS-v2.1.md:121-127`).
  >
  > P2 — Natural-expiry boundary selection is not sufficiently tested. The task requires the latest eligible predecessor boundary and strict ended replay cutoff (`docs/tasks/T-004-period-lifecycle.md:42-51`), but its test list requires only generic “naturally ended successor creation” (`docs/tasks/T-004-period-lifecycle.md:53-57`). Add a workspace with a non-UTC timezone, at least two historical same-account predecessors, and legs just before and exactly at the latest natural end boundary. Assert that the successor selects that latest boundary, the ended predecessor excludes equality, and successor opening includes equality while successor replay excludes it, as required by `docs/specs/ACCOUNT_PERIODS-v2.1.md:138-164`.
  >
  > P2 — Verification is not exact for the declared test scope. `Touches` allows either `tests/test_periods_v2.py` or a separate bounded lifecycle module (`docs/tasks/T-004-period-lifecycle.md:59-63`), but the targeted command executes only `tests/test_periods_v2.py` (`docs/tasks/T-004-period-lifecycle.md:77-81`). Either restrict the task to that file or name/include the alternate module in the command so every permitted implementation has a mandatory targeted gate.
  >
  > P3: None.
  >
  > Verdict: **not ready**. The goal, M-size boundary, T-002 dependency, workspace-local status rules, ended/closed immutability, historical-overlap override, same-day successor partition, T-007/T-008 separation, scratch-database rule, and general repository checks are otherwise appropriately bounded. Commit `e89b7cef0f8d6fd4287514642dde953e1a650ea0` was reviewed read-only; `git diff --check e89b7ce^ e89b7ce` passed.
- Resolution: post-close ledger edits, transactional successor creation, both
  no-write paths, exact natural-boundary partitioning, and the single focused
  test module are now explicit acceptance requirements.
- Verdict: not ready; corrected and submitted for fresh readiness review.

### Pass 2

- Reviewer task name/vendor: `/root/t004_readiness_rereview`, Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed task-file commit: `f03b8e8`.
- Findings (verbatim, P0–P3):

  > P0: None.
  >
  > P1: None. Prior P1 findings are closed:
  >
  > - Post-close Correction, Delete, and Undo must remain functional, change the live ledger normally, and preserve all four stored snapshots unchanged.
  > - Current-period guard, predecessor-boundary selection, exact Decimal balance derivation, and successor persistence are explicitly required in one creation transaction.
  >
  > P2: None. Prior P2 findings are closed:
  >
  > - GET/list natural expiry must be persistence-neutral.
  > - Manual close must leave complete ledger identities, amounts, and statuses unchanged while preserving a high-precision balance.
  > - The non-UTC test requires multiple predecessors and exact-equality boundary partitioning.
  > - `Touches` and the targeted command name the same exact module: `tests/test_period_lifecycle_v2.py`.
  >
  > P3: None.
  >
  > Verdict: **ready**.
  >
  > The goal, M scope, T-002 dependency, Touches, exclusions for T-005–T-010/Phase 15, scratch-database rule, and verification commands are bounded and consistent with the named specifications, ADR-0005, BACKLOG, AGENTS, and review protocol. Reviewed commit `f03b8e87e1033e9d41d6e592c2c7ce06fa922a32` read-only; worktree was clean and `git diff --check f03b8e8^ f03b8e8` passed. No tests were needed for this documentation-only readiness review.
- Resolution: none required.
- Verdict: ready.

### Pass 3 — claimed-scope amendment

- Reviewer task name/vendor: `/root/t004_scope_review`, Codex same-vendor
  fallback; cross-vendor reviewer unavailable in this session.
- Reviewed task-file range: `44c482c..ca4ab5a`.
- Findings (verbatim, P0–P3):

  > Read-only scope verdict for `44c482c..ca4ab5a`: **not ready only because the targeted command can silently deselect the new focused module; the two added legacy-test touches themselves are required and bounded.**
  >
  > Verbatim findings:
  >
  > P0: None.
  >
  > P1: None. Updating the existing closed-period transaction-edit and Undo assertions is required by `ACCOUNT_PERIODS-v2.1.md` §5 lines 182–186: Correction, Delete, and Undo must remain allowed after manual close and must alter the live ledger normally without rewriting snapshots. The present assertions at `tests/test_periods_v2.py:779-790` and `tests/test_operations_undo_v2.py:362-370` encode the superseded rejection and would contradict the accepted contract. Limiting the edits to those lifecycle assertions is bounded T-004 regression work, not a route/API redesign.
  >
  > P2 — The targeted verification is not exact for the new focused test module. `tests/test_period_lifecycle_v2.py` does not yet exist, and the command applies `-k "lifecycle or ended_transaction or resulting_period_state or undo_period_guards"` to all three files. Nothing in Acceptance requires every new test function in `tests/test_period_lifecycle_v2.py` to contain `lifecycle`, so required close/expiry/successor tests can be silently deselected while the command passes. Run `tests/test_period_lifecycle_v2.py` unfiltered, then run the two legacy modules with the narrow `-k`, or remove `-k` from the combined command.
  >
  > P3: None.
  >
  > Implementation-file scope: no file besides `app/periods.py` is presently implied. The shared `enforce_transaction_period_impact` guard that rejects closed-period changes is defined in `app/periods.py:223-242`; existing transaction Correction/Delete and Operations Undo paths already call that shared guard (`app/transactions.py`, `app/operations.py`) and should inherit the new behavior without edits. Manual close, status, predecessor selection, and creation also live in `app/periods.py`. Any need to edit `app/transactions.py` or `app/operations.py` would be a newly discovered scope change requiring review.
  >
  > Verdict: **not ready** until the targeted command executes all of `tests/test_period_lifecycle_v2.py`; after that documentation-only fix, ready for implementation.
- Resolution: the new focused module now runs unfiltered in its own command;
  the narrow selector applies only to the two legacy regression modules.
- Verdict: not ready; corrected and submitted for fresh scope re-review.

### Pass 4 — claimed-scope amendment re-review

- Reviewer task name/vendor: `/root/t004_scope_rereview`, Codex same-vendor
  fallback; cross-vendor reviewer unavailable in this session.
- Reviewed task-file commit: `f371904`.
- Findings (verbatim, P0–P3):

  > P0: None.
  >
  > P1: None.
  >
  > P2: None. Prior scope-review P2 is closed: `tests/test_period_lifecycle_v2.py` now runs unfiltered, while `-k "lifecycle or ended_transaction or resulting_period_state or undo_period_guards"` is limited to the two legacy modules and matches their relevant existing test names.
  >
  > P3: None.
  >
  > The legacy touches remain bounded and required by `ACCOUNT_PERIODS-v2.1.md` §5: the named assertions currently encode the superseded rule rejecting Correction/Delete/Undo after manual close. No implementation file beyond `app/periods.py` is implied. The shared guard, status, close, predecessor selection, snapshot derivation, and creation behavior all live there; transaction Correction/Delete and Operations Undo already invoke that guard through existing paths.
  >
  > Verdict: **ready for implementation**. Reviewed `f3719041ed21a8b36601156cf132e6115807b28f` read-only; worktree was clean and `git diff --check f371904^ f371904` passed. No tests run.
- Resolution: none required.
- Verdict: ready for implementation.

### Pass 5 — complete closed-state scope review

- Reviewer task name/vendor: `/root/t004_final_scope_review`, Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed task-file commit: `7f9e146`.
- Findings (verbatim, P0–P3):

  > P0: None.
  >
  > P1: None.
  >
  > P2: None.
  >
  > P3: None.
  >
  > Verdict: **ready for implementation**.
  >
  > The amended acceptance criterion is consistent with `ACCOUNT_PERIODS-v2.1.md` §§4–5 and ADR-0005: lifecycle state cannot permanently block otherwise authorized Financial Operations or transaction account assignment, while stored period snapshots remain unchanged. Existing ended-state confirmation behavior can remain; it enables rather than permanently rejects the action. Closed-state rejection assertions are superseded.
  >
  > Updating all affected assertions within the already-scoped `tests/test_periods_v2.py` and `tests/test_operations_undo_v2.py` is bounded lifecycle regression work. Verification now runs the new lifecycle module and both legacy modules unfiltered, so no relevant assertion can be silently deselected.
  >
  > No implementation file beyond `app/periods.py` is implied. The shared period-impact guard, lifecycle status, close logic, predecessor selection, snapshot derivation, and creation behavior are all located there; transaction and Operations paths already invoke that shared guard.
  >
  > Reviewed commit `7f9e1467cf1da67583a2de972ec97a450323ecd9` read-only. Worktree was clean. No tests run, as requested.
- Resolution: none required.
- Verdict: ready for implementation.

## Review

Append-only implementation review passes. A different read-only agent returns
the review; the implementer records it verbatim following
[`../REVIEW_PROTOCOL-v2.md`](../REVIEW_PROTOCOL-v2.md).

### Pass 1 — close, expiry, and closed-ledger behavior

- Reviewer task name/vendor: `/root/t004_close_expiry_review`, Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed base/head or working-tree manifest: base `96d1368`; modified
  `app/periods.py`, `tests/test_periods_v2.py`, and
  `tests/test_operations_undo_v2.py`; directly inspected untracked
  `tests/test_period_lifecycle_v2.py`.
- Findings (verbatim, P0–P3):

  > P0: None.
  >
  > P1: None.
  >
  > P2 — Closed-snapshot immutability is not verified for all newly enabled mutation paths required by T-004. The focused test preserves snapshots only across Correction, Delete, a new Spend, and Undo (`tests/test_period_lifecycle_v2.py:154-190`). Account reassignment (`tests/test_periods_v2.py:952-966`, `tests/test_periods_v2.py:1003-1013`), Adjustment/reconcile (`tests/test_periods_v2.py:1014-1023`), and Exchange (`tests/test_periods_v2.py:1073-1083`, `tests/test_periods_v2.py:1195-1207`) assert success or live balance changes but never compare the closed period’s `snapshot_at`, `opening_balance`, `closed_at`, and `closing_balance` before and after. This leaves the explicit T-004 acceptance invariant unproved for those paths. Add persisted-state comparisons around each distinct post-close path, or a focused parameterized test that exercises them and asserts all four snapshot fields remain unchanged.
  >
  > P3 — The final assertion in the closed Undo regression fetches the earlier naturally ended `period`, not `closed_period` (`tests/test_operations_undo_v2.py:371-373`). It therefore provides no evidence about the closed period involved in the Undo and appears to be a stale assertion. Point it at `closed_period` and preferably compare its stored snapshot state, or remove it as redundant once the focused lifecycle test owns that proof.
  >
  > Missing tests:
  >
  > - Immutable stored snapshots after moving a transaction into and out of a closed-period account.
  > - Immutable stored snapshots after assigning an unassigned transaction to a closed-period account.
  > - Immutable stored snapshots after reconcile/Adjustment against a closed-period account.
  > - Immutable stored snapshots after Exchange involving a closed-period account.
  >
  > The implementation itself correctly removes only the closed-ledger guard, keeps ended confirmation behavior, rejects edits/close on naturally ended periods, restricts manual close to `current`, and captures one UTC cutoff used for the posted-ledger balance. The focused close test also proves exact-boundary inclusion, high-precision Decimal storage, and unchanged ledger rows.
  >
  > Verdict: **changes required** because the P2 coverage gap must be closed and re-reviewed. Successor selection/current-period creation behavior was intentionally not reviewed in this pass.
- Resolution: added exact four-field snapshot comparisons around closed-account
  reassignment, assignment, reconcile/Adjustment, shared Exchange, and Undo;
  the stale Undo assertion now checks the actual closed period.
- Reviewer checks: targeted lifecycle/legacy modules `29 passed`; `git
  diff --check` passed before review.
- Verdict: changes required; corrected and submitted for fresh re-review.

### Pass 2 — close/expiry re-review

- Reviewer task name/vendor: `/root/t004_close_expiry_rereview`, Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed base/head or working-tree manifest: base `96d1368`; complete current
  block working tree including untracked `tests/test_period_lifecycle_v2.py`.
- Findings (verbatim, P0–P3):

  > Read-only re-review verdict: **changes required**. P0: None. P1: None. P2 — prior snapshot-immutability coverage is still not fully closed: `tests/test_period_lifecycle_v2.py:179-190` performs a new Spend and then Undo but compares the stored snapshot only after Undo, so it does not prove the new Spend itself left all four fields unchanged; likewise `tests/test_periods_v2.py:965-980` moves one transaction into and another out of the closed account but compares only after both operations, not after each distinct reassignment. Add an immediate `stored_snapshot == closed_snapshot` assertion after the new Spend and after each reassignment (at minimum after move-in before move-out), then re-review. P3: None; stale Undo assertion is fixed and checks `closed_period`. Unassigned assignment, reconcile/Adjustment, shared Exchange, Correction, Delete, and Undo now have direct stored-snapshot comparisons. Production close/expiry behavior reviewed against §§4–5 is otherwise sound for this block: ended GET/list are write-neutral, ended edit/close reject, close is current-only and stores one UTC-cutoff posted balance atomically without ledger mutation, and closed ledger operations are no longer permanently blocked. Successor block not reviewed. I reran the exact target: 29 passed; `git diff --check` passed.
- Resolution: added immediate stored-snapshot equality assertions after the new
  closed-period Spend and after each direction of closed-account reassignment.
- Reviewer checks: reviewer reran the exact target — `29 passed`; `git diff
  --check` passed.
- Verdict: changes required; corrected and submitted for fresh re-review.

### Pass 3 — close/expiry final review

- Reviewer task name/vendor: `/root/t004_close_expiry_final_review`, Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed base/head or working-tree manifest: base `96d1368`; complete current
  block working tree including untracked `tests/test_period_lifecycle_v2.py`.
- Findings (verbatim, P0–P3):

  > Final bounded read-only review, base `96d1368`, complete current working-tree manifest including untracked `tests/test_period_lifecycle_v2.py`:
  >
  > P0: None.
  >
  > P1: None.
  >
  > P2: None. The prior coverage gap is closed: the focused lifecycle test now asserts the stored period state immediately after the new post-close Spend and again after Undo; the reassignment regression asserts the four-field stored snapshot immediately after moving a transaction into the closed account and again after moving one out. Direct snapshot comparisons also remain present after Correction, Delete, unassigned-account assignment, reconcile/Adjustment, shared Exchange, and closed-period Undo.
  >
  > P3: None.
  >
  > Production close/expiry behavior remains sound for this bounded block against `ACCOUNT_PERIODS-v2.1.md` §§4–5: status uses the workspace-local date; GET/list do not write natural-expiry state; ended periods retain null closing fields and reject edit/close; manual close is current-only and records one UTC cutoff plus the exact posted-ledger balance in the same transaction without modifying ledger rows; closed lifecycle state no longer permanently blocks otherwise authorized ledger operations, and those paths do not rewrite stored snapshots. Successor selection/creation remains explicitly out of scope for this review.
  >
  > Target evidence supplied and consistent with the inspected manifest: `29 passed`; `git diff --check` passed.
  >
  > Verdict: **APPROVED** for T-004 block 1 (close, expiry, and post-close ledger behavior).
- Resolution: none required.
- Reviewer checks: targeted lifecycle/legacy modules `29 passed`; `git
  diff --check` passed.
- Verdict: approved; prior P2/P3 findings are closed.

### Pass 4 — successor creation review

- Reviewer task name/vendor: `/root/t004_successor_review`, Codex same-vendor
  fallback; cross-vendor reviewer unavailable in this session.
- Reviewed base/head or working-tree manifest: base `e4946bd`; modified
  `app/periods.py`, `tests/test_period_lifecycle_v2.py`, and
  `tests/test_periods_v2.py`.
- Findings (verbatim, P0–P3):

  > Bounded read-only review of `e4946bd..working tree` (`app/periods.py`, `tests/test_period_lifecycle_v2.py`, `tests/test_periods_v2.py`) against T-004 successor acceptance, ACCOUNT_PERIODS-v2.1 §§4–5, and ADR-0005:
  >
  > P0: None.
  >
  > P1 — The same-account current-period guard is still a check-then-insert race under SQLite, so the implementation does not enforce the required invariant atomically. `create_account_period` performs a normal SELECT in `ensure_no_current_period`, then separately reads predecessors/balance and inserts before commit (`app/periods.py:502-529`); `AccountPeriod` has no uniqueness constraint capable of rejecting the second current row (`app/models.py:513-529`), and the default deferred SQLite transaction does not acquire a write lock on those reads (`app/db.py:23-29`). Two concurrent create requests can both observe no current period and both proceed; the new tests cover only sequential rejection (`tests/test_period_lifecycle_v2.py:315-336`). Acquire the SQLite write reservation before the guard/snapshot reads (or provide an equivalent serialization mechanism that remains within the no-schema-change scope), then add a focused concurrent-create test proving exactly one 201 and one conflict and exactly one persisted current row. The guard, predecessor selection, posted-balance snapshot, and insert must all remain in that serialized transaction.
  >
  > P2: None.
  >
  > P3: None.
  >
  > Verdict: **changes required**. Apart from the concurrency defect, the bounded diff correctly permits closed/ended original-range overlaps, keeps accounts independent, chooses the maximum eligible historical close/end boundary, preserves naive-UTC boundary conventions and Decimal ledger reconstruction, and the same-day/manual-close and non-UTC/two-predecessor tests prove equality partitioning as requested. No T-007 start-edit or T-008 API-contract scope drift was introduced. `git diff --check e4946bd -- app/periods.py tests/test_period_lifecycle_v2.py tests/test_periods_v2.py` passed.
- Resolution: `BEGIN IMMEDIATE` now reserves the SQLite writer before account
  guard, predecessor selection, exact posted-balance reconstruction, and
  successor insert; a file-backed scratch SQLite concurrency test proves one
  `201`, one `409`, and exactly one persisted current row.
- Reviewer checks: bounded diff inspection; `git diff --check` passed.
- Verdict: changes required; corrected and submitted for fresh re-review.

### Pass 5 — successor creation re-review

- Reviewer task name/vendor: `/root/t004_successor_rereview`, Codex same-vendor
  fallback; cross-vendor reviewer unavailable in this session.
- Reviewed base/head or working-tree manifest: base `e4946bd`; complete
  successor-block working tree.
- Findings (verbatim, P0–P3):

  > P0: None.
  >
  > P1: None.
  >
  > P2: None.
  >
  > P3: None.
  >
  > Verdict: **APPROVED**.
  >
  > `BEGIN IMMEDIATE` is acquired before all endpoint account-guard, predecessor, balance, and insert operations. Authentication commits the shared request session before handler entry, so the reservation does not nest inside an active auth transaction.
  >
  > The file-backed scratch test uses separate request-scoped sessions with the pooled SQLite engine and concurrent requests. It proves one `201`, one `409`, the expected conflict detail, and exactly one persisted current period.
  >
  > Re-verified:
  >
  > - Lifecycle tests: `8 passed`
  > - Periods + Undo tests: `25 passed`
  > - Bounded `git diff --check`: passed
  > - Same-day/manual-close and natural-expiry boundaries, overlap rules, Decimal precision, timezone handling, and equality partitioning remain correct.
  > - No schema, T-007, or T-008 scope drift.
- Resolution: none required.
- Reviewer checks: lifecycle `8 passed`; periods plus Undo `25 passed`;
  bounded `git diff --check` passed.
- Verdict: approved; prior concurrency P1 is closed.

## Session log

Append-only. Every session that touches this task adds one entry before it
ends. Date · agent · what landed · what is left · open questions.

- 2026-08-09 Codex: drafted the bounded T-004 lifecycle contract on
  `finapp-v2-develop`; readiness review, owner promotion, branch claim, and
  implementation remain; no open question.
- 2026-08-09 Codex: readiness passed at `f03b8e8`, owner promoted the task at
  `74556f7`, and the exact task branch was claimed from that integration HEAD;
  lifecycle implementation and block review remain; no open question.
- 2026-08-09 Codex: pre-implementation inspection found superseded
  closed-period rejection assertions in `tests/test_periods_v2.py` and
  `tests/test_operations_undo_v2.py`; only those regression-test touches and
  their targeted command were added to the task scope for read-only review;
  implementation remains; no open question.
- 2026-08-09 Codex: a complete closed-guard search found additional
  superseded new-Operation, exchange, and account-reassignment assertions in
  the already scoped legacy module; acceptance now names the §4 invariant and
  the regression gate runs both legacy modules unfiltered; implementation
  remains; no open question.
