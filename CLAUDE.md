# CLAUDE.md — working agreement for the next FinApp v2 release

The primary product and technical specification is
`docs/specs/FinnApp-v2.md`. Read it first, then `docs/BUILD_PLAN-v2.md`,
`docs/REVIEW_PROTOCOL-v2.md`, and `docs/PROGRESS.md`. Historical files within
`docs/specs/` and the root-level v2 markdown pointers cannot override these
active documents.

## Tech stack

- Python 3.12, FastAPI, Pydantic v2.
- SQLAlchemy 2.x async ORM and Alembic.
- SQLite through `aiosqlite` for local development.
- `pytest` and `httpx` for automated tests.
- Plain HTML, CSS and vanilla JavaScript; no frontend build step.

Do not deviate from the stack without recording the reason in
`docs/PROGRESS.md`.

## Hard rules

- The health endpoint is exactly `/health`.
- Money and rates always use `Decimal`, never `float`.
- Asset precision is explicit; ledger storage must support crypto precision.
- Account balances, totals, and account-period values derive from posted ledger
  movements.
- Keep daily-budget calculations in `app/budget.py` pure: no DB or framework
  imports.
- All active product and technical specifications live in `docs/`.
- The public application API uses `/api/v1`.
- UI copy is English only.
- Do not add Redis, Celery, Prometheus, a queue, or a background worker.
- Google Sheets, Telegram Mini App, XLSX export, crypto sync, savings goals,
  category limits, pools, and full analytics are outside this release.
- Docker is added only in Phase 13. Do not add dependencies that are not used.

## V2 reset rule

The release starts with a clean database and a new Alembic history. No legacy
rows are migrated. Before replacing or deleting local `finapp.db`, create a
timestamped recoverable copy in `.backups/`, record its SHA-256 checksum and
open/restore verification in `docs/PROGRESS.md`, then proceed.

## Mandatory workflow

Work strictly phase by phase from `docs/BUILD_PLAN-v2.md`; do not skip ahead.
Every phase is split into bounded logical blocks.

After **every written logical block**:

1. Run targeted tests.
2. Create a separate, read-only reviewer sub-agent following
   `docs/REVIEW_PROTOCOL-v2.md`.
3. Fix all review findings and re-review if those fixes change behavior or
   coverage.
4. Record reviewer task, findings, resolution, and test evidence in
   `docs/PROGRESS.md`.

After every phase:

1. Run phase tests, complete `pytest`, `node --check app/static/app.js`, and
   `git diff --check`, plus the phase-specific migration/browser/Docker checks.
2. Update `docs/PROGRESS.md` with status, 2–4 completed-work lines, exact test
   results, reviewer evidence, and decisions or assumptions.
3. Commit with `v2 phase N: <short summary>` only after all P0–P2 review
   findings are closed.

If blocked, record the blocker and attempted fixes in `docs/PROGRESS.md`,
commit a clean runnable checkpoint, and stop. The app and tests must be
runnable at the end of every phase.

## Definition of done

All acceptance criteria in `docs/specs/FinnApp-v2.md` are met, every logical
block has an independent reviewer-subagent pass, the full automated suite
passes, the SPA passes scratch-database browser checks at phone and desktop
widths, and README documents install, run, migrate, test, Docker persistence,
backup, and restore.
