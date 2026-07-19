# BUILD_PLAN.md — phases

> Historical build plan for completed earlier versions. The active plan is
> [`docs/BUILD_PLAN-v2.md`](docs/BUILD_PLAN-v2.md). Everything below this note,
> including its references to root `PROGRESS.md`, is archival and must not be
> executed for the current release.

Build in this order. Each phase ends with passing tests, an updated
`PROGRESS.md`, and a git commit (see `CLAUDE.md` → Workflow rules). This is what
lets any model resume from `PROGRESS.md` if work stops.

The base product specification is `specs/SPEC.md`; family-finance work is
defined by `specs/SPEC-4-family-finance.md`.

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

---

## Family-finance expansion (SPEC-4)

The earlier out-of-scope statement is superseded by SPEC-4 for these phases.

## Phase 14 — Workspace and migration foundation
- Record SPEC-4, back up the live SQLite file, add the legacy personal
  workspace, rename `expense` to `operation`, and add `occurred_on`.
- Prove migration preservation with an automated upgrade test.

## Phase 15 — Period history
- Preserve periods, reject overlaps within a workspace, support selection and
  historical correction, and export a selected period.

## Phase 16 — Web authentication
- Users, password hashes, persistent sessions, login/logout/me, and owner
  bootstrap.

## Phase 17 — Personal and shared workspaces
- Memberships, owner/editor roles, invitations, and workspace switching.

## Phase 18 — Categories and limits
- Workspace categories, optional operation category, period-specific limits,
  and non-blocking over-limit warnings.

## Phase 19 — Pools
- Period pool allocations, category assignment, allocation validation, and
  optional cloning from the previous period.

## Phase 20 — Savings goals
- Persistent goals plus atomic transfers between a period and a goal.

## Phase 21 — API v1, frontend, export, and final verification
- Complete scoped `/api/v1` flows, UI, richer export, docs, and E2E checks.
