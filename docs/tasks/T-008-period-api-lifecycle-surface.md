---
id: T-008
title: Synchronize the period API and lifecycle response surface
status: backlog
size: M
spec: specs/ACCOUNT_PERIODS-v2.1.md §6–§9; design/MOBILE-BACKEND-GAP-AUDIT.md period API rows
blocked-by: [T-004, T-005, T-006, T-007]
branch: task/T-008-period-api-lifecycle-surface
base-commit:
implementer:
readiness-reviewed-by:
readiness-reviewed-commit:
readiness-verdict:
---

## Goal

The owner-facing period API exposes the accepted current/history lifecycle,
live ledger balance, and both exact allowance policies through the existing
`/api/v1` routes, while leaving only the bounded legacy-field removal to T-009.

## Acceptance

- [ ] `AccountPeriodCreate` accepts required `end_date`, optional
      `start_date`, and optional `rollover_policy`; omitted Start resolves to
      the serialized workspace-local today and omitted policy resolves to
      `redistribute_remaining_days`. Explicit null, future Start, invalid date
      order, and unknown/null policy return deterministic `422` without a row.
- [ ] Create no longer requires `funding_amount`; `snapshot_at` and exact
      `opening_balance` remain server-derived by the accepted T-004/T-007
      transaction. As a bounded T-009 handoff only, a supplied legacy
      `funding_amount` may still parse but is ignored and cannot affect any
      stored or returned financial value; T-009 removes it and makes it an
      extra-field rejection.
- [ ] Explicit create policy `carry_next_day` or
      `redistribute_remaining_days` persists exactly; omission persists
      redistribution. Existing atomic current-period, predecessor,
      chronological-boundary, and Decimal snapshot guards remain unchanged.
- [ ] PATCH accepts optional `start_date`, `end_date`, and `rollover_policy`,
      requires at least one of those three business fields, rejects null or an
      unknown policy, and preserves T-007 atomic Start replay and lifecycle
      rules. Changing policy commits no Transaction/TransactionLeg/RebaseEvent
      and leaves exact account/current balance unchanged.
- [ ] Response schemas distinguish `current` from `ended|closed`. Every shape
      returns common historical facts: id, account, asset, creator, dates,
      exact `snapshot_at`/`opening_balance`, policy, status, created/close
      timestamps, and nullable `closing_balance` with the accepted close-pair
      invariant.
- [ ] A current response additionally returns exact ledger-derived
      `current_balance` and presentation-quantized `available_today`. An ended
      or closed response returns neither live field, never substitutes a later
      account balance, and preserves ended null close fields versus a manual
      close snapshot.
- [ ] Until T-009, `funding_amount`, `remaining`, and `planned` may remain only
      as explicitly transitional response members needed by existing callers.
      They are not sources for `opening_balance`, `current_balance`, or
      `available_today`; T-008 introduces no new legacy use and does not claim
      final §10/scenario-23 removal.
- [ ] `GET /api/v1/accounts/{account_id}/periods/current` returns the one
      current object or HTTP `200` JSON `null`. It performs no lifecycle write,
      ignores ended/closed rows, uses workspace-local today, preserves owner
      404 redaction, and never fabricates zero/N/A values.
- [ ] `GET /accounts/{account_id}/periods?scope=history`, account-period detail,
      PATCH, close, and create return the lifecycle-appropriate schema.
      Existing `scope=all|current` behavior may remain as a desktop-compatible
      superset, but every item uses the same status-aware response rules.
- [ ] Current allowance integration calls the accepted pure
      `compute_allowance` dispatcher with `calculation_opening_balance` from
      T-003, the stored policy, asset quantum, and signed posted window effects
      exactly once. `app/budget.py` remains unchanged and free of DB/framework
      imports.
- [ ] Effective financial days clamp every window effect before dispatch:
      dates before `start_date` map to Start, dates after the current replay day
      map to that replay day, and in-range dates remain unchanged. Boundary
      equality stays in opening only; voided/non-window legs do not enter
      effects; reconciliation delta enters only through the calculation
      opening pool.
