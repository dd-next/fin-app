---
name: verify
description: Launch and drive this app end-to-end (FastAPI + SPA) to verify a change against a scratch DB, without touching tzlvt.db.
---

# Verify this app end-to-end

## Launch (isolated — never against the repo's tzlvt.db)

```sh
DATABASE_URL="sqlite+aiosqlite:////ABS/PATH/scratch.db" \
  .venv/bin/uvicorn app.main:app --port 8765 --log-level warning &
curl -s http://127.0.0.1:8765/health   # {"status":"ok"} when up
```

`app/db.py` reads `DATABASE_URL`; four slashes = absolute path.

## Drive

```sh
curl -s -X POST :8765/period -H 'Content-Type: application/json' \
  -d '{"total_amount":"1000","start_date":"2026-07-14","end_date":"2026-07-23"}'
curl -s -X POST :8765/expenses -d '{"amount":"90","comment":"x"}' -H 'Content-Type: application/json'
curl -s ":8765/budget?pending=50"        # live preview
curl -s :8765/export.xlsx -o /tmp/e.xlsx # read back with .venv openpyxl
```

Multi-day states: start the period in the past, and/or backdate expenses by
writing to the scratch DB directly:

```sh
sqlite3 scratch.db "INSERT INTO expense (period_id, amount, comment, created_at)
  VALUES (1, '250', 'yesterday', '2026-07-14 12:00:00.000000');"
```

Gotchas: amounts are stored as TEXT; `POST /period` deletes + recreates the
period so SQLite **reuses rowid 1** — always `SELECT id FROM period` first
(the sqlite3 CLI does not enforce the FK, so a wrong period_id silently
creates an invisible orphan row).

## UI pixels (headless Chrome works on this machine)

```sh
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless=new --disable-gpu --hide-scrollbars --window-size=480,900 \
  --virtual-time-budget=4000 --user-data-dir="$SCRATCH/chrome-profile-N" \
  --screenshot="$SCRATCH/ui.png" http://127.0.0.1:8765/
```

Use a **fresh** `--user-data-dir` per shot (profile lock makes reruns silently
produce nothing). `--virtual-time-budget` lets the SPA's fetches finish.

## Flows worth driving

- 1:1 spend: today's number must drop by exactly the expense amount.
- Over-state: spend past `budget_today` → UI shows 0, "now spending the
  overall budget", red `next_daily` ("was `daily_base`").
- Carryover: period started yesterday, nothing spent → today = 2 × base.
- Rebase: backdated overspent day → today = remaining / days-after.
- Delete an expense → numbers recompute (pure function of DB state).
