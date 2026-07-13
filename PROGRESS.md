# PROGRESS.md — build ledger

The agent updates this after every phase.

**To resume in a new session (any model):** read `SPEC.md`, `CLAUDE.md`,
`BUILD_PLAN.md`, then this file, and continue from the first unchecked phase,
following the same conventions.

Status legend: `[ ]` not started · `[~]` in progress · `[x]` done

- [x] Phase 1 — Pure budget core + unit tests
- [ ] Phase 2 — Data layer + API
- [ ] Phase 3 — .xlsx export
- [ ] Phase 4 — Frontend (responsive SPA)
- [ ] Phase 5 — Polish & README

## Log
<!-- Agent: append an entry per phase — what you built, test results (pass/fail), decisions. -->

### Phase 1 — Pure budget core + unit tests (2026-07-13)
- Implemented `app/budget.py`: pure functions (`days_total/elapsed/remaining`,
  `spent_total`, `remaining_money`, `per_day`, `preview_after`) plus a
  `compute_budget()` that derives a full `BudgetSummary` from scratch — no
  hidden state, no DB/framework imports. All money is `Decimal`.
- Wrote `tests/test_budget.py` covering every SPEC §9 edge case: overspend
  (negative, unclamped), last day, past end_date, zero-length period,
  delete-after-increase == fresh recompute, Decimal exactness, preview.
- Tests: **12 passed, 0 failed** (`pytest tests/test_budget.py`).
- Env: Python 3.12.7 venv at `.venv/`, deps in `requirements.txt`.

## Blocked
<!-- Agent: if you get stuck, describe the problem, what you tried, and where you stopped. -->

## Decisions / assumptions
<!-- Agent: record any choice you made where SPEC.md was silent. -->
