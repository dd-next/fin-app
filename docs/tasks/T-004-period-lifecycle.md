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
readiness-reviewed-by: /root/t004_readiness_rereview (Codex same-vendor fallback)
readiness-reviewed-commit: f03b8e8
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
      Delete, and Undo with immutable snapshots; same-day closed successor
      boundary partitioning; same-account current-period rejection; and
      different-account independence.
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
.venv/bin/python -m pytest tests/test_period_lifecycle_v2.py tests/test_periods_v2.py tests/test_operations_undo_v2.py -k "lifecycle or ended_transaction or resulting_period_state or undo_period_guards" -q
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

## Review

Append-only implementation review passes. A different read-only agent returns
the review; the implementer records it verbatim following
[`../REVIEW_PROTOCOL-v2.md`](../REVIEW_PROTOCOL-v2.md).

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
