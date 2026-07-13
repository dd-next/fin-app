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
