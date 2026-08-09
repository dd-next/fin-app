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
readiness-reviewed-by: /root/t005_readiness_rereview (Codex same-vendor fallback)
readiness-reviewed-commit: 6f4bf30
readiness-verdict: ready
---

## Goal

Pure budget math computes `carry_next_day` from exact signed account-leg
effects without hidden state, persistence, or intermediate rounding.

## Acceptance

- [ ] `app/budget.py` exposes a bounded `carry_next_day` calculation that
      accepts `Decimal pool_start`, inclusive start/end dates, dated signed
      balance effects (`negative=outflow`, `positive=inflow`), reference day,
      and asset quantum; it imports no database or web-framework module.
- [ ] The pure common result is an immutable `AllowanceResult` usable by
      T-006 policy dispatch. It exposes integer `days_total` and
      `days_remaining`; exact Decimal `current_balance`, `daily_base_exact`,
      `carry_exact`, `available_before_today_effects_exact`, `today_net`, and
      `available_today_exact`; and presentation-quantized Decimal `daily_base`
      and `available_today`. T-005 does not add these fields to a public schema.
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
- [ ] Exact result fields are never quantized internally. Presentation fields
      use `ROUND_HALF_UP` at a supplied base-10 asset-precision quantum of the
      form `1E-n` (including `1`, with `n >= 0`); non-finite, non-positive, or
      non-power-of-ten quantums are rejected, and rounding residue remains in
      the exact balance.
- [ ] The reference day is clamped into the inclusive period. Every supplied
      effect must already be assigned to a day from `start_date` through that
      bounded reference day; an effect before start, after end, or after the
      bounded reference day is rejected instead of ignored or transplanted.
      T-008 owns canonical financial-day clamping before calling policy math.
- [ ] Negative balances and allowances remain negative, a one-day period never
      divides by zero, and `end_date < start_date` raises a deterministic
      `ValueError` before any division.
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
      quantums, invalid range/quantum validation, rejection of pre-start,
      post-end, and post-reference effects, deterministic recomputation, and
      absence of DB/framework imports or a rebase-event argument.

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

### Pass 1

- Reviewer task name/vendor: `/root/t005_readiness_review`, Codex same-vendor
  fallback; cross-vendor reviewer unavailable in this session.
- Reviewed task-file commit: `11fa77f`.
- Findings (verbatim, P0–P3):

  > Readiness verdict for `11fa77f8cf11ed94534af954b1b9837826b6111a`: **NOT READY**.
  >
  > P0: No findings.
  >
  > P1 — `docs/tasks/T-005-carry-next-day-policy.md:23-57` does not define the pure function’s return contract. It names inputs and formulas, but not a result type or named fields, which fields stay exact, which are presentation-quantized, or whether exact `current_balance`, `daily_base`, carry/available-before-effects, `available_today`, and day counts are returned. Lines 38–42 require current-day effects to change “live balance” and “presentation fields” without identifying either as an observable result. T-006 therefore cannot dispatch both policies through a checkable common contract without making a new domain/API-adjacent design decision during implementation. Add an explicit policy-result shape and exact-versus-rounded semantics while keeping public schemas/routes deferred to T-008.
  >
  > P1 — `docs/tasks/T-005-carry-next-day-policy.md:23-26,43-45,53-57` leaves dated-effect membership undefined. The reference day is clamped, but the task never says what happens to effects before `start_date`, after `end_date`, or after the bounded reference day. The existing `compute_budget` clamps such entries onto another day, so an implementation could silently transplant signed ledger effects and still satisfy the current text, violating the specification’s assigned-day and exactly-once semantics. State the accepted input domain and required reject/ignore behavior, and add focused tests for out-of-range/future effects.
  >
  > P2 — `docs/tasks/T-005-carry-next-day-policy.md:23-26,43-45` does not specify behavior for `end_date < start_date`. A pure function can otherwise divide by zero or a negative day count; the one-day test does not cover an invalid range. Require deterministic validation and a focused test, or explicitly document this as a caller precondition with a tested guard at the boundary.
  >
  > P2 — `docs/tasks/T-005-carry-next-day-policy.md:40-42` says any positive finite Decimal is an asset quantum, but Decimal `quantize()` rounds to the operand’s exponent, not arbitrary increments such as `0.05`. Constrain the quantum to the supported base-10 precision form (`1E-n`, including `1`) and test rejection, or specify and test true increment rounding.
  >
  > P3: No findings.
  >
  > The separate pure carry-policy function while retaining legacy `compute_budget` is a safe bounded intermediate: T-005 stays isolated from period domain/API callers and preserves compatibility. It becomes ready once the common result boundary and input validation/membership rules are checkable.
  >
  > Review was read-only; no files changed.
- Resolution: defined the common immutable exact/presentation result contract,
  strict assigned-effect domain, invalid range behavior, base-10 quantum
  validation, and the corresponding focused tests.
- Verdict: not ready; corrected and submitted for fresh readiness review.

### Pass 2

- Reviewer task name/vendor: `/root/t005_readiness_rereview`, Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed task-file commit: `6f4bf30`.
- Findings (verbatim, P0–P3):

  > Readiness verdict for `6f4bf301cdf99e4e8c8fd614f14f2b49669e1203`: **READY**.
  >
  > P0: No findings.
  >
  > P1: No findings.
  >
  > P2: No findings.
  >
  > P3: No findings.
  >
  > The prior findings are closed: the task now defines immutable `AllowanceResult` exact and presentation fields; rejects effects before start, after end, or after the bounded reference date; requires deterministic `ValueError` for `end_date < start_date`; restricts quantum to positive finite base-10 `1E-n` (including `1`) and names focused validation tests. The separate pure carry-policy function preserves legacy `compute_budget` compatibility; T-006 owns redistribution/dispatch and T-008 owns financial-day clamping plus domain/API integration. Goal, dependencies, Touches/Out-of-scope, and verification are bounded against ACCOUNT_PERIODS-v2.1 §§7.1/7.3, Decimal baseline, ADR-0005, BACKLOG, AGENTS, and review protocol. `git diff --check 6f4bf30^ 6f4bf30` passed; worktree is clean. Documentation-only review, so no tests were required.
  >
  > Review was read-only; no files changed.
- Resolution: none required.
- Verdict: ready.

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
