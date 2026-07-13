# Tzlvt clone — minimalist daily-budget tracker

Set an amount and a period; the app splits the money across the remaining days
and shows what you can spend **today**. Add an expense and the allowance
recalculates live. Overspending goes negative — no sugar-coating.

Single-user, no auth, no categories. FastAPI + SQLite backend, vanilla-JS
dark UI, `.xlsx` export.

## Install

```sh
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```sh
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000 — set a budget, start spending.

## Test

```sh
pytest
```

## Notes

- Data lives in `./tzlvt.db` (SQLite, created automatically on first run).
- Migrations: `alembic upgrade head` (optional for local dev — the app also
  creates tables on startup).
- Postgres later: set `DATABASE_URL` (see `.env.example`) — nothing else
  changes.
- API docs at http://127.0.0.1:8000/docs; export at `/export.xlsx`.
