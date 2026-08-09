---
id: T-007
title: Implement atomic period Start-date snapshot replay
status: backlog
size: M
spec: specs/ACCOUNT_PERIODS-v2.1.md §3, §5, §8; design/MOBILE-BACKEND-GAP-AUDIT.md period start date
blocked-by: [T-002, T-003, T-004]
branch: task/T-007-period-start-replay
base-commit:
implementer:
readiness-reviewed-by:
readiness-reviewed-commit:
readiness-verdict:
---

## Goal

An owner can select a past-or-today Start date when creating a period or
editing a current period, and every edit atomically rebuilds the exact opening
snapshot and replay partition without changing the posted ledger balance.

## Acceptance

- [ ] Creating with an explicit workspace-local Start date in the past or on
      today succeeds, while a future Start date and `end_date < start_date`
      fail before any period row is persisted. The existing create path keeps
      deriving `snapshot_at` and exact `opening_balance`; T-008 owns making an
      omitted Start date default to today.
- [ ] PATCH evaluates lifecycle state before applying the update: a period
      that is current at the start of the serialized operation may change
      `start_date` alone or together with `end_date`; an already ended or
      manually closed period remains read-only. A selected future Start date,
      null field, or resulting `end_date < start_date` is rejected
      deterministically and leaves every stored period field unchanged.
- [ ] A successful Start-date change recomputes `snapshot_at` as the exact
      maximum of the new workspace-local day boundary and every eligible
      same-account closed/naturally-ended predecessor boundary, excluding the
      edited period itself. It then recomputes `opening_balance` from posted
      legs with `created_at <= snapshot_at`, using `Decimal` only.
- [ ] The edit atomically persists the selected dates, recomputed
      `snapshot_at`, and recomputed `opening_balance`. SQLite reserves the
      writer before reading lifecycle state, predecessors, ledger snapshot, or
      successor eligibility; any validation or replay failure rolls back the
      complete update.
- [ ] Replaying the new canonical window changes no `Transaction` or
      `TransactionLeg`, creates no movement, and leaves the exact live account
      balance unchanged. `period_movements` includes every later posted leg
      exactly once, excludes legs at the snapshot boundary, and
      `current_period_balance_inputs` still reconciles opening plus window to
      that unchanged live balance.
- [ ] Backward and forward Start-date moves cover pre-boundary corrections and
      posted/voided legs without double counting. A leg exactly at the new
      snapshot boundary is represented in opening only; a later leg is replayed
      only; 18-place Decimal values remain exact.
- [ ] A same-local-day manually closed predecessor remains the effective
      boundary when later than the selected local-day boundary. Changing the
      successor Start date cannot cross or absorb that accepted predecessor
      window, and the equality leg at the close boundary remains in successor
      opening but outside successor replay.
- [ ] Successor/current-period eligibility is checked in the same serialized
      transaction. Historical closed/ended original-range overlap remains
      permitted, but an accepted distinct same-account current successor is
      never crossed or turned into a second current period; different accounts
      remain independent.
- [ ] Existing end-date-only PATCH behavior remains compatible. The obsolete
      legacy assertion that every Start-date change returns `409` is replaced
      only where the accepted v2.1 contract supersedes it.
- [ ] Focused tests cover create past/today/future and invalid range; backward,
      forward, and simultaneous Start/end edits; already ended/closed rejection;
      exact timezone and same-day predecessor boundaries; exact ledger and
      replay/reconciliation invariants; rollback; successor conflict; different
      accounts; and no row or ledger mutation on rejected input.

## Touches

- `app/periods.py`
- `tests/test_period_start_replay_v2.py`
- `tests/test_periods_v2.py` only for assertions directly superseded by Start
  date replay
- `docs/tasks/T-007-period-start-replay.md`
- `docs/BACKLOG.md` and `docs/PROGRESS.md` for task lifecycle state only

## Out of scope

- Public request/response schema replacement, omitted-Start default wiring,
  `rollover_policy` create/update exposure, allowance dispatch, current/history
  route contract, and lifecycle response cleanup — T-008.
- Removal of `funding_amount`, `remaining`, `planned`, RebaseEvent, and legacy
  confirmation fields — T-009.
- Shared-account owner-private permission redesign — T-010.
- Models, migrations, ledger-operation semantics, UI, Phase 15, or any change
  to stored closed/ended snapshots.

## Verification

```bash
.venv/bin/python -m pytest tests/test_period_start_replay_v2.py -q
.venv/bin/python -m pytest tests/test_periods_v2.py tests/test_period_lifecycle_v2.py -q
.venv/bin/python -m pytest -q
node --check app/static/app.js
git diff --check
git status --short
```

All database-backed tests use the isolated in-memory test fixture. Any
migration or manual database check must set an explicit scratch
`DATABASE_URL`; `finapp.db` is never used.

## Readiness review

Append-only readiness passes against `specs/ACCOUNT_PERIODS-v2.1.md` §3,
§5, §8 and acceptance scenarios 2, 6–7, 12–13, 16–18; the Period Start
date audit row; ADR-0005; T-002–T-004 accepted contracts; AGENTS; BACKLOG; and
REVIEW_PROTOCOL.

## Review

Append-only implementation review passes. A different read-only agent returns
the review; the implementer records it verbatim following
[`../REVIEW_PROTOCOL-v2.md`](../REVIEW_PROTOCOL-v2.md).

## Session log

Append-only. Every session that touches this task adds one entry before it
ends. Date · agent · what landed · what is left · open questions.

- 2026-08-09 Codex: drafted bounded T-007 Start-date replay after local T-006
  acceptance; readiness, promotion, claim, implementation, and review remain.
  Public period API/schema synchronization remains explicitly deferred to
  T-008; no open question.
