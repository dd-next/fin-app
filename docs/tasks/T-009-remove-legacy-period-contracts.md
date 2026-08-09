---
id: T-009
title: Remove legacy period money contracts
status: backlog
size: S
spec: specs/ACCOUNT_PERIODS-v2.1.md §3, §9–§10
blocked-by: [T-008]
branch: task/T-009-remove-legacy-period-contracts
base-commit:
implementer:
readiness-reviewed-by:
readiness-reviewed-commit:
readiness-verdict:
---

## Goal

The period API and its existing desktop consumer expose only ledger-derived
opening/current/closing facts and allowance, with every T-008 transitional
`funding_amount`, `remaining`, `planned`, and period-confirmation contract
removed.

## Acceptance

- [ ] `AccountPeriodCreate` contains only optional `start_date`, required
      `end_date`, and optional `rollover_policy`; `AccountPeriodPatch` contains
      only those same three optional business fields. Because both schemas
      keep `extra="forbid"`, any supplied `funding_amount` or
      `confirm_ended_period` value (including null, malformed text, arrays, or
      objects), alone or combined with valid fields, returns deterministic
      `422` before domain mutation.
- [ ] Current, ended, and closed response schemas and every create/current/
      list/detail/PATCH/close response omit `funding_amount`, `remaining`, and
      `planned`. OpenAPI contains none of those properties in any account
      period request or response component.
- [ ] Final lifecycle shapes otherwise remain exactly as accepted in T-008:
      current returns `opening_balance`, `current_balance`, and
      `available_today`; ended returns the historical opening snapshot and
      null close pair without live fields; closed returns opening and closing
      snapshots without live fields. Asset-precision `ROUND_HALF_UP`, exact
      internal Decimal invariants, one route cutoff T, policy behavior, and
      current/null lookup do not change.
- [ ] Period serialization and routes have no `PlanRule`, `PlanOccurrence`, or
      `RebaseEvent` query/import and no legacy zero/alias assignment. The Plan
      subsystem and its `planned_amount` contracts remain unchanged and no
      planned event affects balance or allowance.
- [ ] The existing desktop SPA stops submitting or reading the removed period
      members: the period dialog has no Funding input, create/PATCH submits
      only Start/end, current presentation reads `current_balance`, and
      history renders only opening/current-or-closing lifecycle facts. This is
      a mechanical compatibility update, not a Phase 15 visual redesign.
- [ ] Dormant RebaseEvent storage/relationships and Alembic revision
      `0002_period_snapshot_model` remain unchanged. No schema migration,
      model removal, legacy-row migration, or database reset is introduced.
- [ ] Focused tests prove the exhaustive removed-input matrix is mutation
      neutral, exact key omission for current/ended/closed and every period
      route, OpenAPI removal, unchanged VND/18-decimal presentation,
      unchanged Plan behavior, and absence of removed SPA request/response
      references. Existing lifecycle, allowance, Transactions-filter,
      operations, frontend, and full-suite regressions pass.

## Touches

- `app/schemas.py`
- `app/periods.py`
- `app/static/app.js`
- `app/static/index.html`
- `tests/test_period_contract_removal_v21.py`
- `tests/test_period_api_v21.py`
- `tests/test_periods_v2.py` and existing period/operations/frontend tests
  only where a T-008 transitional request, response, or UI assertion is
  mechanically superseded
- `docs/tasks/T-009-remove-legacy-period-contracts.md`
- `docs/BACKLOG.md` and `docs/PROGRESS.md` for task lifecycle only

## Out of scope

- Permission or shared-account behavior changes — T-010.
- Models, migrations, dormant RebaseEvent storage, ledger commands, allowance
  formulas, lifecycle/snapshot boundaries, Transactions period membership,
  Plan semantics, or new API fields.
- Phase 15 mobile UI, desktop visual redesign, new planning/forecasting
  concepts, deployment, or push.

## Verification

```bash
.venv/bin/python -m pytest tests/test_period_contract_removal_v21.py -q
.venv/bin/python -m pytest tests/test_period_api_v21.py tests/test_periods_v2.py tests/test_period_lifecycle_v2.py tests/test_period_start_replay_v2.py -q
.venv/bin/python -m pytest tests/test_transactions_phase12_v2.py tests/test_phase12_privacy_v2.py tests/test_operations_v2.py tests/test_operations_undo_v2.py -q
.venv/bin/python -m pytest tests/test_plan_v2.py tests/test_frontend_v2.py -q
.venv/bin/python -m pytest -q
node --check app/static/app.js
git diff --check
git status --short
```

All DB-backed tests use isolated in-memory fixtures. Any migration/manual DB
command must set an explicit scratch `DATABASE_URL`; `finapp.db` is never used.

## Readiness review

Append-only readiness passes against ACCOUNT_PERIODS-v2.1 §§3, 9–10, the
accepted T-008 transition matrix, ADR-0005, AGENTS, BACKLOG, and
REVIEW_PROTOCOL. Readiness must confirm this remains a mechanical S removal,
including the bounded existing-desktop consumer update, and does not absorb
T-010 permissions or schema/model work.

### Pass <N>

- Reviewer task name/vendor:
- Reviewed task-file commit:
- Findings (verbatim, P0–P3):
- Resolution:
- Verdict:

## Review

Append-only implementation review passes. A different read-only agent returns
the review; the implementer records it verbatim following
[`../REVIEW_PROTOCOL-v2.md`](../REVIEW_PROTOCOL-v2.md).

### Pass <N>

- Reviewer task name/vendor:
- Reviewed base/head or working-tree manifest:
- Findings (verbatim, P0–P3):
- Resolution:
- Reviewer checks:
- Verdict:

## Session log

Append-only. Every session that touches this task adds one entry before it
ends. Date · agent · what landed · what is left · open questions.

- 2026-08-09 Codex: specified the bounded final removal immediately after
  local T-008 acceptance. Readiness, owner promotion, exact branch claim,
  implementation, review, and acceptance remain; no open question.
