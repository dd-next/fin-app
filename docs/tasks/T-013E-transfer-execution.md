---
id: T-013E
title: Execute a bound Transfer quote atomically
status: in-progress
size: M
spec: design/MOBILE-BACKEND-GAP-AUDIT.md cross-asset Transfer
blocked-by: [T-013Q]
branch: task/T-013E-transfer-execution
base-commit: f7b0d12ec12cec58fc7801a1af56b552ec809821
implementer: Codex
readiness-reviewed-by: /root/t013_readiness_confirmation (Codex same-vendor fallback)
readiness-reviewed-commit: dacb871
readiness-verdict: ready
---

## Goal

An authorized caller can execute one unexpired T-013Q quote exactly once, with
the persisted amounts producing the accepted same-asset transfer or
cross-asset exchange ledger event atomically after proving the quoted Main/rate
dependencies are still unchanged.

## Acceptance

- [x] `POST /api/v1/operations/transfer/quotes/{quote_id}/execute` requires a
      positive integer path ID and a JSON object body; `{}` is valid and an
      omitted/non-object body is `422`. The body has exactly five optional
      properties and no required properties: `local_date` is ISO `date` string
      or null (default null); `occurred_at` is ISO `date-time` string or null
      (default null); `note` is string up to 2000 characters or null (default
      null); `counterparty` is string up to 160 characters or null (default
      null); and `confirm_ended_period` is boolean (default false). Unknown
      members are `422` and do not consume the quote. It accepts no amount,
      account, asset, rate, fee, status, creator, or workspace override.
- [x] OpenAPI freezes the execute request's exact property/required/type/
      format/max-length/default/additional-property sets, positive integer path
      type, `201` success status, existing `TransactionOut` response reference,
      and documented `404`/`409`/`422` errors.
- [x] Only the quote creator may execute it, and execution rechecks current
      owner authorization and current `edit` permission on both quoted accounts.
      Hidden, foreign-workspace, inaccessible, or archived accounts preserve
      accepted privacy/error semantics. Both identity and cross-asset execution
      are owner-only; the preserved direct same-asset transfer route retains
      shipped editor behavior. The quote surface never exposes private rate
      state to shared or foreign users.
- [x] A cross-asset quote is stale and non-consumable when the workspace's
      current Main ID differs from the quoted Main ID or any source/target
      manual-rate dependency row is missing or differs in ID, exact stored
      value, direction, or updated timestamp. A historical Main switch away and
      back is deliberately not stale when the current ID and every rate
      dependency still match. Same-asset quotes have no rate dependency.
      For same-asset execution, an applicable current manual row tagged legacy
      also makes the quote stale; Main/canonical/fallback/unvalued linear paths
      remain eligible without persisting a private rate dependency.
- [x] Execution atomically claims a quote only when status is `open`, it has
      not expired under one captured server clock (`now < expires_at`), and no
      executed transaction is linked. Errors are exact: hidden/unknown is `404
      Transfer quote not found`; expiry is `409 Transfer quote has expired`;
      Main/rate dependency mismatch is `409 Transfer quote is stale`; and an
      executed quote, including the loser of a concurrent race after the winner
      commits, is `409 Transfer quote has already been executed`.
- [x] After visibility/creator and current permission/privacy checks, conflict
      precedence is deterministic: `executed` wins over expiry and staleness;
      for an open quote, expiry (`now >= expires_at`) wins over staleness; stale
      is evaluated only for an unexpired open quote. Tests cover executed plus
      expired/stale, open expired plus stale, and exact-boundary expiry.
- [x] Before reading mutable quote/Main/rate/account state, execution reserves
      the SQLite writer with the accepted `BEGIN IMMEDIATE` pattern; on a
      row-locking database it locks the quote, workspace, dependency-rate, and
      participating account rows through commit. A final conditional quote
      update remains the single-winner guard; no process-local lock is
      authoritative. Sequential and real concurrent attempts create exactly
      one committed root transaction and one set of legs, period effects,
      captured exchange rates, and Undo cursor updates; the losing transaction
      rolls back every provisional row before returning the executed error.
- [x] Same-asset execution creates the existing `transfer` root with equal
      signed legs. Cross-asset execution creates the existing `exchange` root
      with the quote's exact source/destination amounts and the existing two
      direction-tagged captured transaction rates derived from the actual
      legs. Both use `origin=operations`; no fee child is created by this
      one-amount mobile command.
