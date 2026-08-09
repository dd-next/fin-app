---
id: T-004
title: Enforce account-period close, expiry, and successor lifecycle
status: backlog
size: M
spec: specs/ACCOUNT_PERIODS-v2.1.md §4–§5
blocked-by: [T-002]
branch: task/T-004-period-lifecycle
base-commit:
implementer:
readiness-reviewed-by:
readiness-reviewed-commit:
readiness-verdict:
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
- [ ] Closing never creates, edits, deletes, or voids a ledger movement, and
      later Correction, Delete, or Undo cannot rewrite the stored opening or
      closing snapshots.
- [ ] Period creation rejects a second current period on the same account but
      ignores closed and naturally ended predecessors whose original calendar
      ranges overlap the requested successor; periods on different accounts
      remain independent.
- [ ] A same-workspace-day successor is valid immediately after close. Its
      `snapshot_at` is the later of its workspace-local `start_boundary` and
      the latest eligible predecessor close/end boundary, and its
      `opening_balance` is the exact posted balance through that instant.
- [ ] A leg exactly at the predecessor close/successor snapshot boundary is
      included in the predecessor's closed window and successor opening
      snapshot, but excluded from the successor replay window.
- [ ] Natural expiry remains read-only and permits a successor without a
      write-on-read finalization; the ended period's replay window stays
      strictly before its workspace-local end boundary and cannot absorb
      successor-era activity.
- [ ] Focused tests cover workspace-local midnight status, ended close/edit
      rejection, exact manual-close cutoff and snapshot immutability, same-day
      closed successor boundary partitioning, naturally ended successor
      creation, same-account current-period rejection, and different-account
      independence.

## Touches

- `app/periods.py`
- `tests/test_periods_v2.py` or a bounded period-lifecycle test module
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
.venv/bin/python -m pytest tests/test_periods_v2.py -k "lifecycle or close or ended or successor or overlap" -q
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
