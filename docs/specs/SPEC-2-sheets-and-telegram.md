# SPEC-2 — Google Sheets sync + Telegram Mini App

> Historical specification. Google Sheets and Telegram are outside the current
> FinApp v2 release; see [`FinnApp-v2.md`](FinnApp-v2.md).
> All instructions below are archival and must not be executed.

Addendum to `SPEC.md`. All conventions in `CLAUDE.md` still apply. Do these
phases only after the MVP (phases 1–5) is green.

**Approved new dependencies for this increment** (exception to "don't add deps"):
- `gspread` + `google-auth` — Google Sheets write access.
- Telegram: no Python Telegram library is required for the MVP Mini App (see
  Part B). If a bot process is added later, use `aiogram`.

FastAPI `BackgroundTasks` (in-process, runs after the response) IS allowed — it
is not a task queue and does not need Redis/Celery.

---

## Part A — Automatic Google Sheets sync

### A.1 Authentication (read this — an API key will NOT work)
Writing to a Google Sheet requires OAuth. A plain API key can only **read**
publicly-shared sheets; it cannot write. Use a **service account**:

1. Google Cloud Console → enable the "Google Sheets API".
2. Create a service account; create a JSON key for it.
3. Open the target spreadsheet → Share (Editor) with the service account's
   `client_email` (found inside the JSON).
4. The app authenticates with that JSON — no user consent flow.

If you already have a Google credential from n8n, open the JSON: if it contains
`"type": "service_account"` and a `client_email`, it is a service account key —
reuse it directly (just share the sheet with its email). If it is an OAuth client
or a bare API key, create a service account as above instead.

### A.2 Configuration (env — all optional, app runs without them)
- `SHEETS_ENABLED` = true/false (default false).
- `GOOGLE_SHEET_ID` = the spreadsheet id from its URL.
- `GOOGLE_SERVICE_ACCOUNT_FILE` = path to the JSON key (kept out of git).

If `SHEETS_ENABLED` is false or config is missing, the app behaves exactly like
the MVP (zero Sheets calls). Never crash because Sheets is unconfigured.

### A.3 Sync design (the DB stays the source of truth)
The dataset is tiny, so avoid drift with an **idempotent full re-sync**: on every
mutation, rewrite the "Period" and "Expenses" sheets from current DB state (same
layout as the export in SPEC section 6). No append-only diffing, no hidden state —
the sheet always mirrors the DB.

- Put Sheets logic in `app/sheets.py`. It reuses the same row-building code as
  `app/export.py` — refactor that into one shared function so export and sync
  always agree.
- Trigger the sync from a FastAPI `BackgroundTask` after each successful mutation
  (`POST /period`, `POST /expenses`, `DELETE /expenses/{id}`), so the HTTP
  response is not blocked and a slow/failed Google call never delays the user.
- **Best-effort:** wrap the sync in try/except; on failure, log it and continue. A
  Sheets outage must never break the app or lose data (the DB already has it).
- `gspread` is synchronous — running it inside a BackgroundTask (which executes
  sync functions in a threadpool) keeps the event loop free.
- Add `POST /sheets/sync` — a manual "sync now" endpoint running the same full
  re-sync, returning ok/failed. Powers a "Sync" button and recovery after an
  outage.

### A.4 Tests
- With `SHEETS_ENABLED=false`, all existing tests pass and no Google call is made.
- Unit-test the shared row-building function (export and sync produce identical
  rows) — no network.
- Monkeypatch the `gspread` client and assert a mutation writes the expected rows;
  assert a raised gspread error is swallowed and the API still returns `200`.
- Do NOT hit the real Google API in tests.

---

## Part B — Telegram Mini App entry point

Goal: open the existing SPA inside Telegram. Reuse the same frontend; add a thin
Telegram layer. No rewrite.

### B.1 Simplest path (no bot process needed)
1. Create a bot with @BotFather; get the bot token.
2. In @BotFather, set the Mini App / menu button to your app's HTTPS URL. That
   alone makes "open the app" work inside Telegram — no running bot code required
   for the MVP.
3. The frontend loads Telegram's `telegram-web-app.js`, calls
   `Telegram.WebApp.ready()`, and adapts colors to `Telegram.WebApp.themeParams`
   (the dark theme fits the existing design).

### B.2 Auth via initData (required once it is on a public URL)
Once the app is reachable over HTTPS, anyone could hit the API — gate it:
- The frontend sends `Telegram.WebApp.initData` (a signed string) with each
  request, e.g. an `Authorization: tma <initData>` header.
- The backend validates it: HMAC-SHA256 over the data-check-string with a key
  derived from the bot token, per Telegram's documented scheme; reject if invalid
  or older than a few minutes.
- Single-user pin: also require the Telegram user id inside initData to equal your
  own `OWNER_TELEGRAM_ID` (env). Keeps it your personal instance.
- Put validation in `app/telegram_auth.py` as a FastAPI dependency on the data
  endpoints. Keep `/health` open.

Config: `TELEGRAM_BOT_TOKEN`, `OWNER_TELEGRAM_ID`, `TELEGRAM_AUTH_ENABLED`
(default false, so local browser testing still works without Telegram).

### B.3 Hosting note (the one real bit of infra)
Telegram Mini Apps require a public HTTPS URL.
- Local testing: a tunnel (Cloudflare Tunnel or ngrok) pointing at local FastAPI.
- Real use: deploy to a small host (Fly.io / Railway / a VPS) and switch the DB to
  Postgres (the `DATABASE_URL` swap from phase 5).

### B.4 Tests
- initData validation: a correctly-signed sample passes; a tampered one is
  rejected; an expired one is rejected; a wrong `OWNER_TELEGRAM_ID` is rejected.
  Generate the sample signature in the test with the same algorithm — no network.
- With `TELEGRAM_AUTH_ENABLED=false`, existing tests still pass.

---

## New phases (continue PROGRESS.md after phase 5)

- **Phase 6** — Refactor export row-building into one shared function; no behavior
  change; existing tests stay green.
- **Phase 7** — Google Sheets full re-sync: `app/sheets.py`, env config,
  BackgroundTask triggers, `POST /sheets/sync`, tests A.4.
- **Phase 8** — Telegram Mini App: frontend Telegram layer, `app/telegram_auth.py`
  with initData validation, tests B.4. Document the @BotFather + tunnel steps in
  README.

Each phase: tests green, `PROGRESS.md` updated, git commit — same as before. Add
Phase 6–8 checkboxes to PROGRESS.md.

### Still out of scope
Multi-user, sharing between accounts, a full conversational bot UI.
