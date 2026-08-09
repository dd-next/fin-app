---
id: T-003
title: Derive current_balance from the ledger and compute the reconciliation input
status: backlog
size: M
spec: specs/ACCOUNT_PERIODS-v2.1.md §6, §6.1
blocked-by: [T-002]
branch: task/T-003-ledger-derived-balance
base-commit:
implementer:
readiness-reviewed-by:
readiness-reviewed-commit:
readiness-verdict:
---

## Goal

A current period reports the account's posted ledger balance as
`current_balance`, and the pure budget layer receives a derived
`calculation_opening_balance` that absorbs later changes to pre-period ledger
truth exactly once.

## Acceptance

- [ ] An immutable internal period-balance result exposes `current_balance`
      from the same ledger service the Accounts API uses, and the two agree
      exactly before API quantization. T-008 exposes this exact result in JSON;
      T-003 does not change `app/schemas.py` or the public response.
- [ ] The internal result field is named `current_balance`, not `remaining` or
      `account_balance`, so T-008 does not rename or recompute it.
- [ ] Every signed financial leg affects its own account in the correct
      direction, including fees, transfers, exchanges, and adjustments.
- [ ] Correction, Delete, and Undo recompute the value from posted signed legs
      rather than adjusting a stored aggregate.
- [ ] Each current-period read captures one UTC `reference_time` `T` and uses
      that same value for both ledger balance and window queries.
- [ ] `window_net` sums exact signed posted legs using
      `snapshot_at < leg.created_at <= T`; equality at `snapshot_at` belongs to
      `opening_balance`, a leg after `T` is excluded from both queries, and a
      non-posted leg is excluded.
- [ ] `reconciliation_delta = current_balance - (opening_balance + window_net)`
      is computed on read and stored nowhere.
- [ ] `calculation_opening_balance + window_net == current_balance` holds
      exactly, including after a corrected pre-period leg.
- [ ] Closed history uses stored opening/closing snapshots and never
      substitutes the live account balance, reconciliation delta, or a later
      reference time.
- [ ] `app/budget.py` imports no database or web-framework module; inputs are
      plain Decimal data.
- [ ] Focused tests prove exact-boundary partitioning, post-`T` and non-posted
      exclusion, pre-period correction/Delete/Undo without double counting,
      Accounts-service equality, per-account fee/transfer/exchange/adjustment
      direction, 18-place Decimal reconciliation, delivery of
      `calculation_opening_balance` into pure budget math, and immutable closed
      history after later ledger edits.

## Touches

- `app/periods.py`
- `app/ledger.py`
- `app/budget.py` — pure input signature only
- `tests/` — reconciliation and drift tests

## Out of scope

- Rollover-policy calculations — T-005 and T-006.
- Public API response shape, including adding `current_balance` to JSON — T-008.
- Recalculation of immutable closed snapshots.

## Verification

```bash
.venv/bin/python -m pytest tests/ -k "balance or reconcil or period" -q
.venv/bin/python -m pytest -q
git status --short
git diff --check
```

The session log names the exact test proving the reconciliation invariant after
a pre-period correction.

## Readiness review

### Pass 1

- Reviewer task name/vendor: `/root/t003_readiness_review`, Codex same-vendor
  fallback; cross-vendor reviewer unavailable in this session.
- Reviewed task-file commit: `1d6efd6`.
- Findings (verbatim, P0–P3):

  > P0: None.
  >
  > P1 — Contract boundary is contradictory. Acceptance requires the exact
  > name `current_balance`, while public API response changes are explicitly
  > deferred to T-008. For T-003, an internal immutable domain/result structure
  > named `current_balance` is sufficient, tested directly; `app/schemas.py`
  > and public JSON must remain unchanged. T-008 should later expose that same
  > value unchanged.
  >
  > P1 — Reference time `T` is undefined. Capture one `T` per current-period
  > read and use it consistently for both ledger balance and window queries:
  > posted legs only, `snapshot_at < created_at <= T`. Closed periods must use
  > stored opening/closing snapshots and must not receive live balance or
  > reconciliation substitution.
  >
  > P2 — Required tests are underspecified. Add explicit tests for:
  >
  > - exact snapshot-boundary inclusion only in opening;
  > - exclusion of legs after `T` and non-posted legs;
  > - pre-period correction/Delete/Undo without double counting;
  > - same ledger service and exact pre-quantization equality with Accounts;
  > - fee/transfer/exchange/adjustment direction per account;
  > - high-precision Decimal reconciliation;
  > - `calculation_opening_balance` actually passed into pure budget math;
  > - closed history remaining unchanged after later ledger edits.
  >
  > P3: None.
- Resolution: internal/public boundary, one-reference-time rule, closed-history
  isolation, and the focused test matrix are now explicit.
- Verdict: not ready; corrected and submitted for fresh readiness review.

## Review

### Pass 1

- Reviewer task name/vendor:
- Reviewed base/head or working-tree manifest:
- Findings (verbatim, P0–P3):
- Resolution:
- Reviewer checks:
- Verdict:

## Session log

- (empty)
