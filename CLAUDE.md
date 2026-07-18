# CLAUDE.md — working agreement for FinApp v2

The primary product and technical specification for this branch is
`specs/FinnApp-v2.md`. Read it first, then `BUILD_PLAN-v2.md`, then
`PROGRESS.md`. Older files in `specs/` and `BUILD_PLAN.md` are historical
references only. If they conflict with the v2 specification, v2 wins.

## Tech stack

- Python 3.12, FastAPI, Pydantic v2.
- SQLAlchemy 2.x async ORM and Alembic.
- SQLite through `aiosqlite` for local development.
- `pytest` and `httpx` for automated tests.
- Plain HTML, CSS and vanilla JavaScript; no frontend build step.

Do not deviate from the stack without recording the reason in `PROGRESS.md`.

## Hard rules

- The health endpoint is exactly `/health`.
- Money and rates always use `Decimal`, never `float`.
- Asset precision is explicit; ledger storage must support crypto precision.
- Account balances and totals are derived from posted ledger movements.
- Keep daily-budget calculations in `app/budget.py` pure: no DB or framework
  imports.
- All product and technical specifications live in `specs/`.
- The public application API uses `/api/v1`.
- UI copy is English only.
- Do not add Redis, Celery, Prometheus, a queue, or a background worker.
- Google Sheets, Telegram Mini App, XLSX export, crypto sync, savings goals,
  category limits, pools, and full analytics are outside the first v2 release.
- Do not add dependencies that are not used.

## V2 reset rule

V2 starts with a clean database and a new Alembic history. No legacy rows are
migrated. Before replacing or deleting the local `finapp.db`, create a
timestamped recoverable copy inside `.backups/` and record it in `PROGRESS.md`.

## Workflow

Work strictly phase by phase from `BUILD_PLAN-v2.md`; do not skip ahead.

After every phase:

1. Run the phase tests and the complete test suite.
2. Update `PROGRESS.md` with status, 2–4 lines of work completed, exact test
   results, and decisions or assumptions.
3. Commit with `v2 phase N: <short summary>`.

If blocked, record the blocker and attempted fixes in `PROGRESS.md`, commit a
clean runnable state, and stop. The app and tests must be runnable at the end
of every phase.

## Definition of done

All first-release acceptance criteria in `specs/FinnApp-v2.md` are met, the
full automated suite passes, the SPA passes scratch-database browser checks at
phone and desktop widths, and README documents install, run, migrate, and test.
