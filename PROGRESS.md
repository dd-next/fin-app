# PROGRESS.md — build ledger

The agent updates this after every phase.

**To resume in a new session (any model):** read `SPEC.md`, `CLAUDE.md`,
`BUILD_PLAN.md`, then this file, and continue from the first unchecked phase,
following the same conventions.

Status legend: `[ ]` not started · `[~]` in progress · `[x]` done

- [x] Phase 1 — Pure budget core + unit tests
- [x] Phase 2 — Data layer + API
- [x] Phase 3 — .xlsx export
- [x] Phase 4 — Frontend (responsive SPA)
- [x] Phase 5 — Polish & README
- [x] Phase 6 — Shared export row-building (SPEC-2)
- [x] Phase 7 — Google Sheets full re-sync (SPEC-2)
- [x] Phase 8 — Telegram Mini App (SPEC-2)

## Log
<!-- Agent: append an entry per phase — what you built, test results (pass/fail), decisions. -->

### Phase 1 — Pure budget core + unit tests (2026-07-13)
- Implemented `app/budget.py`: pure functions (`days_total/elapsed/remaining`,
  `spent_total`, `remaining_money`, `per_day`, `preview_after`) plus a
  `compute_budget()` that derives a full `BudgetSummary` from scratch — no
  hidden state, no DB/framework imports. All money is `Decimal`.
- Wrote `tests/test_budget.py` covering every SPEC §9 edge case: overspend
  (negative, unclamped), last day, past end_date, zero-length period,
  delete-after-increase == fresh recompute, Decimal exactness, preview.
- Tests: **12 passed, 0 failed** (`pytest tests/test_budget.py`).
- Env: Python 3.12.7 venv at `.venv/`, deps in `requirements.txt`.

### Phase 2 — Data layer + API (2026-07-13)
- Built `app/db.py` (async engine + session, `DATABASE_URL` env override),
  `app/models.py` (Period/Expense, FK cascade), `app/schemas.py`,
  `app/main.py` with all SPEC §5 endpoints except `/export.xlsx`.
- Alembic set up (async env.py); migration `0001` creates both tables.
  Verified `alembic upgrade head` works against a fresh DB; app also does an
  idempotent `create_all` on startup for zero-setup dev.
- Fixed: SQLite FK enforcement is off by default → replacing a period left
  orphan expenses that collided with the reused rowid. Added a
  `PRAGMA foreign_keys=ON` connect listener in `app/db.py`.
- Tests: **23 passed, 0 failed** (12 budget + 11 API). Boot smoke-tested:
  `/health` → 200 ok, `/period` → 404 when none.
