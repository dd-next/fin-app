# BUILD_PLAN.md — phases

Build in this order. Each phase ends with passing tests, an updated
`PROGRESS.md`, and a git commit (see `CLAUDE.md` → Workflow rules). This is what
lets any model resume from `PROGRESS.md` if work stops.

**You MAY do all phases in a single session** if you have the budget for it — the
scope is small. The phase structure exists so the work is checkpointed and
resumable, not because it must be split across sessions.

## Phase 1 — Pure budget core + unit tests
- Implement `app/budget.py` per SPEC section 4.
- Write `tests/test_budget.py` per SPEC section 9 (all edge cases).
- No DB, no API yet. `pytest tests/test_budget.py` is green.

## Phase 2 — Data layer + API
- `app/db.py` (async SQLite engine/session), `app/models.py`, `app/schemas.py`.
- Alembic set up; one migration creating both tables.
- `app/main.py` with all endpoints from SPEC section 5 **except** `/export.xlsx`.
- `tests/test_api.py` per SPEC section 9. App boots; all API tests green.

## Phase 3 — .xlsx export
- `app/export.py` builds the workbook per SPEC section 6.
- Wire `GET /export.xlsx` (`StreamingResponse`, correct headers).
- `tests/test_export.py` round-trip per SPEC section 9. Green.

## Phase 4 — Frontend (responsive SPA)
- `app/static/` page per SPEC section 7; served via FastAPI `StaticFiles`.
- Live "after this purchase" preview, set-period UI, expense list + delete,
  download button. Consult the **frontend-design** skill.
- Manual check: works on a narrow (phone) and a wide (desktop) viewport.

## Phase 5 — Polish & README
- `README.md`: install / run / test in fewer than 5 commands.
- `.gitignore`, `.env.example` (with a commented `DATABASE_URL` showing the
  Postgres swap).
- Final pass over the acceptance criteria (SPEC section 8). All tests green.

---

## Out of scope (do not build)
Telegram Mini App, Google Sheets sync, multi-user / auth. These are future
phases and are intentionally excluded from this plan.
