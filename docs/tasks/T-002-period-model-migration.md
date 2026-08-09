---
id: T-002
title: Replace the account-period model and migrate the schema
status: backlog
size: M
spec: specs/ACCOUNT_PERIODS-v2.1.md §3
blocked-by: [T-001]
branch: task/T-002-period-model-migration
base-commit:
implementer:
readiness-reviewed-by:
readiness-reviewed-commit:
readiness-verdict:
---

## Goal

The period table stores the v2.1 snapshot model with no column that can act as
a second independently editable representation of account money.

## Acceptance

- [ ] The period model persists `account_id`, `asset_id`, `start_date`,
      `end_date`, `snapshot_at`, `opening_balance`, `rollover_policy`, `created_at`,
      `closed_at`, and `closing_balance`.
- [ ] `account_id` and `asset_id` are immutable. `snapshot_at` and
      `opening_balance` change only through the T-007 current-period Start-date
      operation and are immutable for ended/closed history.
- [ ] `end_date` is inclusive and a period with `end_date < start_date` is
      rejected.
- [ ] `closed_at` and `closing_balance` are nullable and are written together
      or not at all.
- [ ] `rollover_policy` accepts only the two approved stable values.
- [ ] `funding_amount` no longer participates in the period model or domain
      calculation. Removing it from public responses belongs to T-009.
- [ ] `planned` is absent from the period model and period calculations.
- [ ] No stored column holds a mutable current balance.
- [ ] One Alembic revision upgrades a scratch database from
      `0001_release_v2`, and `alembic check` reports no pending operations.
- [ ] Money columns keep Decimal storage at crypto precision; no `float`
      appears in the model, migration, or domain guards.

## Touches

- `app/models.py`
- `app/periods.py` only for model invariants and transitional read removal
- `app/schemas.py` only where persistence validation requires it
- `alembic/versions/` — one new revision
- `tests/` — model and migration tests

## Out of scope

- Balance derivation and reconciliation — T-003.
- Lifecycle transitions, close, and successor rules — T-004.
- Start-date editing semantics — T-007.
- Public period/Operations response cleanup — T-008 and T-009.
- Frontend.

## Verification

```bash
task_tmp_dir="$(mktemp -d)"
export DATABASE_URL="sqlite+aiosqlite:///$task_tmp_dir/finapp.db"
.venv/bin/alembic upgrade 0001_release_v2
.venv/bin/alembic upgrade head
.venv/bin/alembic check
.venv/bin/python -m pytest tests/ -k "period or model or migration" -q
git status --short
git diff --check
unset DATABASE_URL
```

The explicit scratch URL is mandatory. Never run this task's migration gate
with `DATABASE_URL` unset because the repository fallback is `./finapp.db`.

## Review

### Pass 1

- Reviewer task name/vendor:
- Reviewed base/head or working-tree manifest:
- Findings (verbatim, P0–P3):
- Resolution:
- Reviewer checks:
- Verdict:

## Session log

- (empty)
