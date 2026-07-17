# AGENTS.md — working agreement for this repo

You are building the app described in `specs/SPEC.md` and its numbered
addenda. Read `specs/SPEC.md` first, then `BUILD_PLAN.md`. This file defines
HOW you work.

## Tech stack (do not deviate without recording a reason in PROGRESS.md)
- Python 3.12, FastAPI, Pydantic v2.
- SQLAlchemy 2.x async ORM + Alembic for migrations.
- Database: **SQLite via aiosqlite** for local dev (zero setup, so the app runs
  and tests pass with no external services). Keep the DB layer clean so switching
  to Postgres later is only a connection-string change.
- `openpyxl` for the `.xlsx` export.
- `pytest` + `httpx` for tests.
- Frontend: plain HTML / CSS / vanilla JS, single small bundle, no build step
  preferred. Consult the **frontend-design** skill when styling the UI.

## Conventions (hard rules)
- The health-check endpoint is exactly `/health` — never `/healthz`.
- Workspace-scoped multi-user behavior is defined by
  `specs/SPEC-4-family-finance.md`. Bank accounts remain out of scope.
- Do NOT add Redis, Celery, or Prometheus. No message queues, no background
  workers. This app does not need them.
- Money is always `Decimal`, never `float`.
- Keep the budget math in `app/budget.py` as pure functions with no DB or
  framework imports.
- Don't add dependencies you don't actually use.

## Project layout (target)
    app/
      main.py          # FastAPI app + routes
      budget.py        # pure calculation module (no DB / framework imports)
      models.py        # SQLAlchemy models
      schemas.py       # Pydantic schemas
      db.py            # async engine / session
      export.py        # xlsx builder
      static/          # frontend (index.html, style.css, app.js)
    alembic/           # migrations
    tests/
      test_budget.py
      test_api.py
      test_export.py
    README.md
    specs/             # all product/technical specifications
    pyproject.toml     # or requirements.txt

## Workflow rules (critical for resumability)
Work phase by phase as listed in `BUILD_PLAN.md`. Do not skip ahead.

Use git. Initialize a repo if none exists. **After finishing each phase:**
1. Run the tests for that phase and make them pass.
2. Update `PROGRESS.md`: check off the phase, write 2–4 lines on what you did,
   paste the test result (pass/fail counts), and note any decision or assumption
   you made.
3. Commit with a message like `phase N: <short summary>`.

If you hit an error you cannot resolve, write it in `PROGRESS.md` under
"Blocked" with what you tried, commit, and stop cleanly — do not leave the repo
half-broken.

Prefer small, working increments over large unfinished ones. The repo should be
runnable at the end of every phase: later phases may leave the frontend
incomplete, but the backend + tests must stay green.

After the final phase, make sure `README.md` lets a new person install, run, and
test in a handful of commands.

## Definition of done
All acceptance criteria in `specs/SPEC.md` and its active addenda are met and
all tests pass.
