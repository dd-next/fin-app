# Tzlvt-clone — Product & Technical Specification

This is the single source of truth for what to build. If anything here
conflicts with your own assumptions, this file wins. If something is genuinely
undefined, pick the simplest option and record the decision in PROGRESS.md.

## 1. What the app is

A minimalist daily-budget tracker (a clone of "Тяжеловато" / Tzlvt).

The user sets an amount of money and a period. The app divides the money across
the remaining days and shows how much can be spent **today**. When the user adds
an expense, today's allowance is recalculated live. Overspending today lowers the
allowance for the remaining days.

No categories. No currencies (amounts are plain numbers). No auth (single-user,
single-tenant). Dark, minimal UI.

## 2. Scope

### In scope (MVP — build this)
- Set / replace the current budget period (amount + start date + end date).
- Add an expense (amount + optional comment).
- Delete an expense.
- List expenses for the current period.
- See today's budget: the current allowance, and a live preview of the allowance
  after a pending (not-yet-saved) expense.
- Export all data to a downloadable `.xlsx` file.
- Automated tests covering the budget math and the API.

### Out of scope (do NOT build now)
- Telegram Mini App wrapper.
- Google Sheets sync.
- Multiple periods / cross-period history, multi-user, accounts, auth.
- Notifications, home-screen widgets, native mobile apps.

Keep the code structured so these can be added later, but do not implement them.

## 3. Domain model

Two tables.

**period** (at most one active period at a time for the MVP)
- `id`: int, pk
- `total_amount`: numeric(12,2) — money available for the whole period
- `start_date`: date
- `end_date`: date — inclusive
- `created_at`: datetime

**expense**
- `id`: int, pk
- `period_id`: int, fk → period.id (cascade delete)
- `amount`: numeric(12,2)
- `comment`: text, nullable
- `created_at`: datetime — the moment/day the expense was entered

Use `Decimal` for money everywhere (never `float`). Round displayed per-day /
allowance values to 2 decimals; keep stored amounts exact.

## 4. Core budget calculation (the heart of the app)

Put this in a pure module `app/budget.py` with NO database and NO framework
imports, so it can be unit-tested in isolation. Functions take plain values /
Decimals and return Decimals.

Definitions (relative to a reference date `today`, default = `date.today()`):

    days_total      = (end_date - start_date).days + 1
    days_elapsed    = clamp((today - start_date).days, 0, days_total)
    days_remaining  = max(days_total - days_elapsed, 1)    # never divide by 0
    spent_total     = sum(amount for expenses in the period)
    remaining_money = total_amount - spent_total
    per_day_today   = remaining_money / days_remaining

Live preview while typing an expense of size X (X not yet saved):

    preview_after   = (remaining_money - X) / days_remaining

Rules / edge cases the math MUST handle correctly:
- **Overspending:** `remaining_money` and `per_day_today` may go negative. Do NOT
  clamp them to zero — show the real (negative) number.
- **Last day:** `days_remaining == 1`, so `per_day_today == remaining_money`.
- **After the period ends** (`today > end_date`): `days_remaining` stays at 1
  (guarded), no crash.
- **Deleting an expense** must recompute everything correctly. (This was a real
  bug in the original app: deleting an expense after the daily budget increased
  corrupted the numbers.) There is no hidden state here — everything is derived
  from `(period + list of expenses)`, so recomputation from scratch is always
  correct. Rely on that.
- `days_remaining` is never 0 (guard against division by zero).

## 5. HTTP API (FastAPI)

JSON everywhere except the export endpoint. Routes at root (no prefix).

- `GET /health`
  → `200 {"status": "ok"}` — health-check endpoint; the path is exactly `/health`.

- `POST /period`
  body: `{total_amount, start_date, end_date}`
  → creates/replaces the active period; returns the period + current budget summary.

- `GET /period`
  → the active period + budget summary, or `404` if none set.

- `GET /budget`
  → `{days_total, days_remaining, spent_total, remaining_money, per_day_today}`.
  Optional query `?pending=<amount>` → also returns `preview_after`.

- `GET /expenses`
  → list of expenses for the active period (newest first).

