---
id: T-010
title: Keep owner-private periods non-authorizing for shared users
status: backlog
size: M
spec: specs/ACCOUNT_PERIODS-v2.1.md §11
blocked-by: [T-008]
branch: task/T-010-owner-private-period-permissions
base-commit:
implementer:
readiness-reviewed-by:
readiness-reviewed-commit:
readiness-verdict:
---

## Goal

Account periods remain fully owner-private and never change which otherwise
permitted financial actions a shared-account user can perform or which generic
permission/confirmation result that user receives.

## Acceptance

- [ ] For each `editor`, `contributor`, and `viewer`, collection routes
      `POST/GET /accounts/{account_id}/periods` and
      `GET /accounts/{account_id}/periods/current` return the same owner-private
      `404 Account not found` as a foreign user. Detail/PATCH/close routes for
      known current, ended, and closed IDs return the same
      `404 Account period not found` as an unknown ID. Responses never contain
      lifecycle, date, balance, policy, allowance, or creator facts, and every
      rejected write is mutation-neutral.
- [ ] `GET /transactions?period_id=...` is owner-private for every shared role
      and foreign user. A known period ID, an unknown period ID, and a known ID
      combined with matching or mismatching `account_id` all return the same
      `404 Account period not found` before account-filter validation, without
      returning transaction rows or period facts.
- [ ] A shared `editor` can Spend, Add funds, Transfer, and Exchange on the
      same participating accounts permitted by the existing role matrix, and a
      shared `contributor` can Spend. Each allowed create has the same HTTP
      status and public transaction shape when the account owner's relevant
      period state is absent, current, naturally ended, or manually closed.
      Hidden ended periods require no period confirmation from a shared user;
      current balances remain ledger-derived and closed snapshots remain
      immutable.
- [ ] Shared transaction correction, Delete, and Operations Undo retain their
      existing generic shared confirmation contract regardless of absent,
      current, ended, or closed hidden period state: an unconfirmed permitted
      mutation returns exactly `409 Shared transaction correction requires
      explicit confirmation`, a confirmed mutation follows the existing
      success path, and neither response mentions a period or differs because
      of one. No shared response returns the owner-only `Ended account period
      change requires explicit confirmation` or the transitional hidden-state
      string `Transaction change requires explicit confirmation`.
- [ ] Existing role and participating-account authorization remains the first
      effective boundary: contributor Add funds/Transfer/Exchange/edit/Delete,
      all viewer writes, and any Transfer/Exchange with a forbidden or foreign
      source, target, or fee account retain their accepted `403`/`404` result
      with or without a hidden period and do not mutate any transaction, leg,
      rate, Undo, period, or snapshot row.
- [ ] Account owners retain the accepted T-008 behavior. A financial change
      inside their naturally ended period returns `409 Ended account period
      change requires explicit confirmation` until the retained transaction
      `confirm_ended_period` member is true; current/closed/no-period behavior,
      period route access, exact Decimal ledger effects, and closed snapshot
      immutability do not change.
- [ ] The shared-user privacy decision is centralized in the period-impact
      guard rather than duplicated per command. Period read/write routes still
      use owner-only account lookup; no public schema, model, migration,
      rollover formula, lifecycle boundary, transaction visibility/redaction,
      sharing-role definition, or desktop UI contract changes.
- [ ] Focused tests cover all period routes and Transactions period filtering,
      the create/correction/Delete/Undo matrix, every shared role, multi-account
      source/target/fee permissions, owner regression, mutation neutrality, and
      exact error text. Existing period, operations, transactions, sharing,
      privacy, frontend, and full-suite regressions pass.

## Touches

- `app/periods.py`
- `tests/test_period_permissions_v21.py`
- `tests/test_periods_v2.py`, `tests/test_operations_v2.py`,
  `tests/test_operations_undo_v2.py`, `tests/test_sharing_v2.py`, and existing
  privacy/transaction tests only where an old hidden-period shared-user
  expectation is mechanically superseded
- `docs/tasks/T-010-owner-private-period-permissions.md`
- `docs/BACKLOG.md` and `docs/PROGRESS.md` for task lifecycle only

## Out of scope

- New roles, changes to the accepted Viewer/Contributor/Editor action matrix,
  account ownership transfer, workspace permissions, invitation behavior, or
  transaction visibility/redaction changes.
- Period schemas, lifecycle/snapshot/allowance math, transaction confirmation
  field removal/rename, models, migrations, database reset, or dormant
  RebaseEvent cleanup.
- T-012 rates, T-013 transfer quote/execution, later Phase 14 tasks, Phase 15
  mobile UI, deployment, push, or PR creation.

## Verification

```bash
.venv/bin/python -m pytest tests/test_period_permissions_v21.py -q
.venv/bin/python -m pytest tests/test_period_api_v21.py tests/test_period_contract_removal_v21.py tests/test_periods_v2.py -q
.venv/bin/python -m pytest tests/test_operations_v2.py tests/test_operations_undo_v2.py tests/test_transactions_phase12_v2.py tests/test_phase12_privacy_v2.py tests/test_sharing_v2.py -q
.venv/bin/python -m pytest -q
node --check app/static/app.js
git diff --check
git status --short
```

All DB-backed tests use isolated in-memory fixtures. Any migration/manual DB
command must set an explicit scratch `DATABASE_URL`; `finapp.db` is never used.

## Readiness review

Append-only readiness passes against ACCOUNT_PERIODS-v2.1 §11, the accepted
T-008/T-009 privacy and transaction-confirmation contracts, AGENTS, BACKLOG,
and REVIEW_PROTOCOL. Readiness must confirm that private period state becomes
non-authorizing only for shared users, while owner confirmation and the
existing generic shared correction confirmation remain intact.

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

- 2026-08-11 Codex: drafted the bounded owner-private permission task after
  local T-009 acceptance. Independent readiness review, owner promotion, exact
  branch claim, implementation, and review remain; no open question.
