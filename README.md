# FinApp — minimalist daily-budget tracker

Product specifications live in [`specs/`](specs/); the current family-finance
expansion is defined in `specs/SPEC-4-family-finance.md`.

Set an amount and a period; the app splits the money across the days and
shows what you can spend **today**. Add an expense and today's number drops
by exactly that amount. Money you don't spend rolls into tomorrow; blowing
past today's budget eats the overall pool and rebases the daily budget for
the remaining days.

Features:
- **Expenses and incomes**: the Expense | Income toggle records top-ups
  mid-period; an income raises today's number 1:1 and grows the pool.
- **Undo**: an inline "‹ Undo {amount}" control right after adding an
  operation.
- **Next-day savings decision**: if yesterday ended with money left over, a
  full-screen "Nice!" prompt asks whether to spend it all today (default
  carry-over) or increase the daily budget (re-spread the remaining money).
- **Expenses History** view (all operations, human timestamps, delete) with
  the **Export .xlsx** button inside it; **Budget Settings** view with a
  live "{X} per day" preview.
- "Spent" state when the whole budget is gone — recoverable with an income.
- **Workspace categories and period limits**: expenses may stay Uncategorized
  or use a reusable category; exceeding a limit warns without hiding or
  rejecting the real expense.

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

For the family web-auth mode, migrate and create the first owner before
enabling `WEB_AUTH_ENABLED`:

```sh
alembic upgrade head
python -m app.manage bootstrap-owner your_username
```

Then set `WEB_AUTH_ENABLED=true`. Login sessions use an HttpOnly cookie; set
`COOKIE_SECURE=true` when serving over HTTPS.

The first owner receives the migrated Personal space. In the authenticated UI,
use **+ Shared** to create the family space and **Invite** to copy a one-time
7-day signup link for the second member. Both members edit finances; only the
owner can issue invitations.

## Test

```sh
pytest
```

## Notes

- Data lives in `./finapp.db` (SQLite, created automatically on first run).
  Upgrading from a pre-rename install: the app renames the old DB file
  (the legacy filename is the `_LEGACY_DB_FILE` constant in `app/db.py`)
  to `finapp.db` automatically on startup (default SQLite URL only), and
  older schemas get the new columns added automatically too.
- Migrations: `alembic upgrade head` (optional for local dev — the app also
  creates tables and patches missing columns on startup).
- Postgres later: set `DATABASE_URL` (see `.env.example`) — nothing else
  changes.
- API docs at http://127.0.0.1:8000/docs; export at `/export.xlsx`.

## Google Sheets sync (optional)

The DB stays the source of truth; every mutation triggers a best-effort full
re-sync that mirrors it into a spreadsheet (same layout as the .xlsx export).

1. Google Cloud Console → enable the **Google Sheets API**.
2. Create a **service account** and download its JSON key (an API key cannot
   write to sheets).
3. Share the target spreadsheet (Editor) with the service account's
   `client_email` from that JSON.
4. Set `SHEETS_ENABLED`, `GOOGLE_SHEET_ID`, `GOOGLE_SERVICE_ACCOUNT_FILE`
   (see `.env.example`). Keep the JSON out of git.

`POST /sheets/sync` forces a manual re-sync (e.g. after a Google outage).
A Sheets failure never breaks the app — it's logged and the DB keeps the data.

## Telegram Mini App (optional)

1. Create a bot with [@BotFather](https://t.me/BotFather); copy the token.
2. Telegram needs a public **HTTPS** URL. For local testing, run a tunnel:
   `ngrok http 8000` or `cloudflared tunnel --url http://localhost:8000`.
3. In @BotFather: *Bot Settings → Menu Button / Mini App* → set that URL.
   Opening the bot's menu button now launches the app inside Telegram —
   no bot process needed.
4. Gate the API so only you can use it: set `TELEGRAM_AUTH_ENABLED=true`,
   `TELEGRAM_BOT_TOKEN`, and `OWNER_TELEGRAM_ID` (your numeric user id).
   The frontend then sends Telegram's signed `initData` with every request;
   the backend verifies the signature (HMAC per Telegram's scheme), its age,
   and that the user is you. `/health` stays open; leave the flag off for
   plain-browser local use.
