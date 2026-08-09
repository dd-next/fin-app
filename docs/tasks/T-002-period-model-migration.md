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
      `0001_release_v2`, including populated legacy period rows, and the final
      `alembic check` reports no pending operations.
- [ ] The populated upgrade preserves period IDs, dates, creator, account,
      asset, timestamps, and dependent `rebase_event` rows; it never copies
      legacy `funding_amount` into a v2.1 balance field.
- [ ] For each compatible legacy row, the migration derives `snapshot_at` as
      the later of the workspace-local `start_date` boundary and the preceding
      same-account period boundary, then derives `opening_balance` from posted
      signed account legs with `leg.created_at <= snapshot_at`.
- [ ] A manually closed legacy row keeps `closed_at` and receives a
      `closing_balance` derived from posted signed account legs with
      `leg.created_at <= closed_at`; an open or naturally ended row has both
      closing fields null. Every migrated row defaults to
      `redistribute_remaining_days`.
- [ ] Before changing schema or rows, the populated upgrade fails explicitly
      and leaves the database at `0001_release_v2` when legacy data cannot be
      represented without invention or loss: a future `start_date`,
      `end_date < start_date`, overlapping same-account ranges, account/asset
      mismatch, or invalid workspace timezone.
- [ ] Migration tests cover empty upgrade, current/open, naturally ended, and
      manually closed populated rows, an exact snapshot-boundary leg, preserved
      `rebase_event` linkage, and one rejected incompatible fixture whose
      original schema/data remain readable.
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
.venv/bin/python -m pytest tests/test_migrations_v2.py tests/test_periods_v2.py \
  -k "period or model or migration" -q
git status --short
git diff --check
unset DATABASE_URL
```

The explicit scratch URL is mandatory. Never run this task's migration gate
with `DATABASE_URL` unset because the repository fallback is `./finapp.db`.

## Readiness review

### Pass 1

- Reviewer task name/vendor: `/root/t002_readiness_fast`, Codex same-vendor
  fallback; cross-vendor reviewer unavailable in this session.
- Reviewed task-file commit: `6bfa5a4`.
- Findings (verbatim, P0–P3):

  > P0: None.
  >
  > P1 — `T-002` does not define or test migration of populated
  > `0001_release_v2` databases. The old schema contains only
  > `funding_amount`, `created_at`, and optional `closed_at`
  > (`alembic/versions/0001_release_v2.py:550`), while the task requires
  > `snapshot_at`, `opening_balance`, `rollover_policy`, and paired
  > `closing_balance` (`docs/tasks/T-002-period-model-migration.md:23`). The
  > specification requires those snapshots to have exact financial meaning
  > (`docs/specs/ACCOUNT_PERIODS-v2.1.md:63`), but the task neither defines
  > deterministic backfill values nor requires a populated migration fixture.
  > Its verification currently exercises only an empty `0001` database
  > (`docs/tasks/T-002-period-model-migration.md:61`). Before readiness,
  > specify the bounded one-time mapping for open, ended, and manually closed
  > legacy rows—including the default rollover policy and
  > `closed_at`/`closing_balance` consistency—and require both empty and
  > populated upgrade tests. This can remain migration-only without
  > implementing T-003 runtime reconciliation or T-007 editing.
  >
  > P2: None.
  >
  > P3: None.
- Resolution: populated-row mapping, safe rejection conditions, and required
  migration fixtures added without adding T-003 runtime reconciliation or
  T-007 editing to this task.
- Verdict: not ready; corrected and submitted for a fresh readiness review.

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
