---
id: T-013E
title: Execute a bound Transfer quote atomically
status: backlog
size: M
spec: design/MOBILE-BACKEND-GAP-AUDIT.md cross-asset Transfer
blocked-by: [T-013Q]
branch: task/T-013E-transfer-execution
base-commit:
implementer:
readiness-reviewed-by:
readiness-reviewed-commit:
readiness-verdict:
---

## Goal

An authorized caller can execute one unexpired T-013Q quote exactly once, with
the persisted amounts producing the accepted same-asset transfer or
cross-asset exchange ledger event atomically and without re-reading a changed
manual rate.

## Acceptance

- [ ] `POST /api/v1/operations/transfer/quotes/{quote_id}/execute` accepts only
      optional `local_date`, `occurred_at`, `note`, `counterparty`, and
      `confirm_ended_period`; it accepts no amount, account, asset, rate, fee,
      status, creator, or workspace override. Unknown members are `422` and do
      not consume the quote.
- [ ] Only the quote creator may execute it, and execution rechecks current
      transaction-create/edit permission on both quoted accounts. Hidden,
      foreign-workspace, inaccessible, or archived accounts preserve accepted
      privacy/error semantics. A workspace Main-asset change makes the quote
      stale and non-consumable; a later manual-rate change/delete does not.
- [ ] Execution atomically claims a quote only when status is `open`, it has
      not expired, and no executed transaction is linked. Expired, already
      executed, and concurrently claimed quotes return stable distinct
      `409` errors. Sequential and real concurrent attempts create exactly one
      root transaction and one set of legs, period effects, captured exchange
      rates, and Undo cursor updates.
- [ ] Same-asset execution creates the existing `transfer` root with equal
      signed legs. Cross-asset execution creates the existing `exchange` root
      with the quote's exact source/destination amounts and the existing two
      direction-tagged captured transaction rates derived from the actual
      legs. Both use `origin=operations`; no fee child is created by this
      one-amount mobile command.
- [ ] Execution never recalculates destination amount from current manual
      rates. The quote's captured amounts are the only leg amounts; changing or
      deleting a rate between quote and execution leaves the resulting legs
      and captured transaction exchange rates byte-for-value identical to the
      quote contract.
- [ ] The transaction write, quote `executed` transition/link, period replay or
      ended-period guard, and creator/account Undo cursor advancement commit in
      one database transaction. Any validation, permission, period-confirmation,
      constraint, or injected flush/commit failure rolls all of them back and
      leaves the still-valid quote open for a corrected retry.
- [ ] Existing exact financial-time precedence, workspace-local date, future
      date guards, ended-period confirmation, signed-leg replay for both
      accounts, closed-history immutability, and owner-private shared-period
      behavior remain unchanged and are focused-regression protected.
- [ ] The response is the existing full `TransactionOut`; the quote row links
      exactly that root transaction. Transaction detail, soft delete, creator-
      scoped persistent Undo, and voided captured-rate eligibility behave the
      same as for the corresponding shipped explicit transfer/exchange.
- [ ] Before and after a no-fee quoted execution, Account summary Total capital
      is identical at Main precision. Same-asset transfers are exactly neutral;
      cross-asset quotes use the neutrality proof accepted in T-013Q. Both
      account balances and active/ended period projections change by their
      exact signed quote legs.
- [ ] Existing `POST /api/v1/operations/transfer` remains same-asset-only and
      existing `POST /api/v1/operations/exchange` remains explicit two-amount
      with optional fee for the preserved desktop. Their OpenAPI and regression
      behavior do not change.
- [ ] Focused execution/replay/concurrency/permissions/period/Undo/OpenAPI
      tests, full pytest, Node syntax, and diff/status checks pass on isolated
      fixtures. No migration or production/local database command is needed in
      this task after accepted T-013Q schema installation.

## Touches

- `app/schemas.py`
- `app/transfer_quotes.py`
- `app/operations.py` and `app/transactions.py` only to reuse the existing
  atomic transfer/exchange creation path without weakening legacy routes
- `app/operations_undo.py` only if the shared commit boundary requires a
  bounded extraction
- `tests/test_transfer_quote_execution_v21.py`
- existing operation/period/Undo tests only for direct regressions
- `docs/tasks/T-013E-transfer-execution.md`
- `docs/BACKLOG.md` and `docs/PROGRESS.md` for task lifecycle only

## Out of scope

- Quote calculation/schema/migration, rate CRUD/storage meaning, automatic
  rates, fees on the one-amount command, transaction type conversion, feed
  mapping, mobile/desktop UI changes, or Phase 15.
- Quote listing/refresh/cancellation, cleanup workers, hard deletion, changes
  to explicit exchange input, or resetting/reading `finapp.db`.

## Verification

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_transfer_quote_execution_v21.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_operations_v2.py tests/test_operations_undo_v2.py tests/test_periods_v2.py tests/test_period_permissions_v21.py -q
.\.venv\Scripts\python.exe -m pytest -q
node --check app/static/app.js
git diff --check
git status --short
```

All database-backed tests use isolated fixtures. No command may fall back to,
open, replace, or delete `finapp.db`.

## Readiness review

Append-only readiness passes against accepted T-013Q, the transfer audit,
shipped transaction/period/permission/Undo contracts, AGENTS, BACKLOG,
BUILD_PLAN, and REVIEW_PROTOCOL.

## Review

Append-only implementation review passes. A different read-only agent returns
the review; the implementer records it verbatim following
[`../REVIEW_PROTOCOL-v2.md`](../REVIEW_PROTOCOL-v2.md).

## Session log

- 2026-08-11 Codex: drafted the bounded execution half of T-013. It remains
  blocked by accepted T-013Q; readiness review, owner promotion, branch claim,
  implementation, and implementation review remain. No application code or
  database was changed.
