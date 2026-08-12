---
name: verify
description: Launch and drive this app end-to-end (FastAPI + SPA) to verify a change against a scratch DB, without touching finapp.db.
---

# Verify this app end-to-end

## Launch (isolated — never against the repo's `finapp.db`)

```sh
FINAPP_VERIFY_DIR="$(mktemp -d /private/tmp/finapp-verify.XXXXXX)"
FINAPP_VERIFY_DB="$FINAPP_VERIFY_DIR/finapp.db"
DATABASE_URL="sqlite+aiosqlite:///$FINAPP_VERIFY_DB" .venv/bin/alembic upgrade head
DATABASE_URL="sqlite+aiosqlite:///$FINAPP_VERIFY_DB" \
  .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8765 --log-level warning
```

Run Uvicorn in a persistent terminal/session, then verify from another shell:

```sh
curl -sS -i http://127.0.0.1:8765/health
curl -sS -I http://127.0.0.1:8765/
```

`app/db.py` reads `DATABASE_URL`; four slashes before an absolute path are
required. Keep the explicit scratch URL on both Alembic and Uvicorn. Never
unset `DATABASE_URL` and assume that the default database is safe.

## Establish an authenticated scratch workspace

Register through the visible UI, or preserve the session cookie with the
current API:

```sh
curl -sS -c "$FINAPP_VERIFY_DIR/cookies.txt" \
  -H 'Content-Type: application/json' \
  -d '{"username":"uiowner","password":"correct-horse-battery","display_name":"UI Owner","timezone":"Asia/Ho_Chi_Minh","base_asset_code":"USD"}' \
  http://127.0.0.1:8765/api/v1/auth/register
curl -sS -b "$FINAPP_VERIFY_DIR/cookies.txt" \
  http://127.0.0.1:8765/api/v1/auth/me
```

Use the public `/api/v1` contracts or the visible UI to create accounts,
periods, operations, rates, and Plan data. Do not insert directly into SQLite:
direct rows can bypass ledger, permission, replay, and soft-void invariants.

## Browser matrix

The app is the acceptance surface. Drive it with the available browser tooling
against the scratch server and retain screenshots in the task's scratch
directory.

- Mobile reference: `390×844`.
- Preserved desktop acceptance width: `1280×900`.
- Register or log in through the UI so the actual cookie/session flow is used.
- Exercise the task's visible state, loading/error/empty state, keyboard/focus
  state when applicable, and the return path from sheets/confirmations.
- Inspect browser console errors and horizontal/forbidden vertical overflow.
- Never treat a static HTML/CSS string assertion as visual acceptance.

For a public/auth-shell pixel smoke, headless Chrome is available:

```sh
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless=new --disable-gpu --hide-scrollbars --window-size=390,844 \
  --virtual-time-budget=4000 \
  --user-data-dir="$FINAPP_VERIFY_DIR/chrome-mobile" \
  --screenshot="$FINAPP_VERIFY_DIR/mobile-auth.png" \
  http://127.0.0.1:8765/
```

Use a fresh `--user-data-dir` per Chrome run; profile locks otherwise make
reruns silently fail. Headless screenshots do not replace authenticated
interactive checks for feature tasks.

## Required financial UI checks when the task touches them

- Spend above Available today remains valid; the recalculated allowance may be
  negative.
- Transfer uses the quote/execute result and preserves both account values and
  Total capital semantics.
- Period Start/Edit uses the selected rollover policy and refreshes the
  ledger-derived cards.
- Delete and Undo remain soft operations and refresh balances/periods.
- Planned feed rows never change real balances until an eligible transaction
  is linked.