- [x] Execution never recalculates destination amount from current manual
      rates. The quote's captured amounts are the only leg amounts. Unchanged
      dependency rows produce legs and captured transaction exchange rates
      byte-for-value identical to the quote contract; updated/deleted rate rows
      produce `409 stale` before claim/transaction mutation.
- [x] The transaction write, quote `executed` transition/link, period replay or
      ended-period guard, and creator/account Undo cursor advancement commit in
      one database transaction. Any validation, permission, period-confirmation,
      constraint, or injected flush/commit failure rolls all of them back and
      leaves the still-valid quote open for a corrected retry.
- [x] Existing exact financial-time precedence, workspace-local date, future
      date guards, ended-period confirmation, signed-leg replay for both
      accounts, closed-history immutability, and owner-private shared-period
      behavior remain unchanged and are focused-regression protected.
- [x] The response is the existing full `TransactionOut`; the quote row links
      exactly that root transaction. Transaction detail, soft delete, creator-
      scoped persistent Undo, and voided captured-rate eligibility behave the
      same as for the corresponding shipped explicit transfer/exchange.
- [x] After successful execution, correction, soft Delete, or Undo of the root
      never reopens or unlinks the immutable quote and never makes it executable
      again. The quote remains `executed` and points to the same root; ordinary
      transaction status alone controls whether its captured exchange rates are
      eligible as valuation fallback.
- [x] Before and after a no-fee quoted execution, Account summary Total capital
      is identical at Main precision. Same-asset transfers are exactly neutral;
      cross-asset execution is allowed only while the exact quote-time Main and
      canonical manual-rate dependencies still match. T-013Q rejects legacy
      divide dependencies and requires exact incoming/outgoing Main equality;
      canonical multiplication is additive across complete account balances, so
      arbitrary other balances cannot change the aggregate. Stale
      updated/deleted-rate cases mutate
      no balance or summary. Both account balances and active/ended period
      projections change by their exact signed quote legs on success.
- [x] Existing `POST /api/v1/operations/transfer` remains same-asset-only and
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
- `app/main.py` only to preserve the four explicit OpenAPI `default: null`
  members that FastAPI otherwise removes from its generated schema
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

### Pass 2

