# FinApp v2

This repository is being reset toward the next FinApp v2 release. Its active
requirements and execution rules are under [`docs/`](docs/README.md):

- [`docs/specs/FinnApp-v2.md`](docs/specs/FinnApp-v2.md) — product and technical
  target;
- [`docs/BUILD_PLAN-v2.md`](docs/BUILD_PLAN-v2.md) — mandatory Phase 8–13
  implementation order;
- [`docs/REVIEW_PROTOCOL-v2.md`](docs/REVIEW_PROTOCOL-v2.md) — independent
  reviewer-subagent gate for every logical block;
- [`docs/PROGRESS.md`](docs/PROGRESS.md) — current release checkpoint; and
- [`docs/specs/MANUAL_TEST_CASES-v2.md`](docs/specs/MANUAL_TEST_CASES-v2.md) —
  manual release acceptance.

The checked-in application still contains the earlier Tracker/commitment
prototype. It is a starting point, not evidence that the target documented in
`docs/` has already been implemented. In particular, do not treat current
Tracker, commitments, or Plan Pay/Receive behavior as active requirements.

## Install and run

Until the clean-schema reset in Phase 9 is implemented, these commands run the
current checkout for inspection and regression tests:

```sh
python3.12 -m venv .venv

source .venv/bin/activate

pip install -r requirements.txt

alembic upgrade head
uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000>. API documentation is available at
<http://127.0.0.1:8000/docs>; `GET /health` remains public.

No Redis, worker, queue, or other external service is required. Docker delivery
is added only in Phase 13. For HTTPS deployments set `COOKIE_SECURE=true`; the
reverse proxy and TLS stay outside Compose.

## Database and migration

The current default database is `./finapp.db`. Before Phase 9 replaces or
deletes it, the implementation agent must make a timestamped, recoverable
backup inside `.backups/`, record SHA-256 and open/restore verification in
`docs/PROGRESS.md`, and only then create the clean release schema.

Use an absolute async SQLite URL for isolated current-checkout tests, for
example:

```sh
DATABASE_URL=sqlite+aiosqlite:////tmp/finapp-v2.db alembic upgrade head
DATABASE_URL=sqlite+aiosqlite:////tmp/finapp-v2.db uvicorn app.main:app
```

## Test

```sh
.venv/bin/python -m pytest -q
node --check app/static/app.js
.venv/bin/pip check
git diff --check
```

The new release also requires fresh migration, scratch-browser, Docker
persistence, and backup/restore checks described in the active build plan.

## First-release boundary

The target includes Main currency/manual valuation rates, Operations,
account-specific periods, revised Transactions and Plan behavior, and a
single-container Docker deployment. Blockchain/exchange synchronization, real
Scan/OCR, full Analytics reports, XLSX export, external market-rate providers,
bank APIs, Telegram, Google Sheets, pools, goals, and category limits remain
future work.
