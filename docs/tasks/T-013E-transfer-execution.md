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
cross-asset exchange ledger event atomically after proving the quoted Main/rate
dependencies are still unchanged.

## Acceptance

- [ ] `POST /api/v1/operations/transfer/quotes/{quote_id}/execute` requires a
      positive integer path ID and a JSON object body; `{}` is valid and an
      omitted/non-object body is `422`. The body has exactly five optional
      properties and no required properties: `local_date` is ISO `date` string
      or null (default null); `occurred_at` is ISO `date-time` string or null
      (default null); `note` is string up to 2000 characters or null (default
      null); `counterparty` is string up to 160 characters or null (default
      null); and `confirm_ended_period` is boolean (default false). Unknown
      members are `422` and do not consume the quote. It accepts no amount,
      account, asset, rate, fee, status, creator, or workspace override.
- [ ] OpenAPI freezes the execute request's exact property/required/type/
      format/max-length/default/additional-property sets, positive integer path
      type, `201` success status, existing `TransactionOut` response reference,
      and documented `404`/`409`/`422` errors.
- [ ] Only the quote creator may execute it, and execution rechecks current
      transaction-create/edit permission on both quoted accounts. Hidden,
      foreign-workspace, inaccessible, or archived accounts preserve accepted
      privacy/error semantics. Same-asset execution retains the accepted shared
      editor/contributor behavior. Cross-asset execution rechecks owner-only
      workspace authorization and never exposes private rate state to shared or
      foreign users.
- [ ] A cross-asset quote is stale and non-consumable when the workspace's
      current Main ID differs from the quoted Main ID or any source/target
      manual-rate dependency row is missing or differs in ID, exact stored
      value, direction, or updated timestamp. A historical Main switch away and
      back is deliberately not stale when the current ID and every rate
      dependency still match. Same-asset quotes have no rate dependency.
- [ ] Execution atomically claims a quote only when status is `open`, it has
      not expired under one captured server clock (`now < expires_at`), and no
      executed transaction is linked. Errors are exact: hidden/unknown is `404
      Transfer quote not found`; expiry is `409 Transfer quote has expired`;
      Main/rate dependency mismatch is `409 Transfer quote is stale`; and an
      executed quote, including the loser of a concurrent race after the winner
      commits, is `409 Transfer quote has already been executed`.
- [ ] Before reading mutable quote/Main/rate/account state, execution reserves
      the SQLite writer with the accepted `BEGIN IMMEDIATE` pattern; on a
      row-locking database it locks the quote, workspace, dependency-rate, and
      participating account rows through commit. A final conditional quote
      update remains the single-winner guard; no process-local lock is
      authoritative. Sequential and real concurrent attempts create exactly
      one committed root transaction and one set of legs, period effects,
      captured exchange rates, and Undo cursor updates; the losing transaction
      rolls back every provisional row before returning the executed error.
- [ ] Same-asset execution creates the existing `transfer` root with equal
      signed legs. Cross-asset execution creates the existing `exchange` root
      with the quote's exact source/destination amounts and the existing two
      direction-tagged captured transaction rates derived from the actual
      legs. Both use `origin=operations`; no fee child is created by this
      one-amount mobile command.
- [ ] Execution never recalculates destination amount from current manual
      rates. The quote's captured amounts are the only leg amounts. Unchanged
      dependency rows produce legs and captured transaction exchange rates
      byte-for-value identical to the quote contract; updated/deleted rate rows
      produce `409 stale` before claim/transaction mutation.
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
- [ ] After successful execution, correction, soft Delete, or Undo of the root
      never reopens or unlinks the immutable quote and never makes it executable
      again. The quote remains `executed` and points to the same root; ordinary
      transaction status alone controls whether its captured exchange rates are
      eligible as valuation fallback.
- [ ] Before and after a no-fee quoted execution, Account summary Total capital
      is identical at Main precision. Same-asset transfers are exactly neutral;
      cross-asset execution is allowed only while the exact quote-time Main and
      manual-rate dependencies still match, so T-013Q's neutrality proof is the
      live valuation proof at execution. Stale updated/deleted-rate cases mutate
      no balance or summary. Both account balances and active/ended period
      projections change by their exact signed quote legs on success.
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

### Pass 1

- Reviewer task name/vendor: `/root/t013_readiness_review`, Codex same-vendor
  fallback; cross-vendor reviewer unavailable in this session.
- Reviewed task-file commit: `cddefcf` (combined T-013Q/T-013E readiness pass).
- Findings (verbatim, P0–P3): the reviewer returned one combined findings block
  for the split. Its complete verbatim text is recorded under
  [`T-013Q` Readiness Pass 1](T-013Q-transfer-quote.md#pass-1) and applies to
  both task files. T-013E-specific P1 findings were live-summary neutrality
  after rate change, unfrozen execute/OpenAPI types, and an underspecified
  exactly-once state machine; P2 findings were Main/expiry boundaries and
  permanent single use after correction/Delete/Undo. Combined verdict:
  **NOT READY**.
- Resolution: execution now stales on current Main/rate dependency mismatch;
  freezes request/path/OpenAPI/error types; defines one-clock expiry and a
  database conditional single-winner claim; keeps executed linkage permanent
  after correction/Delete/Undo; and promises live Total-capital neutrality only
  while quote-time dependencies still match. Fresh re-review is required.
- Reviewer checks: direct committed docs/spec/code/test inspection; supplied
  `git diff --check` passed; no application tests run for documentation-only
  readiness.
- Verdict: not ready; corrected and submitted for fresh re-review.

## Review

Append-only implementation review passes. A different read-only agent returns
the review; the implementer records it verbatim following
[`../REVIEW_PROTOCOL-v2.md`](../REVIEW_PROTOCOL-v2.md).

## Session log

- 2026-08-11 Codex: drafted the bounded execution half of T-013. It remains
  blocked by accepted T-013Q; readiness review, owner promotion, branch claim,
  implementation, and implementation review remain. No application code or
  database was changed.
- 2026-08-11 Codex: recorded and resolved the combined readiness Pass 1
  execution findings: changed dependencies stale the quote, execute/OpenAPI and
  exact errors are frozen, database serialization is explicit, and successful
  linkage is permanent. Fresh readiness re-review remains; no application code
  or database was changed.