- Reviewer task name/vendor: `/root/t013_readiness_rereview`, fresh Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed task-file range: `cddefcf..508055f` (combined split-task pass).
- Findings (verbatim, P0–P3): the complete combined verbatim block is recorded
  under [`T-013Q` Readiness Pass 2](T-013Q-transfer-quote.md#pass-2). The
  T-013E-specific P1 was the invalid aggregate-neutrality proof and the P2 was
  unfrozen overlapping-conflict precedence; combined verdict: **NOT READY**.
- Resolution: execution now relies on exact pre-rounding Main-value equality,
  retains shipped owner/editor permission with contributor denied, and applies
  deterministic permissions → executed → expired → stale precedence. Fresh
  re-review is required.
- Reviewer checks: direct committed docs/spec/code/test inspection;
  `git diff --check cddefcf 508055f` passed; no application tests run for
  documentation-only readiness.
- Verdict: not ready; corrected and submitted for fresh re-review.

### Pass 3

- Reviewer task name/vendor: `/root/t013_readiness_final`, fresh Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed task-file range: `508055f..7c7b511` (combined split-task pass).
- Findings (verbatim, P0–P3): the complete combined verbatim block is recorded
  under [`T-013Q` Readiness Pass 3](T-013Q-transfer-quote.md#pass-3). The sole
  P1 showed that legacy divide valuation is not additive across complete account
  balances even when quoted leg values compare equal; verdict: **NOT READY**.
- Resolution: quote and execution are owner-only; applicable tagged legacy
  manual rows are rejected until explicitly resaved canonical through T-012;
  execution treats a newly applicable legacy row as stale. The execution
  neutrality proof now uses additive canonical multiplication only.
- Reviewer checks: direct committed docs/spec/code/test inspection;
  `git diff --check 508055f..7c7b511` passed; no application tests run for
  documentation-only readiness.
- Verdict: not ready; corrected and submitted for fresh re-review.

### Pass 4

- Reviewer task name/vendor: `/root/t013_readiness_confirmation`, fresh Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed task-file range: `7c7b511..dacb871` plus cumulative split-task
  readiness history.
- Findings (verbatim, P0–P3): the complete confirmation is recorded under
  [`T-013Q` Readiness Pass 4](T-013Q-transfer-quote.md#pass-4). It returned
  `P0: None`, `P1: None`, `P2: None`, and `P3: None`, confirmed the legacy
  counterexample cannot enter either quote path, and found no earlier
  privacy/API/state/concurrency/migration/lifecycle regression.
- Resolution: no change required; every prior readiness finding is closed.
- Reviewer checks: `git diff --check 7c7b511 dacb871` passed; worktree clean;
  no application tests run for documentation-only readiness.
- Verdict: ready, but remains blocked by accepted T-013Q implementation.

## Review

Append-only implementation review passes. A different read-only agent returns
the review; the implementer records it verbatim following
[`../REVIEW_PROTOCOL-v2.md`](../REVIEW_PROTOCOL-v2.md).

### Initial claim review

- Reviewer task name/vendor: `/root/t013q_domain_api_review`, fresh Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed manifest: branch `task/T-013E-transfer-execution` at HEAD/base
  `f7b0d12ec12cec58fc7801a1af56b552ec809821`; modified only
  `docs/BACKLOG.md`, `docs/PROGRESS.md`, and this task file.
- Findings (verbatim, P0–P3):

  > Reviewed manifest: branch `task/T-013E-transfer-execution` at HEAD/base `f7b0d12ec12cec58fc7801a1af56b552ec809821`, with only three modified documentation files: `docs/BACKLOG.md`, `docs/PROGRESS.md`, and `docs/tasks/T-013E-transfer-execution.md`; no untracked files. The complete tracked diff is the bounded `todo` → `in-progress` claim metadata/session handoff. `git diff --check` passed (line-ending warnings only).
  >
  > P0: None.
  >
  > P1: None.
  >
  > P2: None.
  >
  > P3: None.
  >
  > Approved.
  >
  > The accepted integration commit `f7b0d12` records T-013Q as `done`, T-013E as readiness-approved `todo`, and readiness commit `dacb871` is its ancestor. Reflog shows the exact branch was created from that HEAD, which is still unchanged. The task records the full immutable base commit, implementer `Codex`, and `in-progress`; BACKLOG and PROGRESS consistently mirror the claim and name the exact branch without claiming implementation evidence. The manifest is cleanly bounded to claim documentation, and no files were edited by the reviewer.
- Resolution: none required.
- Verdict: approved with no open P0–P3 findings.

### Implementation review Pass 1

- Reviewer task name/vendor: `/root/t013q_domain_api_rereview`, fresh Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed manifest: application/test block on task HEAD `4e428d7`, including
  latest strict JSON-boundary validation; modified `app/schemas.py` and
  `app/transfer_quotes.py`, plus untracked execution test file.
- Findings (verbatim, P0–P3):

  > P0: None.
  >
  > P1 — The frozen OpenAPI contract omits the specified `null` defaults for four optional fields.
  >
  > - `docs/tasks/T-013E-transfer-execution.md:28-32` requires `local_date`, `occurred_at`, `note`, and `counterparty` to have default `null`, and lines 35-38 require OpenAPI to freeze exact default sets.
  > - The generated `TransferQuoteExecute` schema from `app/schemas.py:173-184` has no `default` member for any of those four fields. Only `confirm_ended_period` exposes its required `false` default.
  > - `tests/test_transfer_quote_execution_v21.py:99-109` checks formats/max lengths but does not assert the nullable branches or the four missing defaults.
  > - Runtime omission/null handling is correct, and the latest strict pre-validation correctly rejects non-string JSON time values, but the published schema still does not meet the explicitly frozen contract.
  >
  > P2 — Cross-asset execution privacy is not regression-tested.
  >
  > - `docs/tasks/T-013E-transfer-execution.md:39-45` explicitly requires both identity and cross-asset execution to remain owner-only without exposing private rate state to shared or foreign users.
  > - `tests/test_transfer_quote_execution_v21.py:340-355` exercises only a same-asset quote and only a shared editor. There is no execution attempt against a cross-asset quote after rate state exists, so an ordering regression that evaluates stale/private dependencies before rejecting the caller would not be caught.
  > - Add at least one cross-asset shared or unrelated-user execution assertion for generic `404 Transfer quote not found`, quote remaining open, and zero transaction/leg/rate/Undo mutation.
  >
  > P2 — The five-minute execution boundary lacks the required neighboring-clock coverage.
  >
  > - T-013Q froze clock-controlled just-before, exact-boundary, and just-after behavior; T-013E implements `now >= expires_at`.
  > - `tests/test_transfer_quote_execution_v21.py:298-318` covers only the exact five-minute boundary. No test proves success immediately before expiry or rejection immediately after expiry while preserving the quote and mutation counts.
  > - Add clock-controlled `expires_at - ε`, `expires_at`, and `expires_at + ε` cases.
  >
  > P3: None.
  >
  > Verdict: Not approved. The implementation’s atomic transaction structure, SQLite `BEGIN IMMEDIATE`, PostgreSQL row locks plus conditional claim, rollback path, conflict precedence, persisted-amount execution, dependency comparison, permanent execution linkage, period guard reuse, and concurrent single-winner behavior otherwise appear coherent. The latest strict JSON-boundary correction was included in this review. I relied on the supplied gates (`7 focused passed`; `50 combined passed`) and did not run additional suites. No files edited.
- Resolution: preserved explicit null defaults in the published schema; added
  cross-asset non-owner privacy/mutation coverage; added one-microsecond-before,
  exact-boundary, and one-microsecond-after TTL coverage.
- Verdict: not approved; one P1 and two P2 findings fixed and submitted for
  fresh review.

### Implementation review Pass 2

- Reviewer task name/vendor: `/root/t013q_domain_api_rereview`, fresh Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed manifest: complete corrected tracked/untracked T-013E application,
  OpenAPI, and focused-test manifest, including bounded `app/main.py` wrapper.
- Findings (verbatim, P0–P3):

  > P0: None.
  >
  > P1: None.
  >
  > P2: None.
  >
  > P3: None.
  >
  > Approved.
  >
  > All prior findings are closed:
  >
  > - The execute component now exposes explicit `default: null` for `local_date`, `occurred_at`, `note`, and `counterparty`, retains their exact nullable string/date/date-time and max-length shapes, and keeps `confirm_ended_period` defaulted to `false`. The bounded `app.openapi` wrapper changes only `TransferQuoteExecute`, operates on FastAPI’s generated/cached schema, and does not alter runtime validation or unrelated components.
  > - Cross-asset privacy now covers a non-owner who has workspace-adjacent shared access but no access to the quoted accounts. Execution returns generic `404 Transfer quote not found`, leaves the quote open, and creates no transaction, legs, captured rates, or Undo mutation.
  > - TTL coverage now proves success one microsecond before expiry and rejection at and one microsecond after expiry. Boundary failures retain the open quote and are mutation-neutral; the exact-boundary case also confirms expiry wins over staleness.
  >
  > The latest strict JSON boundary validation is coherent with the frozen API: non-string dates/timestamps, coerced note/counterparty values, and non-boolean confirmation inputs are rejected. No new regression found in atomicity, concurrency, permission ordering, Decimal-only captured-amount execution, dependency staleness, rollback, period guards, Undo, or PostgreSQL locking semantics.
  >
  > I relied on the supplied focused result, `7 passed in 3.26s`, and did not run broader suites. No files edited.
- Resolution: none required; all prior findings are closed.
- Verdict: approved with no open P0–P3 findings.

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
- 2026-08-11 Codex: readiness Pass 2 corrected contributor authorization,
  aggregate-neutrality proof, dependency snapshot constraints, and conflict
  precedence. Fresh readiness re-review remains; no application code or
  database was changed.
- 2026-08-11 Codex: readiness Pass 3 demonstrated non-additive legacy divide
  valuation. Quoted commands are now owner-only and reject applicable legacy
  rates until T-012 resaves them canonical; execution stales if legacy becomes
  applicable. Fresh re-review remains; no application code or database changed.
- 2026-08-11 Codex: readiness Pass 4 approved committed split-task definitions
  at `dacb871` with no P0–P3 findings. T-013E remains blocked by accepted
  T-013Q; no application code or database was changed.
- 2026-08-11 repository owner: accepted T-013Q and promoted the already
  readiness-approved, now-unblocked T-013E from `backlog` to `todo`. Exact
  branch claim from the resulting integration commit is next.
- 2026-08-11 Codex: confirmed clean accepted integration HEAD
  `f7b0d12ec12cec58fc7801a1af56b552ec809821`, the exact task branch was absent,
  and atomically claimed `task/T-013E-transfer-execution`. Recorded the
  immutable base and implementer; atomic execution implementation is next.
- 2026-08-11 Codex: fresh read-only initial-claim review approved the exact
  three-file lifecycle manifest with no P0–P3 findings. The claim is ready for
  its first task commit; no application or database file changed.
- 2026-08-11 Codex: implemented strict atomic quote execution by reusing the
  accepted transfer/exchange, period, captured-rate, and Undo paths. Focused
  execution passed `7`; combined quote/operations/period/Undo passed `50`.
  Implementation Pass 1 found one OpenAPI P1 and two coverage P2 gaps; all
  were corrected, and fresh Pass 2 approved with no open P0–P3. Full task gate
  and final status remain.
