---
id: T-006
title: Implement redistribution allowance policy and pure dispatch
status: backlog
size: M
spec: specs/ACCOUNT_PERIODS-v2.1.md §7.2, §7.3
blocked-by: [T-003, T-005]
branch: task/T-006-redistribute-policy
base-commit:
implementer:
readiness-reviewed-by:
readiness-reviewed-commit:
readiness-verdict:
---

## Goal

Pure budget math redistributes the exact start-of-day balance across remaining
days and dispatches both accepted rollover policies through one immutable
result contract.

## Acceptance

- [ ] `app/budget.py` exposes `compute_redistribute_remaining_days` with the
      same plain signed-effect inputs, strict assigned-day validation,
      base-10 asset quantum, and immutable `AllowanceResult` as T-005.
- [ ] For bounded reference day `D`, exact
      `current_balance = pool_start + sum(effects through D)`, `today_net` is
      the exact sum assigned to `D`, and
      `start_of_day_balance = current_balance - today_net`.
- [ ] Exact `daily_base = start_of_day_balance / days_remaining`, where
      `days_remaining = (end_date - D) + 1`; `carry_exact` is always zero and
      `available_before_today_effects_exact = daily_base`.
- [ ] Exact `available_today = daily_base + today_net`; the current-day effect
      is subtracted once before division and added once afterward, so it is
      never double counted. Signed income raises and outflow lowers today's
      amount one-for-one after the start-of-day division.
- [ ] Every new reference day performs a fresh exact redistribution regardless
      of prior under/overspend. The canonical day-two example after day-one
      spend `60` produces exact base `940 / 9`, not carry-policy `140`.
- [ ] Presentation fields use T-005 `ROUND_HALF_UP` asset-precision validation
      without modifying exact fields. Rounding residue remains in
      `current_balance`, and on the final day `available_today_exact` equals the
      complete exact current balance.
- [ ] Negative balances/allowances remain negative, one-day and clamped
      before/after reference dates never divide by zero, invalid date ranges
      and effects outside `start_date..bounded_reference` are rejected, and
      recomputation persists no aggregate.
- [ ] A pure `compute_allowance` dispatcher accepts exactly
      `carry_next_day` and `redistribute_remaining_days`, defaults omitted
      policy to `redistribute_remaining_days`, returns `AllowanceResult`, and
      rejects unknown values deterministically.
- [ ] Dispatching `carry_next_day` is exactly equal to the reviewed T-005
      direct function for the same inputs; T-006 does not duplicate or alter
      carry math.
- [ ] Existing legacy `compute_budget` behavior remains compatible. T-008 will
      replace period-domain calls with explicit signed effects and the new
      dispatcher; T-006 changes no DB, period, schema, route, or UI file.
- [ ] Focused tests cover canonical redistribution versus carry, current-day
      outflow/income exactly once, successive-day under/overspend rebases,
      final-day residue, negative/one-day/date bounds, strict validation,
      both dispatch paths/default/unknown policy, 18-place Decimal and VND/BTC
      presentation precision, deterministic frozen results, and pure imports.

## Touches

- `app/budget.py`
- `tests/test_budget_redistribute_v2.py`
- `docs/tasks/T-006-redistribute-policy.md`
- `docs/BACKLOG.md` and `docs/PROGRESS.md` for task lifecycle state only

## Out of scope

- Period create/edit Start-date replay — T-007.
- `app/periods.py`, request/response schemas, API policy fields, and default
  persistence wiring — T-008.
- RebaseEvent/API removal and removed legacy fields — T-008 and T-009.
- Models, migrations, permissions, UI, and Phase 15.

## Verification

```bash
.venv/bin/python -m pytest tests/test_budget_redistribute_v2.py -q
.venv/bin/python -m pytest tests/test_budget_carry_v2.py tests/test_budget.py -q
.venv/bin/python -m pytest -q
node --check app/static/app.js
git diff --check
git status --short
```

These tests are pure and must not open a database. Any unrelated manual DB
check must use an explicit scratch `DATABASE_URL`.

## Readiness review

Append-only readiness passes against `specs/ACCOUNT_PERIODS-v2.1.md` §7.2 and
§7.3, T-005's reviewed common result, the Decimal baseline in
`specs/FinnApp-v2.md`, and ADR-0005.

## Review

Append-only implementation review passes. A different read-only agent returns
the review; the implementer records it verbatim following
[`../REVIEW_PROTOCOL-v2.md`](../REVIEW_PROTOCOL-v2.md).

## Session log

- 2026-08-09 Codex: drafted bounded T-006 pure redistribution/dispatch after
  local T-005 acceptance; readiness, promotion, claim, implementation, and
  review remain; no open question.
