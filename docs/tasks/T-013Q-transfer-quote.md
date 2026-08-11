---
id: T-013Q
title: Persist exact one-amount same/cross-asset Transfer quotes
status: backlog
size: M
spec: design/MOBILE-BACKEND-GAP-AUDIT.md cross-asset Transfer
blocked-by: [T-012]
branch: task/T-013Q-transfer-quote
base-commit:
implementer:
readiness-reviewed-by:
readiness-reviewed-commit:
readiness-verdict:
---

## Goal

The public API can quote one exact source amount into a same-asset or
cross-asset destination amount using the accepted manual Asset-to-Main rates,
and persist an immutable, short-lived quote that T-013E can execute without
recalculating its amounts while rejecting changed rate dependencies as stale.

## Acceptance

- [ ] `POST /api/v1/operations/transfer/quotes` accepts exactly
      `from_account_id`, `to_account_id`, `from_amount`, and `rate_source`.
      Both account IDs are required positive JSON integers. `from_amount` is a
      required positive plain Decimal JSON string with the accepted modeled
      Numeric(38,18) and source-asset precision bounds, using exact OpenAPI
      pattern `^(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$`. `rate_source` is the required
      literal `manual`. JSON money numbers, exponent/sign syntax,
      booleans, nulls, zero/negative/non-finite values, unknown members, and
      unsupported scale/precision return input-derived `422` before a quote row
      is written. Auto/external sources remain unavailable.
- [ ] The source and destination are distinct, active accounts in one
      workspace. A same-asset quote retains the accepted transaction-create/
      edit permission on both accounts, including eligible editor/contributor
      callers. A cross-asset quote is owner-only because it consumes and returns
      information derived from owner-private workspace manual rates; shared
      editor/contributor/viewer and foreign users receive the accepted generic
      owner-private `404 Workspace not found` without learning whether a pair or
      rate exists. A failed quote writes nothing. Focused tests cover owner,
      editor, contributor, viewer, and unrelated users for both same- and
      cross-asset requests plus failure mutation neutrality.
- [ ] A same-asset quote uses exact identity conversion: destination amount
      equals source amount after the one shared asset-precision validation,
      rate is `1`, and no manual-rate row is required.
- [ ] A cross-asset quote uses only the workspace's current manual
      Asset-to-Main rows accepted by T-012. It first values the source exactly
      in Main: a Main source is unchanged, a canonical source multiplies by its
      stored `asset_to_main` value, and a tagged legacy source divides by its
      original stored `main_to_asset_legacy` value. It then solves the target
      amount with the exact inverse operation: unchanged for Main, division for
      canonical target storage, multiplication for legacy target storage. The
      calculation never substitutes T-012's 18-place public legacy reciprocal.
      No latest transaction exchange, multi-hop non-Main pair, foreign rate,
      external provider, or binary `float` participates.
- [ ] Missing manual components return deterministic `422` naming each
      unvalued Asset-to-Main pair. The failure does not create a quote or alter
      accounts, rates, ledger rows, periods, or Undo candidates.
- [ ] Intermediate multiplication/division uses the repository's explicit
      high-precision Decimal helpers and never ambient 28-digit context.
      The source amount is validated once at source precision. The unrounded
      target result from the exact canonical/legacy path is rounded once with
      `ROUND_HALF_UP` to destination precision:
      `to_amount = quantize_asset(exact_main_to_target(exact_source_to_main(from_amount)))`.
      Public/stored effective `rate = to_amount / from_amount` is independently
      quantized `ROUND_HALF_UP` to 18 places through the supported exchange-rate
      helper. A zero after quantization, more than 20 integer digits, amount/
      product/quotient overflow, or unsupported money/rate result is `422` and
      writes nothing. Tests cover canonical/canonical, canonical/legacy,
      legacy/canonical, legacy/legacy, Main on either side, repeating quotients,
      18-place underflow, maximum integer digits, and a poisoned ambient Decimal
      context.