- `POST /expenses`
  body: `{amount, comment?}`
  → adds an expense to the active period; returns the expense + updated budget.

- `DELETE /expenses/{id}`
  → deletes the expense; returns the updated budget. `404` if not found.

- `GET /export.xlsx`
  → streams an `.xlsx` file (see section 6).
  `Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
  `Content-Disposition: attachment; filename="tzlvt-export.xlsx"`

Validation: amounts must parse as `Decimal`; `end_date >= start_date`; reject
malformed input with `422` (Pydantic default).

## 6. .xlsx export

Use `openpyxl`. One workbook, two sheets.

**Sheet "Period":** a two-column key/value table with rows for
`total_amount`, `start_date`, `end_date`, `days_total`, `spent_total`, `remaining`.

**Sheet "Expenses":** columns
`Date | Amount | Comment | Running balance | Per-day allowance at that point`.
Header row bold; columns auto-sized; dates as `YYYY-MM-DD`; amounts numeric.

`Running balance` and `Per-day allowance at that point` are computed by replaying
expenses in chronological order.

## 7. Frontend (lightweight responsive SPA)

A single static page served by FastAPI (`StaticFiles`). Plain HTML + CSS +
vanilla JS, single small bundle, no build step preferred. Add a small framework
only if it stays a single bundle with no toolchain.

UX (mirror the original's feel):
- Dark background, high contrast, one accent color (orange). Large, calm type.
- Top: today's allowance, shown big.
- An input to add an expense; as the user types the amount, show the live
  "after this purchase" allowance (`GET /budget?pending=X` or compute client-side).
- A settings area to set the period (amount + dates).
- A list of recent expenses, each with a delete action.
- A "Download .xlsx" button hitting `/export.xlsx`.
- Responsive: usable on a phone (single column, big tap targets) and on desktop.

When you build the UI, consult the **frontend-design** skill for styling
direction. Keep it minimal; do not pull in libraries you don't need.

## 8. Acceptance criteria (the app is "done" when ALL are true)

1. `GET /health` returns `200 {"status":"ok"}`.
2. I can set a period, add several expenses, and today's allowance changes
   correctly and live.
3. Overspending shows a negative allowance (not clamped).
4. Deleting an expense recomputes the allowance correctly.
5. `GET /export.xlsx` downloads a valid file that opens in Excel / LibreOffice
   with both sheets populated.
6. The frontend works and is usable on both a narrow (phone) and wide (desktop)
   viewport.
7. All tests pass (`pytest`), including the edge cases in section 9.
8. `README.md` explains how to install, run, and test in fewer than 5 commands.

## 9. Testing requirements

Framework: `pytest`. API tests via `httpx.AsyncClient` against the FastAPI app.

**Unit tests for `app/budget.py` (pure math) — `tests/test_budget.py`:**
- normal case: an amount split across N days gives the expected per-day value.
- after adding an expense, `per_day_today` drops as expected.
- overspend → `remaining_money` and `per_day_today` are negative (not clamped).
- last day: `days_remaining == 1`, `per_day_today == remaining_money`.
- after `end_date`: `days_remaining` guarded to 1, no crash.
- division-by-zero guard: a zero-length or ended period never raises.
- delete-after-increase: build a sequence where the allowance rises, then remove
  an earlier expense; assert the final numbers equal a fresh recomputation.
- `Decimal` is used (no float drift) — assert exact expected `Decimal` values.

**API tests — `tests/test_api.py`:**
- `POST /period` then `GET /budget` returns the correct summary.
- `POST /expenses` updates the budget; `DELETE /expenses/{id}` restores it.
- `GET /budget?pending=X` returns the expected `preview_after`.
- `404` on deleting a missing expense; `422` on bad input; `404` on `GET /period`
  when none is set.

**Export test (round-trip) — `tests/test_export.py`:**
- create a period + expenses, `GET /export.xlsx`, load the bytes back with
  `openpyxl`, and assert the Expenses sheet row count and totals match the API.

Aim for meaningful coverage of `budget.py` (the critical module) and the error
paths — not a coverage number for its own sake.
