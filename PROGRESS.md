# PROGRESS.md — build ledger

The agent updates this after every phase.

**To resume in a new session (any model):** read `SPEC.md`, `CLAUDE.md`,
`BUILD_PLAN.md`, then this file, and continue from the first unchecked phase,
following the same conventions.

Status legend: `[ ]` not started · `[~]` in progress · `[x]` done

- [x] Phase 1 — Pure budget core + unit tests
- [x] Phase 2 — Data layer + API
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

### Phase 2 — Data layer + API (2026-07-13)
- Built `app/db.py` (async engine + session, `DATABASE_URL` env override),
  `app/models.py` (Period/Expense, FK cascade), `app/schemas.py`,
  `app/main.py` with all SPEC §5 endpoints except `/export.xlsx`.
- Alembic set up (async env.py); migration `0001` creates both tables.
  Verified `alembic upgrade head` works against a fresh DB; app also does an
  idempotent `create_all` on startup for zero-setup dev.
- Fixed: SQLite FK enforcement is off by default → replacing a period left
  orphan expenses that collided with the reused rowid. Added a
  `PRAGMA foreign_keys=ON` connect listener in `app/db.py`.
- Tests: **23 passed, 0 failed** (12 budget + 11 API). Boot smoke-tested:
  `/health` → 200 ok, `/period` → 404 when none.
- Decisions: (a) money stored as TEXT on SQLite via a `Money` TypeDecorator
  (SQLite NUMERIC is float and would break Decimal exactness; real
  `Numeric(12,2)` on Postgres — still just a connection-string change);
  (b) amounts must have ≤ 2 decimal places (Pydantic `decimal_places=2`);
  (c) `POST /period` hard-deletes the old period + its expenses (SPEC: "at
  most one active period", no cross-period history in scope);
  (d) response shapes: `POST/GET /period` → `{period, budget}`,
  `POST /expenses` → `{expense, budget}`, `DELETE /expenses/{id}` → budget;
  (e) `greenlet` added to requirements (SQLAlchemy async needs it; not
  auto-installed on macOS arm64).

## Blocked
<!-- Agent: if you get stuck, describe the problem, what you tried, and where you stopped. -->

## Decisions / assumptions
<!-- Agent: record any choice you made where SPEC.md was silent. -->
