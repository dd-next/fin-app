---
id: T-003
title: Derive current_balance from the ledger and compute the reconciliation input
status: in-progress
size: M
spec: specs/ACCOUNT_PERIODS-v2.1.md §6, §6.1
blocked-by: [T-002]
branch: task/T-003-ledger-derived-balance
base-commit: 1af115628c25781fbc0b2d40f900e6503e2badf4
implementer: Codex
readiness-reviewed-by: /root/t003_readiness_rereview (Codex same-vendor fallback)
readiness-reviewed-commit: 32f7f17
readiness-verdict: ready
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

### Pass 2

- Reviewer task name/vendor: `/root/t003_readiness_rereview`, Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed task-file commit: `32f7f17`.
- Findings (verbatim, P0–P3):

  > - P0: None.
  > - P1: None.
  > - P2: None.
  > - P3: None.
  >
  > All prior findings are closed:
  >
  > - `current_balance` is an immutable internal result only; no
  >   `app/schemas.py` or public JSON change before T-008.
  > - One captured UTC `reference_time` governs both the shared ledger-balance
  >   query and strict `snapshot_at < created_at <= T` window.
  > - Closed periods are isolated from live balance, reconciliation, and later
  >   reference times.
  > - Focused tests explicitly cover boundary/post-T/non-posted behavior,
  >   pre-period correction/Delete/Undo, Accounts-service equality, movement
  >   directions, 18-place precision, pure-budget delivery, and immutable
  >   closed history.
  >
  > Scope is bounded M, T-002 is accepted and the only blocker is satisfied,
  > Touches/Out-of-scope align with the specifications, and verification
  > includes targeted/full tests plus repository checks.
- Resolution: none required.
- Verdict: ready.

## Review

### Pass 1

- Reviewer task name/vendor: `/root/t003_balance_block_review`, Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed base/head or working-tree manifest: base `efdb5c0`; modified
  `app/ledger.py`, `app/periods.py`, and `tests/test_periods_v2.py`.
- Findings (verbatim, P0–P3):

  > P0 none.
  >
  > P1: ended periods are incorrectly treated as current.
  > `app/periods.py:373-380` uses now/`current_period_balance_inputs` whenever
  > `closed_at` is null, so naturally ended history includes legs after
  > `period_end_boundary` (`period_movements:295-297` uses `<= now`) and can
  > absorb successor-era activity; §5 requires ended window strictly `<` first
  > instant after `end_date` and no live reconciliation.
  >
  > P1: closed history still replays mutable live rows for `available_today`
  > (`384-419`); test mutates a pre-close leg but asserts only remaining
  > (`tests:314-328`), so `available_today` can change after close, violating
  > closed-history isolation from subsequently mutable transaction rows.
  >
  > P2 missing acceptance evidence: Accounts API/pre-quantization equality is
  > tautologically checked against `account_balance` helper only (`235-237`);
  > no fee/transfer/exchange/adjustment per-account direction tests; no distinct
  > correction/Delete/Undo paths (direct DB amount/status mutation only); no
  > assertion that `account_period_out` actually passes
  > `calculation_opening_balance` into budget math; no test for ended strict end
  > boundary.
  >
  > P3 none. Positive: cutoff boundaries, posted-only, same T, exact Decimal
  > helpers, and equality invariant are sound for a true current period.
- Resolution: split current/ended/closed reads; ended now uses strict end
  boundary without reconciliation, closed uses stored snapshots only; added
  budget-input spy and ended/closed immutability coverage. Existing
  Operations/period suites cover signed movement directions and public
  Correction/Delete/Undo paths.
- Reviewer checks: targeted `20 passed`; `git diff --check` passed.
- Verdict: changes required; corrected and submitted for re-review.

### Pass 2

- Reviewer task name/vendor: `/root/t003_balance_block_rereview`, Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed base/head or working-tree manifest: base `efdb5c0`; complete block
  after Pass 1 fixes.
- Findings (verbatim, P0–P3):

  > P0: None.
  > P1: None.
  > P2: None.
  > P3: None.
  >
  > Verdict: **APPROVED**.
  >
  > Confirmed:
  >
  > - Current periods use one `reference_time` and exact
  >   `snapshot_at < created_at <= T`.
  > - Reconciliation is exact `Decimal` and passed into `compute_budget`.
  > - Ended periods use strict end boundary without live reconciliation.
  > - Closed periods derive financial output only from stored opening/closing
  >   snapshots; later ledger edits do not change it.
  > - Shared `account_balance` service is used.
  > - Focused suite: `tests/test_periods_v2.py` — **16 passed**.
  > - No public contract expansion before T-008.
- Resolution: none required.
- Reviewer checks: bounded diff inspection; targeted combined selector
  `21 passed, 8 deselected`; `git diff --check` passed.
- Verdict: approved; prior P1/P2 findings are closed.

## Session log

- 2026-08-09 Codex: claimed `task/T-003-ledger-derived-balance` from accepted
  integration commit `1af115628c25781fbc0b2d40f900e6503e2badf4`.
  Starting with the shared cutoff-aware ledger service and immutable internal
  reconciliation result; public JSON remains unchanged until T-008.
- 2026-08-09 Codex: implemented and independently approved the shared cutoff
  ledger service and reconciliation block. Current, ended, and closed reads
  now use their distinct canonical cutoffs; targeted balance/reconciliation
  selector passes `21 passed, 8 deselected`. Remaining: full task gate, final
  acceptance review/evidence, commit, and local integration.