- [ ] A quote is accepted only when the outgoing and incoming values, each
      independently converted by the selected manual rates and rounded at the
      Main asset presentation boundary, are equal. An amount that cannot be
      represented in the destination precision without changing displayed
      Total capital returns deterministic `422` and writes nothing.
- [ ] The `201` response contains exactly `id`, `workspace_id`,
      `created_by_user_id`, `from_account`, `to_account`, `from_amount`,
      `to_amount`, `rate`, `rate_source`, `created_at`, and `expires_at`; all are
      required and no owner-private Main/rate-row metadata is exposed.
      `id`, `workspace_id`, and `created_by_user_id` are positive JSON integers.
      Each account is exactly `{"id": <positive integer>, "name": <string>,
      "asset": <full AssetOut>}` with all three keys required and no balance,
      workspace, owner, access-role, or valuation fields. Amount/rate values are
      normalized plain Decimal JSON strings. Timestamps are ISO-8601 strings
      with OpenAPI `date-time` format and represent naive UTC consistently with
      existing persisted timestamps. OpenAPI freezes exact component property,
      required, type, additional-property, literal, pattern, and bound sets.
- [ ] Exact response JSON is, modulo IDs/timestamps:

      ```json
      {
        "id": 1,
        "workspace_id": 1,
        "created_by_user_id": 1,
        "from_account": {"id": 10, "name": "Cash VND", "asset": {"id": 3, "code": "VND", "name": "Vietnamese dong", "kind": "fiat", "decimals": 0, "is_active": true}},
        "to_account": {"id": 11, "name": "Card USD", "asset": {"id": 1, "code": "USD", "name": "US dollar", "kind": "fiat", "decimals": 2, "is_active": true}},
        "from_amount": "1000000",
        "to_amount": "38",
        "rate": "0.000038",
        "rate_source": "manual",
        "created_at": "2026-08-11T12:00:00",
        "expires_at": "2026-08-11T12:05:00"
      }
      ```
- [ ] Quotes expire exactly five minutes after server creation time, use UTC
      timestamps, and are immutable. One captured server clock sets
      `created_at`; `expires_at = created_at + 5 minutes`; T-013E treats
      `now >= expires_at` as expired. Exact-boundary, just-before, and
      just-after cases are clock-controlled. Expired rows are retained for
      audit and lazy rejection; no queue, worker, scheduled cleanup, Redis, or
      external dependency is added.
- [ ] A new additive Alembic revision after
      `0003_manual_rate_direction` creates a `transfer_quote` table with exact
      Decimal storage for both amounts and the effective rate. Required columns
      are positive integer `id`; `workspace_id`; `created_by_user_id`;
      `from_account_id`/`to_account_id`; `from_asset_id`/`to_asset_id`;
      quoted `main_asset_id`; Numeric(38,18) `from_amount`, `to_amount`, and
      `rate`; `rate_source`; nullable source/target manual-rate dependency ID,
      stored value, direction, and updated-at snapshot fields; `status`;
      `created_at`; `expires_at`; nullable `executed_at`; and nullable unique
      `executed_transaction_id`.
- [ ] Status is exactly `open | executed`. Named checks enforce positive
      amounts/rate, `rate_source = 'manual'`, `expires_at > created_at`, and
      `(status = 'open' AND executed_at IS NULL AND executed_transaction_id IS NULL)
      OR (status = 'executed' AND executed_at IS NOT NULL AND executed_transaction_id IS NOT NULL)`.
      Workspace deletion cascades quotes; creator, account, asset, Main, and
      executed-transaction FKs use `RESTRICT`; the executed link is unique.
      Manual-rate dependency IDs intentionally are immutable scalar snapshots,
      not FKs, so rate deletion can make a quote stale without deleting,
      mutating, or blocking the quote. One composite index covers
      `(workspace_id, created_by_user_id, status, expires_at)`.
