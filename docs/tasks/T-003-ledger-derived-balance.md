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

- [ ] `current_balance` is produced by the same ledger service the Accounts API
      uses, and the two agree exactly before API quantization.
- [ ] The value is named `current_balance`, not `remaining` or
      `account_balance`.
- [ ] Every signed financial leg affects its own account in the correct
      direction, including fees, transfers, exchanges, and adjustments.
- [ ] Correction, Delete, and Undo recompute the value from posted signed legs
      rather than adjusting a stored aggregate.
- [ ] `window_net` sums exact signed posted legs using
      `snapshot_at < leg.created_at <= T`; equality at `snapshot_at` belongs to
      `opening_balance` and is never replayed.
- [ ] `reconciliation_delta = current_balance - (opening_balance + window_net)`
      is computed on read and stored nowhere.
- [ ] `calculation_opening_balance + window_net == current_balance` holds
      exactly, including after a corrected pre-period leg.
- [ ] Closed history uses stored opening/closing snapshots and never
      substitutes the live account balance.
- [ ] `app/budget.py` imports no database or web-framework module; inputs are
      plain Decimal data.

## Touches

- `app/periods.py`
- `app/ledger.py`
- `app/budget.py` — pure input signature only
- `tests/` — reconciliation and drift tests

## Out of scope

- Rollover-policy calculations — T-005 and T-006.
- Public API response shape — T-008.
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