- [ ] The dated Asia/Ho_Chi_Minh VND fixture returns exact
      `opening_balance=6000000`, `current_balance=5980000`, redistribution base
      `5672269/15`, and API `available_today=685882` at VND precision, without
      Planned input or hard-coded response constants.
- [ ] Both policies cover current-day income/outflow exactly once, pre-period
      correction reconciliation, negative balances, one-day periods,
      timezone/boundary clamping, and 18-place Decimal precision. Dispatch
      results are derived on read and persist no daily aggregate.
- [ ] Spending above `available_today`, including repeated overspend, remains
      accepted under normal Operations permissions; account/current balance
      changes normally and the recalculated allowance may be negative. No
      period value is used as an authorization limit.
- [ ] Focused tests cover create defaults/explicit policies/validation and
      ignored transitional funding; policy-only and combined PATCH with
      mutation-neutral ledger assertions; current object/null; ended/closed
      response separation; history/detail/create/patch/close schemas; VND
      fixture; signed/clamped/reconciled effects; both policies and Decimal
      edges; overspend; route 404 isolation; and legacy regression boundaries.

## Touches

- `app/schemas.py`
- `app/periods.py`
- `tests/test_period_api_v21.py`
- existing period tests only where the additive/status-aware API supersedes an
  assertion
- `docs/tasks/T-008-period-api-lifecycle-surface.md`
- `docs/BACKLOG.md` and `docs/PROGRESS.md` for task lifecycle state only

## Out of scope

- Final rejection/removal of `funding_amount`, `remaining`, `planned`, the
  legacy confirmation field, RebaseEvent contract/storage, and Period-to-Plan
  queries — T-009.
- New permission semantics or shared-role redaction changes — T-010; existing
  owner-private behavior must not regress.
- Models, migrations, ledger command semantics, Plan behavior, UI, Phase 15,
  or changes to accepted T-004/T-007 lifecycle/snapshot rules.
- Changes to pure formulas in `app/budget.py`; T-005/T-006 are consumed as-is.

## Verification

```bash
.venv/bin/python -m pytest tests/test_period_api_v21.py -q
.venv/bin/python -m pytest tests/test_budget_carry_v2.py tests/test_budget_redistribute_v2.py -q
.venv/bin/python -m pytest tests/test_periods_v2.py tests/test_period_lifecycle_v2.py tests/test_period_start_replay_v2.py -q
.venv/bin/python -m pytest -q
node --check app/static/app.js
git diff --check
git status --short
```

All DB-backed tests use isolated in-memory or `tmp_path` file-backed fixtures.
Any migration/manual database command must set an explicit scratch
`DATABASE_URL`; `finapp.db` is never used.

## Readiness review

Append-only readiness passes against `specs/ACCOUNT_PERIODS-v2.1.md`
§6–§9 and acceptance scenarios 3, 9–15, 19–20, 22, 25; the audit rows for
source of money, allowance fixture, rollover selection, and informational
Available today; ADR-0005; accepted T-003–T-007; AGENTS; BACKLOG; and
REVIEW_PROTOCOL. Scenario 23 and final §10 separation remain assigned to
T-009, and scenario 24 permission hardening remains assigned to T-010.

## Review

Append-only implementation review passes. A different read-only agent returns
the review; the implementer records it verbatim following
[`../REVIEW_PROTOCOL-v2.md`](../REVIEW_PROTOCOL-v2.md).

## Session log

Append-only. Every session that touches this task adds one entry before it
ends. Date · agent · what landed · what is left · open questions.

- 2026-08-09 Codex: drafted bounded T-008 API/lifecycle integration after
  local T-007 acceptance. The new contract is additive until T-009 removes the
  three legacy fields; permission changes remain T-010. Readiness, promotion,
  claim, implementation, and review remain; no open question.
