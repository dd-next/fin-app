---
id: T-030B
title: Preserve desktop and run the Phase 15 regression gate
status: backlog
size: M
spec: BUILD_PLAN-v2.md Phase 15; specs/FinnApp-v2.md
blocked-by: [T-030A]
branch: task/T-030B-desktop-regression
base-commit:
implementer:
readiness-reviewed-by:
readiness-reviewed-commit:
readiness-verdict:
---

## Goal

Prove the responsive redesign retains supported desktop behavior and passes the
complete Phase 15 runtime regression gate.

## Acceptance

- [ ] A 1280×900 scratch-browser pass covers Accounts, Transactions,
      Operations, periods, Plan, Analytics, Profile, rates, categories, sharing
      and logout.
- [ ] Existing desktop capabilities omitted by mobile remain reachable, except
      only explicitly deferred new controls; there is no horizontal overflow,
      hidden/unreachable action, broken navigation, or console error.
- [ ] Full pytest passes, including financial, period, feed, Plan, privacy and
      permission suites; JS syntax, dependency, diff and clean-status manifest
      gates pass.
- [ ] A fresh explicit scratch DB upgrades to exactly one Alembic head;
      `alembic check`, `/health` and SPA `/` pass.
- [ ] Any fix is a bounded regression correction; no new desktop design,
      backend contract, schema, or deferred product capability is introduced.

## Touches

Frontend/tests only for demonstrated regression fixes, this task and progress
evidence. Backend/schema/migration changes require a new task and stop this one.

## Out of scope

New desktop design, feature expansion, populated migration/downgrade under
ADR-0010, push/deploy, task archival, phase acceptance.

## Verification

```bash
.venv/bin/python -m pytest -q
node --check app/static/app.js
.venv/bin/pip check
git diff --check
.venv/bin/alembic heads
```

With an explicit fresh scratch `DATABASE_URL`: `alembic upgrade head`,
`alembic check`, Uvicorn `/health` and `/`; use `verify` for the 1280×900 matrix
and record `git status --short`.

## Review

Append the bounded independent implementation review following the protocol.

## Session log

- 2026-08-12 Codex GPT-5: task split from former L-sized T-030; not claimed.
