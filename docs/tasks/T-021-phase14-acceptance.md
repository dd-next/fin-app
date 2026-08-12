---
id: T-021
title: Run the lean Phase 14 backend acceptance gate
status: done
size: M
spec: specs/ACCOUNT_PERIODS-v2.1.md §12 and design/MOBILE-BACKEND-GAP-AUDIT.md
blocked-by: [T-009, T-010, T-012, T-013Q, T-013E, T-014F, T-014P, T-019]
branch: task/T-021-phase14-acceptance
base-commit: 79bbe1f
implementer: Codex GPT-5
readiness-reviewed-by: owner fast-track exception
readiness-reviewed-commit: 79bbe1f
readiness-verdict: ready
---

## Goal

The retained Phase 14 backend contracts pass one lean smoke matrix and the
owner-approved final release gates on a fresh disposable database.

## Acceptance

- [x] Focused smoke nodes cover period lifecycle/projection, exact manual rates,
  quote and atomic execute, financial-date feed, planned projections, and the
  T-019 mobile Plan adapter without creating a new compatibility matrix.
- [x] Complete pytest and JavaScript syntax pass once for Phase 14.
- [x] A fresh explicit scratch database upgrades to the single Alembic head;
  `alembic check` reports no pending operations.
- [x] The application starts on that scratch database; `/health` returns 200
  with `{"status":"ok"}` and `/` returns the SPA.
- [x] `git diff --check` passes and the reviewed manifest contains no product
  behavior, schema, ledger, or migration changes.

## Touches

This task file, backlog/progress state, and verification evidence only.

## Out of scope

No populated migration, downgrade, preservation check, new exhaustive matrix,
runtime behavior change, compatibility work, or Phase 15 UI.

## Verification

```bash
.venv/bin/python -m pytest -q <seven retained-contract smoke nodes>
.venv/bin/python -m pytest -q
node --check app/static/app.js
DATABASE_URL=sqlite+aiosqlite:////private/tmp/<scratch>/finapp.db .venv/bin/alembic upgrade head
.venv/bin/alembic heads
DATABASE_URL=sqlite+aiosqlite:////private/tmp/<scratch>/finapp.db .venv/bin/alembic check
DATABASE_URL=sqlite+aiosqlite:////private/tmp/<scratch>/finapp.db .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8765
curl -sS -i http://127.0.0.1:8765/health
curl -sS -i http://127.0.0.1:8765/
git diff --check
```

## Review

### Pass 1

- Reviewer task name/vendor: `/root/t021_review`, Codex GPT-5.6 Terra medium;
  same-vendor fallback because a cross-vendor reviewer was unavailable.
- Reviewed base/head or working-tree manifest: base/HEAD `79bbe1f`; modified
  `docs/BACKLOG.md` and untracked task file; no runtime/schema/migration diff.
- Findings (P0–P3): no findings.
- Resolution: none.
- Reviewer checks: inspected every recorded gate and re-ran Node syntax,
  `git diff --check`, and `alembic heads`; all passed. The ambient default DB is
  intentionally outside ADR-0010; the required explicit fresh-scratch
  `alembic check` passed.
- Verdict: clean; no open P0–P3.

## Evidence

- Retained-contract smoke: seven named nodes covering period lifecycle,
  canonical manual rate, cross-asset quote, captured atomic execution,
  financial-date type mapping, planned actions, and mobile Plan adapter —
  `7 passed in 1.06s`.
- Complete pytest: `341 passed, 246 warnings in 32.45s`; warnings are the
  existing Python 3.12 SQLite datetime/date adapter deprecations.
- `node --check app/static/app.js` and `git diff --check` — passed.
- `.venv/bin/alembic heads` — exactly `0004_transfer_quotes (head)`.
- Fresh explicit scratch DB `/private/tmp/finapp-t021.teZNt1/finapp.db` upgraded
  `0001 → 0002 → 0003 → 0004`; `alembic check` — `No new upgrade operations
  detected.` No populated upgrade or downgrade was run.
- Uvicorn started against that same scratch DB; `GET /health` returned 200
  `{"status":"ok"}` and `GET /` returned 200 `text/html` with the FinApp v2 SPA.

## Session log

- 2026-08-12 Codex GPT-5: claimed from accepted T-019 commit `79bbe1f` under
  ADR-0010; running the bounded retained-contract and final Phase 14 gates.
- 2026-08-12 Codex GPT-5: all targeted/final/fresh-schema/live-app gates passed;
  independent review, documentation commit, and fast-forward acceptance remain.
- 2026-08-12 Codex GPT-5: independent review found no P0–P3; the lean Phase 14
  acceptance gate is complete and nothing remains for T-021.
