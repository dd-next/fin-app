# FinApp v2

FinApp v2 is being built as a multi-asset account ledger with planning and a
daily spending tracker. The authoritative specification is
[`specs/FinnApp-v2.md`](specs/FinnApp-v2.md); active implementation phases are
in [`BUILD_PLAN-v2.md`](BUILD_PLAN-v2.md).

The current checkpoint provides open web registration, secure cookie sessions,
multi-asset accounts, an exact double-entry-style movement ledger, derived
exchange rates, account-level sharing with four roles, and a responsive SPA.
Plan supports recurring rules, occurrence actions, explicit transaction links,
and plan-vs-actual. Tracker provides confirmed income-based periods, frozen
multi-asset valuation, required commitments, exact daily-budget replay, live
expense preview, history, and next-day carry decisions. Analytics intentionally
remains a `Coming soon` placeholder for the first release.

## Install and run

```sh
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000>. API documentation is available at
<http://127.0.0.1:8000/docs>; `GET /health` remains public.

## Test

```sh
.venv/bin/python -m pytest
node --check app/static/app.js
```

The default database is `./finapp.db`. Set `DATABASE_URL` to use another async
SQLAlchemy connection. Existing databases must be upgraded with Alembic before
the app starts.

FinApp v2 intentionally starts with a clean schema. The pre-v2 local database
is preserved under `.backups/`; no legacy financial or authentication rows are
migrated into v2.
