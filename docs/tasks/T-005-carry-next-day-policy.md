---
id: T-005
title: Implement exact carry-next-day allowance policy
status: backlog
size: M
spec: specs/ACCOUNT_PERIODS-v2.1.md §7.1, §7.3
blocked-by: [T-003]
branch: task/T-005-carry-next-day-policy
base-commit:
implementer:
readiness-reviewed-by:
readiness-reviewed-commit:
readiness-verdict:
---

## Goal

Pure budget math computes `carry_next_day` from exact signed account-leg
effects without hidden state, persistence, or intermediate rounding.

## Acceptance

- [ ] `app/budget.py` exposes a bounded `carry_next_day` calculation that
      accepts `Decimal pool_start`, inclusive start/end dates, dated signed
      balance effects (`negative=outflow`, `positive=inflow`), reference day,
      and asset quantum; it imports no database or web-framework module.
- [ ] The initial exact `daily_base` is `pool_start / days_total` and carry is
      zero. For every completed day with
      `available_end = daily_base + carry + net_day >= 0`, the complete exact
      `available_end` becomes next-day carry and `daily_base` is unchanged.
- [ ] Consecutive unused allowances accumulate only into the next day: the
      canonical `100` base example produces day-two `140` after day-one spend
      `60`, then day-three `240` after day-two spend `0`; unused money is not
      redistributed over all future days.
- [ ] When a completed day has `available_end < 0`, carry resets to zero and
      the next exact daily base is `balance_after_day / days_after_that_day`;
      repeated overspends reapply that rule from the newly rebased pool.
- [ ] Current-day signed effects are applied exactly once to both live balance
      and `available_today`; income raises and outflow lowers today's amount.
- [ ] Exact pool/balance values are never quantized internally. Presentation
      fields use `ROUND_HALF_UP` at the supplied positive finite asset quantum,
      and rounding residue remains in the exact balance.
- [ ] Negative balances and allowances remain negative, a one-day period never
      divides by zero, and before/after-range reference dates remain bounded to
      a real inclusive period day.
- [ ] Recomputing from the same plain inputs is deterministic and persists no
      daily aggregate. The new policy function has no `rebase_days` or other
      ad hoc user-triggered rebase input.
- [ ] Existing `compute_budget` callers and tests remain compatible during
      T-005; policy dispatch and `redistribute_remaining_days` land in T-006,
      and the period domain/API switches to explicit `rollover_policy` only in
      T-008.
- [ ] Focused tests cover the canonical carry sequence, exact-spend boundary,
      first and repeated overspends, signed income/outflow, negative pool,
      one-day/before/after bounds, 18-place Decimal precision, non-cent asset
      quantums, deterministic recomputation, and absence of DB/framework
      imports or a rebase-event argument.

## Touches

- `app/budget.py`
- `tests/test_budget_carry_v2.py`
- `docs/tasks/T-005-carry-next-day-policy.md`
- `docs/BACKLOG.md` and `docs/PROGRESS.md` for task lifecycle state only

## Out of scope

- `redistribute_remaining_days` and final policy dispatch/default — T-006.
- Period create/edit request fields and Start-date replay — T-007.
- `app/periods.py`, public schemas/routes, RebaseEvent removal, and API response
  naming — T-008 and T-009.
- Database models, migrations, permissions, UI, and Phase 15.

## Verification

```bash
.venv/bin/python -m pytest tests/test_budget_carry_v2.py -q
.venv/bin/python -m pytest tests/test_budget.py -q
.venv/bin/python -m pytest -q
node --check app/static/app.js
git diff --check
git status --short
```

All tests are pure and must not open a database. If an unrelated manual DB
check becomes necessary, it must set an explicit scratch `DATABASE_URL`.

## Readiness review

Append-only readiness passes. The reviewer checks this definition against
`specs/ACCOUNT_PERIODS-v2.1.md` §7.1 and §7.3, the Decimal/rounding baseline
in `specs/FinnApp-v2.md`, and
`decisions/ADR-0005-periods-are-optional-and-ledger-derived.md`.

## Review

Append-only implementation review passes. A different read-only agent returns
the review; the implementer records it verbatim following
[`../REVIEW_PROTOCOL-v2.md`](../REVIEW_PROTOCOL-v2.md).

## Session log

Append-only. Every session that touches this task adds one entry before it
ends. Date · agent · what landed · what is left · open questions.

- 2026-08-09 Codex: drafted the bounded pure-math T-005 contract on
  `finapp-v2-develop` after local T-004 acceptance; readiness review, owner
  promotion, branch claim, and implementation remain; no open question.