- [ ] Quote persistence snapshots every execution-relevant value, including
      account/asset/Main identities, both exact amounts, and the IDs, exact
      stored values, directions, and update timestamps of every manual-rate row
      used. Later rate update/delete cannot mutate the quote; T-013E compares
      current dependencies to this snapshot and rejects a changed/missing row
      as stale without consuming it. T-013E may not recalculate destination
      amount.
- [ ] Migration verification covers clean upgrade from `0003`, SQLite
      constraints/indexes/FKs, PostgreSQL-compatible Numeric/check/index DDL,
      actual upgrade/downgrade operation compilation, and one Alembic head.
      Downgrade to `0003` succeeds only with an empty quote table; any row makes
      downgrade abort before DDL/version mutation so audit evidence is not
      silently discarded. The upgrade is additive and does not read, rewrite,
      or require `finapp.db` or legacy v1 rows.
- [ ] ADR-0009 records persisted five-minute single-use quotes, manual
      Asset-to-Main cross-rate derivation (including exact legacy divide
      semantics), destination quantization, displayed Total-capital neutrality,
      owner-only cross-asset privacy, stale-on-rate/Main-change execution,
      immutable rate dependency snapshots, empty-only downgrade, and the
      decision not to add background cleanup; `docs/DECISIONS.md` indexes it.
- [ ] Focused quote/domain/OpenAPI/permission/migration tests, full pytest,
      Node syntax, and diff/status checks pass using isolated fixtures or an
      explicit scratch `DATABASE_URL` only.

## Touches

- `app/models.py`
- `app/schemas.py`
- `app/ledger.py` only for a shared exact manual-rate/cross-rate helper
- `app/transfer_quotes.py` and router registration
- `app/main.py` for router registration
- `alembic/versions/0004_transfer_quotes.py`
- `tests/test_transfer_quotes_v21.py`
- `tests/test_migrations_v2.py`
- `docs/decisions/ADR-0009-bound-transfer-quotes.md`
- `docs/DECISIONS.md`
- `docs/tasks/T-013Q-transfer-quote.md`
- `docs/BACKLOG.md` and `docs/PROGRESS.md` for task lifecycle only

## Out of scope

- Executing, consuming, refreshing, cancelling, or listing a quote; T-013E
  owns execution and replay/expiry error behavior.
- Changing the existing same-asset `/operations/transfer` or explicit
  two-amount `/operations/exchange` routes, fee behavior, captured transaction
  exchange rates, Undo, transaction feed/detail mapping, or desktop UI.
- Automatic/external rates, network calls, multi-hop rate graphs, quote cleanup
  jobs, account-period changes, mobile UI, Phase 15, or `finapp.db` mutation.