- Decisions: (a) money stored as TEXT on SQLite via a `Money` TypeDecorator
  (SQLite NUMERIC is float and would break Decimal exactness; real
  `Numeric(12,2)` on Postgres — still just a connection-string change);
  (b) amounts must have ≤ 2 decimal places (Pydantic `decimal_places=2`);
  (c) `POST /period` hard-deletes the old period + its expenses (SPEC: "at
  most one active period", no cross-period history in scope);
  (d) response shapes: `POST/GET /period` → `{period, budget}`,
  `POST /expenses` → `{expense, budget}`, `DELETE /expenses/{id}` → budget;
  (e) `greenlet` added to requirements (SQLAlchemy async needs it; not
  auto-installed on macOS arm64).

### Phase 3 — .xlsx export (2026-07-13)
- `app/export.py`: pure `build_workbook()` (plain values in, bytes out).
  Sheet "Period" = key/value table; sheet "Expenses" = chronological replay
  with running balance and per-day allowance at each point. Bold header,
  auto-sized columns, `YYYY-MM-DD` dates, numeric amounts.
- Wired `GET /export.xlsx` in `app/main.py` as a `StreamingResponse` with the
  exact Content-Type / Content-Disposition from SPEC §5. 404 if no period.
- `tests/test_export.py`: full round-trip (API → xlsx → openpyxl → compare
  against API numbers) + 404 case. Note: openpyxl reads empty cells back as
  `None`, so blank comments assert as `None`-or-empty.
- Tests: **25 passed, 0 failed** (full suite).

### Phase 4 — Frontend (responsive SPA) (2026-07-13)
- `app/static/` (index.html / style.css / app.js): dark UI, orange accent,
  big "today's allowance" number (red when negative), live "after this
  purchase" preview via `GET /budget?pending=X` (debounced), set-period form
  (defaults: today → end of month), expense list with delete, .xlsx download
  link, error toast. Plain vanilla JS, no build step, no libraries.
- Served via `StaticFiles`: `/static/*` for assets, `/` (html=True) mounted
  last so API routes win. Verified: `GET /` → 200 text/html, assets → 200;
  full flow (set period → add expense → pending preview → export) exercised
  against the running server with correct numbers.
- Mobile-first single column (max-width 480px, `clamp()` type, ≥44px tap
  targets) + one wide-viewport media query.
- Note: SPEC says to consult the **frontend-design** skill, but it is not
  available in this session's skill list; followed its intent from SPEC §7
  (dark, minimal, one accent). Visual check in a real browser at narrow/wide
  widths is left as a human step (Chrome extension not connected).
- Tests: **25 passed, 0 failed** (suite unchanged — frontend is static).

### Phase 5 — Polish & README (2026-07-13)
- `README.md`: install (2 commands), run (1), test (1) — 4 commands total.
- `.env.example` with commented SQLite default and Postgres swap;
  `.gitignore` was added in Phase 1.
- Final acceptance pass (SPEC §8), verified against a fresh server on :8000:
  1. `/health` → `200 {"status":"ok"}` ✓
  2. set period + expenses → allowance updates correctly, live preview via
     `?pending=` ✓ (API tests + manual flow)
  3. overspend → `remaining_money: "-200"`, `per_day_today: "-20.00"` ✓
  4. delete recomputes correctly ✓ (test_expense_updates_budget_and_delete_restores,
     test_delete_after_increase_equals_fresh_recompute)
  5. `/export.xlsx` → 200, valid workbook, both sheets populated ✓
  6. frontend served at `/`, responsive single-column layout ✓ (visual
     browser pass left to a human — extension unavailable, see Phase 4)
  7. full suite: **25 passed, 0 failed** ✓
  8. README: < 5 commands ✓
- Done. Out-of-scope items (Telegram, Sheets sync, multi-user) not built.

### Phase 6 — Shared export row-building (SPEC-2) (2026-07-14)
- Refactored `app/export.py`: extracted `period_rows()`, `expense_rows()`
  and `EXPENSE_HEADERS`; `build_workbook()` now consumes them. No behavior
  change — Phase 7's Sheets sync will reuse the same functions so export
  and sync always agree.
- Fixed a latent timezone bug the refactor surfaced: `created_at` was
  stamped in UTC while all budget math uses local `date.today()`, so after
  local midnight (but before UTC midnight) expense dates disagreed with
  "today". `models.utcnow()` → `models.localnow()` (naive local time) —
  a single-user local app lives in local calendar days.
- Tests: **25 passed, 0 failed**.

### Phase 7 — Google Sheets full re-sync (SPEC-2) (2026-07-14)
- `app/sheets.py`: service-account auth via gspread (lazy import),
  `enabled()` reads env at call time, `sync_now()` rewrites both sheets
  from the shared `export.period_rows/expense_rows` builders (clear +
  update, worksheet auto-created), `sync_safe()` logs and never raises.
- Mutations (`POST /period`, `POST /expenses`, `DELETE /expenses/{id}`)
  queue a BackgroundTask with a plain-values snapshot captured in-request
  (the DB session is closed by the time the task runs). Zero Sheets code
  runs when disabled. `POST /sheets/sync` → `{"status": "ok"|"failed"}`,
  runs in a threadpool (gspread is sync).
- Tests (`tests/test_sheets.py`, all offline, gspread faked): export/sync
  row parity, mutation writes expected rows, delete re-syncs, gspread
  errors swallowed (API still 200), disabled ⇒ zero Google calls
  (fails loudly if touched), manual sync ok/failed/disabled.
- Decisions: (a) Decimal → float when writing cells so Sheets gets numeric
  cells (mirror only; DB keeps exact Decimals); (b) `/sheets/sync` returns
  `{"status":"disabled"}` when the feature is off (SPEC-2 only specifies
  ok/failed); (c) `enabled()` requires the flag AND both config values —
  a half-configured app behaves as disabled rather than crashing.
- Tests: **33 passed, 0 failed** (25 existing + 8 new).

### Phase 8 — Telegram Mini App (SPEC-2) (2026-07-14)
- `app/telegram_auth.py`: `validate_init_data()` implements Telegram's
  documented scheme (secret = HMAC-SHA256("WebAppData", bot_token); hash =
  HMAC over the sorted data-check-string; constant-time compare), rejects
  stale initData (> 5 min) and any user other than `OWNER_TELEGRAM_ID`.
  `require_telegram_auth` FastAPI dependency → 401; no-op when
  `TELEGRAM_AUTH_ENABLED` is off (default).
- All data endpoints gated (`dependencies=[AUTH]`); `/health` and the
  static frontend stay open. Smoke-tested live: 401 without header,
  /health 200, / 200.
- Frontend: loads `telegram-web-app.js` (no-op in a normal browser), calls
  `ready()`/`expand()`, adopts `themeParams` bg colors, sends
  `Authorization: tma <initData>` on every API call, and downloads the
  .xlsx via fetch+blob inside Telegram (plain link in a browser).
- `tests/test_telegram.py` (12 tests): signature generated locally with the
  same algorithm — valid passes; tampered / wrong-token / expired /
  wrong-owner / missing-hash rejected; API 401 without or with bad header,
  200 with valid; /health open; disabled ⇒ no auth wall.
- README: @BotFather + tunnel setup documented. `.env.example` updated.
- No bot process, no aiogram — the Mini App needs none (SPEC-2 B.1).
- Tests: **44 passed, 0 failed** (full suite; Sheets + Telegram both
  default-off, so the MVP behavior is unchanged).

### Fix — daily budget copies the original app's semantics (2026-07-15)
- Bug report with screenshots of the original Tzlvt: spending must reduce
  **today's** number 1:1. Our spec'd formula `remaining / days_remaining`
  re-spread every expense over the whole rest of the period, so today's
  number barely moved (6000/15 with 493.33 spent showed 367.11 instead of
  400 − 493.33). SPEC §4 itself was wrong; user asked to copy the original.
- Rewrote `app/budget.py` (still a pure, stateless recompute): fixed
  `daily_base = total/days`; unspent money rolls forward into today; an
  overspent day eats the pool and rebases the base to remaining/days-after.
  `compute_budget` now takes dated amounts. New summary/API fields:
  `daily_base`, `budget_today`, `spent_today`, `next_daily`;
  `per_day_today` is now today's number (budget_today − spent_today) and
  `preview_after = per_day_today − pending`.
- Export/Sheets: "Per-day allowance at that point" column → "Left to spend
  that day" (replayed with the real math at each expense's date).
- Frontend: over-state copied from the original — big "0", "Now spending
  the overall budget", rebased daily budget big and red with "was X".
- SPEC.md §1/§4/§5/§8/§9 updated to the new math (recorded as a user
  override dated 2026-07-15). README wording updated.
- Verified end-to-end against a live server on a scratch DB (screenshot
  scenario reproduced: 400 → 6.67 → −93.33 with next_daily 393.33; carryover,
  cross-day rebase, delete-recompute, export replay, ?pending preview, 422s;
  UI over-state + normal state screenshotted via headless Chrome). Added
  `.claude/skills/verify/SKILL.md` with the launch/drive recipe.
- Tests: `test_budget.py` rewritten (17 unit tests incl. the bug-report
  scenario); `test_api`/`test_export`/`test_sheets` updated.
  **49 passed, 0 failed** (was 44).

## Blocked
<!-- Agent: if you get stuck, describe the problem, what you tried, and where you stopped. -->

## Decisions / assumptions
<!-- Agent: record any choice you made where SPEC.md was silent. -->
