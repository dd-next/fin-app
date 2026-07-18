# FinApp v2

FinApp v2 is a self-hosted multi-asset account ledger with planning and a
daily spending tracker. The authoritative specification is
[`specs/FinnApp-v2.md`](specs/FinnApp-v2.md); active implementation phases are
in [`BUILD_PLAN-v2.md`](BUILD_PLAN-v2.md).

The first release provides:

- open web registration and opaque server-side cookie sessions;
- exact multi-asset accounts, balances, Net worth, Available, exchange-derived
  rates, and explicit unvalued assets;
- expense, income, transfer, exchange, adjustment, correction, assignment, and
  void commands over a movement ledger;
- per-account sharing with owner, editor, contributor, and viewer roles;
- recurring Plan rules, materialized occurrences, actions, links, and
  plan-vs-actual;
- confirmed income-based Tracker periods, frozen multi-asset valuation,
  commitments, deterministic daily replay, live preview, history, and carry
  decisions;
- a responsive English SPA with Accounts, Transactions, Tracker, Plan, and an
  intentional `Coming soon` Analytics placeholder.

## Install and run

```sh
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000>. API documentation is available at
<http://127.0.0.1:8000/docs>; `GET /health` remains public.

No Redis, worker, queue, or other external service is required. For HTTPS
deployments set `COOKIE_SECURE=true`.

## Database and migration

The default database is `./finapp.db`. Use an absolute async SQLite URL for an
isolated database, for example:

```sh
DATABASE_URL=sqlite+aiosqlite:////tmp/finapp-v2.db alembic upgrade head
DATABASE_URL=sqlite+aiosqlite:////tmp/finapp-v2.db uvicorn app.main:app
```

Run `alembic upgrade head` before starting after pulling schema changes. The v2
migration chain supports its own revisions `0001_v2` through `0005_v2`.
FinApp v2 intentionally began with a clean schema: pre-v2 financial and auth
rows are not imported. The original local database was preserved under
`.backups/` before reset.

## Test

```sh
.venv/bin/python -m pytest -q
node --check app/static/app.js
.venv/bin/pip check
```

Tests use isolated in-memory or temporary databases and do not write test data
to `finapp.db`. The Russian end-to-end checklist is
[`specs/MANUAL_TEST_CASES-v2.md`](specs/MANUAL_TEST_CASES-v2.md).

## First-release boundary

Blockchain/exchange synchronization, full Analytics reports, XLSX export,
external market-rate providers, bank APIs, Telegram, Google Sheets, pools,
goals, and category limits are future work, not partially enabled features.