## Verification

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_transfer_quotes_v21.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_valuation_rate_direction_v21.py tests/test_valuation_v2.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_migrations_v2.py -q
.\.venv\Scripts\python.exe -m pytest -q
node --check app/static/app.js
git diff --check
git status --short
```

All database-backed commands use isolated fixtures or an explicit absolute
scratch `DATABASE_URL`. They never fall back to, open, replace, or delete
`finapp.db`.

## Readiness review

Append-only readiness passes against the accepted transfer audit, T-012 and
ADR-0008 rate direction, shipped ledger/permissions/period/Undo invariants,
AGENTS, BACKLOG, BUILD_PLAN, and REVIEW_PROTOCOL.

### Pass 1

- Reviewer task name/vendor: `/root/t013_readiness_review`, Codex same-vendor
  fallback; cross-vendor reviewer unavailable in this session.
- Reviewed task-file commit: `cddefcf` (both T-013Q and T-013E plus the backlog
  split).
- Findings (verbatim, P0–P3):

  > P0: None.
  >
  > P1 — Shared-user rate privacy is unresolved and internally contradictory.
  >
  > - T-013Q allows any caller with the existing edit permission on both accounts (`docs/tasks/T-013Q-transfer-quote.md:32-36`), which includes shared editors under `app/access.py:12-18`.
  > - The same request consumes the accounts’ workspace-private manual rates (`T-013Q:40-46`) and returns the effective rate and Main asset (`T-013Q:61-67`).
  > - This conflicts with `docs/specs/FinnApp-v2.md:53-56,360-362`, which prohibits a shared-account-only user from receiving or inferring the owner’s rate/workspace-private data. Existing rate endpoints are owner-only (`app/valuation_rates.py:55-80,120-124`).
  > - Freeze one policy before implementation: for example, owner-only cross-asset quoting, or another explicitly documented rate ownership/context model that does not leak the account owner’s rates. Add owner/editor/contributor/viewer/unrelated-user tests for same- and cross-asset quotes and failure mutation neutrality.
  >
  > P1 — Immutable execution after a rate change cannot also guarantee live Account-summary neutrality.
  >
  > - T-013E says a manual-rate update/delete does not stale a quote (`docs/tasks/T-013E-transfer-execution.md:30-34`) and execution must retain the bound amounts (`:47-51`).
  > - It simultaneously requires live Account summary Total capital to be identical before and after execution (`:65-69`).
  > - Current valuation gives the current manual rate precedence (`docs/specs/FinnApp-v2.md:122-136`). Once that rate changes, fixed legs neutral under the old quote rate are generally not neutral under the new live rate. Deletion can additionally make the newly captured exchange rate become valuation fallback and revalue pre-existing holdings.
  > - Choose a satisfiable invariant: either stale the quote when rate state changes, or define neutrality using the quote-time captured valuation proof while allowing live Total capital to move after a rate change. Tests must separately cover unchanged, updated, and deleted-rate execution.
  >
  > P1 — Public request/response and OpenAPI contracts are not frozen.
  >
  > - T-013Q explicitly leaves `from_account`, `to_account`, and `main_asset` shapes “selected during readiness” (`docs/tasks/T-013Q-transfer-quote.md:61-67`). This readiness pass therefore has no exact contract to approve.
  > - It also omits exact integer constraints for account/quote IDs, timestamp representation, nested required/property sets, and a complete JSON example.
  > - T-013E lists optional field names (`docs/tasks/T-013E-transfer-execution.md:25-29`) but does not freeze their JSON/OpenAPI types, null behavior, defaults, maximum lengths, whether an empty or omitted body is valid, path-ID type, success status, or exact required/property sets. Existing `TransactionCommon` is permissive and has no `extra="forbid"` (`app/schemas.py:303-309`).
  > - Select explicit compact or existing public shapes and add exact component/OpenAPI assertions comparable to `tests/test_valuation_rate_direction_v21.py:27-69`.
  >
  > P1 — Legacy-rate arithmetic and effective-rate rounding are financially ambiguous.
  >
  > - T-013Q describes `S → D` as a quotient of Asset-to-Main rates (`docs/tasks/T-013Q-transfer-quote.md:40-46`) and calls the stored/public rate an “18-place exact quotient” (`:50-55`).
  > - A quotient need not terminate; Numeric(38,18) requires a stated quantization rule. The task also never explicitly states `to_amount = ROUND_HALF_UP(from_amount × cross_rate, destination precision)` or overflow/underflow behavior.
  > - More importantly, legacy public Asset-to-Main output is an 18-place quantized reciprocal (`app/ledger.py:139-145`), while ledger valuation retains exact legacy divide semantics (`app/ledger.py:149-157`). Using the public reciprocal in quote arithmetic can disagree with Account-summary valuation and ADR-0008’s preserved legacy meaning.
  > - Freeze the exact canonical/legacy calculation path, destination formula, effective-rate `ROUND_HALF_UP` rule, normalization, and boundary failures. Cover canonical/legacy combinations, repeating quotients, 18-place underflow, maximum integer digits, and ambient-context regression.
  >
  > P1 — The persisted state machine is insufficiently specified for the claimed exactly-once contract.
  >
  > - T-013Q only says “single-use status” and “executed transaction linkage” (`docs/tasks/T-013Q-transfer-quote.md:72-83`); it does not enumerate statuses, nullability, FK `ondelete` behavior, or consistency constraints between status and executed transaction.
  > - T-013E assumes exact `open`/`executed` semantics and distinct concurrency outcomes (`docs/tasks/T-013E-transfer-execution.md:35-40`).
  > - Specify all columns and modeled types, allowed statuses, `open ⇔ executed_transaction_id IS NULL`, `executed ⇔ link IS NOT NULL`, positive amount/rate checks, `expires_at > created_at`, unique link behavior, FK deletion policies, and whether `executed_at` is stored. Add exercised SQLite CHECK/FK/unique tests and PostgreSQL migration-operation compilation.
  >
  > P2 — Main-asset staleness and expiry boundaries are ambiguous.
  >
  > - “A workspace Main-asset change makes the quote stale” (`T-013E:32-34`) cannot be detected from only the persisted Main asset identity if Main changes away and back before execution. Define either “current Main ID differs from quoted Main ID” or add a revision/version snapshot.
  > - “Exactly five minutes” and “not expired” (`T-013Q:68-71`; `T-013E:35-38`) do not define the equality boundary. Freeze one captured server clock, `expires_at = created_at + 5 minutes`, and expiry at `now >= expires_at`; test just-before, exact-boundary, and just-after behavior.
  >
  > P2 — Post-execution lifecycle must explicitly preserve single use.
  >
  > - T-013E requires normal soft Delete/Undo behavior (`docs/tasks/T-013E-transfer-execution.md:61-64`) but does not state that Undo, soft deletion, or later correction never reopens, unlinks, or makes the quote executable again.
  > - Add acceptance and tests that the immutable quote remains executed and linked after correction or soft void, while captured-rate eligibility follows the transaction’s ordinary posted/voided rules.
  >
  > P2 — `Touches` omits the concrete router-registration file.
  >
  > - T-013Q requires a new module “and router registration” (`docs/tasks/T-013Q-transfer-quote.md:100-102`), but `app/main.py`—where routers are registered (`app/main.py:9-20,31-42`)—is absent from `Touches`.
  > - Name `app/main.py`, or explicitly require registration through an already-listed module.
  >
  > P3: None.
- Resolution: cross-asset quote/execution is owner-only while same-asset keeps
  accepted shared write roles; Main/rate dependency changes now stale a quote;
  compact public JSON/OpenAPI shapes are exact; legacy arithmetic uses stored
  divide semantics; amount/rate rounding and boundaries are explicit; all
  columns/status checks/FKs/index/downgrade rules are frozen; clock/Main
  boundaries and permanent post-execution single use are explicit; `app/main.py`
  is in scope. Fresh readiness re-review is required.
- Reviewer checks: direct committed docs/spec/code/test inspection; supplied
  `git diff --check` passed; no application tests run for documentation-only
  readiness.
- Verdict: not ready; corrected and submitted for fresh re-review.

## Review

Append-only implementation review passes. A different read-only agent returns
the review; the implementer records it verbatim following
[`../REVIEW_PROTOCOL-v2.md`](../REVIEW_PROTOCOL-v2.md).

## Session log

- 2026-08-11 Codex: split the ordered L-sized T-013 into bounded quote and
  execution tasks and drafted the exact quote contract. Readiness review,
  owner promotion, branch claim, implementation, and implementation review
  remain; no application code or database was changed.
- 2026-08-11 Codex: readiness Pass 1 returned five P1 and three P2 contract
  gaps. Owner-only cross-asset privacy, stale dependency rules, exact public
  shapes/arithmetic/state/FKs/downgrade, expiry boundaries, and post-execution
  single use are now explicit. Fresh readiness re-review remains; no application
  code or database was changed.
