# FinApp v2

The authoritative v2 specification is
[`specs/FinnApp-v2.md`](specs/FinnApp-v2.md); implementation phases are in
[`BUILD_PLAN-v2.md`](BUILD_PLAN-v2.md). The currently running code still
represents the completed family-finance generation and will be replaced phase
by phase while the repository remains runnable.

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
- **Budget pools**: group period categories into envelopes such as Home or Food,
  validate nested allocations, and optionally copy the plan into the next
  period without rolling spending forward.
- **Savings goals**: planned contributions participate in period allocation;
  Save/Withdraw ledger operations move money atomically and goal balances persist
  across periods.
- **Personal and family spaces**: two users can share a workspace while keeping
  personal periods isolated; owner/editor memberships are checked on every
  financial request.
- **Period history**: previous periods remain selectable and correctable instead
  of being replaced by the next period.

FastAPI + SQLite backend, Argon2id web authentication, vanilla-JS dark UI,
and period-specific `.xlsx` export. The family beta intentionally uses one
unit of money per workspace rather than multi-currency accounting.

## Install

```sh
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```sh
alembic upgrade head
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
  to `finapp.db` automatically on startup (default SQLite URL only).
- Migrations: run `alembic upgrade head` before starting after every update.
  Automatic table creation keeps a fresh local checkout convenient, but only
  Alembic performs data-preserving upgrades of an existing database.
- Postgres later: set `DATABASE_URL` (see `.env.example`) — nothing else
  changes.
- API docs are at http://127.0.0.1:8000/docs. Public application routes are
  versioned as `/api/v1/workspaces/{workspace_id}/...`; export requires an
  explicit period at
  `/api/v1/workspaces/{workspace_id}/periods/{period_id}/export.xlsx`.

## Google Sheets sync (optional)

The DB stays the source of truth; every mutation triggers a best-effort full
re-sync. Google Sheets intentionally keeps its legacy six-column operation
layout for now; family metadata is available in the `.xlsx` export only.

1. Google Cloud Console → enable the **Google Sheets API**.
2. Create a **service account** and download its JSON key (an API key cannot
   write to sheets).
3. Share the target spreadsheet (Editor) with the service account's
   `client_email` from that JSON.
4. Set `SHEETS_ENABLED`, `GOOGLE_SHEET_ID`, `GOOGLE_SERVICE_ACCOUNT_FILE`
   (see `.env.example`). Keep the JSON out of git.

`POST /api/v1/workspaces/{workspace_id}/sheets/sync` forces a manual re-sync
(e.g. after a Google outage).
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
