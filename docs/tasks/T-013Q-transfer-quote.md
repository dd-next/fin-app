---
id: T-013Q
title: Persist exact one-amount same/cross-asset Transfer quotes
status: in-progress
size: M
spec: design/MOBILE-BACKEND-GAP-AUDIT.md cross-asset Transfer
blocked-by: [T-012]
branch: task/T-013Q-transfer-quote
base-commit: fc1ce24088941667e1e473adce8fe49385ba63a1
implementer: Codex
readiness-reviewed-by: /root/t013_readiness_confirmation (Codex same-vendor fallback)
readiness-reviewed-commit: dacb871
readiness-verdict: ready
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
      workspace, and the quote API is owner-only for both identity and
      cross-asset requests. This prevents the new quote surface from leaking
      owner-private workspace/Main/rate state; existing direct same-asset
      `/operations/transfer` keeps shipped editor behavior. Shared editor,
      contributor, viewer, and foreign users receive the accepted generic
      owner-private `404 Workspace not found` without learning whether a pair,
      rate, or legacy row exists. A failed quote writes nothing. Focused tests
      cover owner/editor/contributor/viewer/unrelated users for both paths plus
      failure mutation neutrality.
- [ ] A same-asset quote uses exact identity conversion: destination amount
      equals source amount after the one shared asset-precision validation,
      rate is `1`, and no rate is required. Main, canonical manual multiplication,
      latest-exchange multiplication fallback, and unvalued exclusion are
      additive over the unchanged combined asset balance. If an applicable
      owner-workspace manual row is tagged legacy, quote creation returns the
      same explicit resave `422` as cross-asset quoting; finite-precision legacy
      division is not accepted even for identity quotes.
- [ ] A cross-asset quote uses only the workspace's current manual
      canonical `asset_to_main` rows accepted by T-012. A Main source is valued
      unchanged; every non-Main source multiplies by its exact stored canonical
      rate. A Main target receives that exact value; every non-Main target is
      solved by exact division by its stored canonical rate. Tagged
      `main_to_asset_legacy` rows remain valid for shipped account valuation but
      are deliberately ineligible for new quotes because finite-precision
      per-account division is not additive. No public reciprocal, latest
      transaction exchange, multi-hop pair, foreign rate, external provider,
      or binary `float` participates.
- [ ] Missing manual components return deterministic `422` naming each
      unvalued Asset-to-Main pair. The failure does not create a quote or alter
      accounts, rates, ledger rows, periods, or Undo candidates.
- [ ] A required tagged legacy row returns deterministic `422 Manual valuation
      rate must be resaved before transfer quoting: <Asset> → <Main>` and writes
      nothing. The existing owner-only T-012 PUT of the displayed Asset-to-Main
      Decimal converts only that row to canonical storage; quoting never
      silently inverts, rewrites, or upgrades a legacy row.
- [ ] Intermediate multiplication/division uses the repository's explicit
      high-precision Decimal helpers and never ambient 28-digit context.
      The source amount is validated once at source precision. The unrounded
      target result from the exact canonical path is rounded once with
      `ROUND_HALF_UP` to destination precision:
      `to_amount = quantize_asset(exact_main_to_target(exact_source_to_main(from_amount)))`.
      Public/stored effective `rate = to_amount / from_amount` is independently
      quantized `ROUND_HALF_UP` to 18 places through the supported exchange-rate
      helper. A zero after quantization, more than 20 integer digits, amount/
      product/quotient overflow, or unsupported money/rate result is `422` and
      writes nothing. Tests cover canonical/canonical, Main on either side,
      repeating quotients, 18-place underflow, maximum integer digits, explicit
      legacy rejection/resave success, and a poisoned ambient Decimal context.
- [ ] A quote is accepted only when exact outgoing Main value equals exact
      incoming Main value before any Main/presentation rounding. This remains
      neutral for every unrelated balance because Account summary sums exact
      valued balances before one final Main quantization. An amount that
      destination precision cannot represent with exact Main equality returns
      deterministic `422 Transfer amount cannot preserve Total capital` and
      writes nothing. Tests include adversarial unrelated balances where
      independently rounded legs look equal but aggregate rounding would change
      Total capital.
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
- [ ] Each dependency tuple is exactly nullable positive integer rate-row ID,
      nullable Numeric(38,18) stored value, nullable `String(24)` direction, and
      nullable UTC `DateTime` updated-at. Named checks enforce all-or-none tuple
      nullability, positive stored value, and direction exactly
      `asset_to_main`. Identity quotes require both
      dependency tuples absent, equal asset IDs, equal amounts, and rate `1`.
      Cross-asset quotes require a tuple absent exactly for a side whose asset
      equals quoted Main and a complete valid tuple for every non-Main side.
      Named checks also require distinct account IDs. SQLite tests exercise
      every invalid partial/direction/value/identity/cross combination and the
      actual PostgreSQL migration operations compile with the same constraints.
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
      Asset-to-Main cross-rate derivation, explicit legacy-row rejection with
      owner resave through T-012, destination quantization, exact
      pre-rounding Main-value equality under additive canonical multiplication
      for aggregate Total-capital neutrality,
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

### Pass 2

- Reviewer task name/vendor: `/root/t013_readiness_rereview`, fresh Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed task-file range: `cddefcf..508055f` (both split tasks).
- Findings (verbatim, P0–P3):

  > P0: None.
  >
  > P1 — The Total-capital neutrality proof is still insufficient.
  >
  > - T-013Q accepts when the two leg valuations are independently rounded to Main precision and compare equal (`docs/tasks/T-013Q-transfer-quote.md:75-79`).
  > - Account summary instead sums exact valued balances first and rounds only the aggregate (`app/accounts.py:159-181`).
  > - Therefore equal independently rounded legs do not guarantee unchanged Total capital. Example with 2-decimal Main: exact outgoing `0.014` and incoming `0.01` both display `0.01`, so the quote passes; with an unrelated exact valued balance of `0.001`, aggregate capital changes from `0.015 → 0.011`, displayed `0.02 → 0.01`.
  > - This contradicts T-013E’s unconditional unchanged-summary requirement (`docs/tasks/T-013E-transfer-execution.md:97-103`) and Phase 14’s Total-capital invariant (`docs/BUILD_PLAN-v2.md:213-216`). Require exact Main-value equality, or another proof valid for arbitrary existing balances, with an adversarial aggregate-rounding regression.
  >
  > P1 — Same-asset contributor authorization contradicts shipped permissions.
  >
  > - T-013Q promises eligible editor/contributor same-asset quoting (`docs/tasks/T-013Q-transfer-quote.md:35-44`), and T-013E says execution retains editor/contributor behavior (`docs/tasks/T-013E-transfer-execution.md:39-45`).
  > - Shipped `edit` permission is owner/editor only (`app/access.py:11-18`), and transfer checks `edit` on both accounts (`app/transactions.py:208-213`).
  > - Existing regression coverage explicitly accepts editor/editor and rejects a transfer involving a contributor (`tests/test_operations_v2.py:181-203`).
  > - Freeze contributor as denied for same-asset quote/execute, or explicitly authorize and scope a permission-model change. “Preserve existing routes” currently favors denial.
  >
  > P1 — The quote migration contract still does not fully specify the dependency snapshot state.
  >
  > - T-013Q names nullable dependency ID/value/direction/timestamp fields (`docs/tasks/T-013Q-transfer-quote.md:116-125`) but does not freeze their modeled types or enforce all-or-none tuples, permitted direction values, positive stored values, or when source/target tuples must be absent/present.
  > - The listed checks only cover effective amounts/rate, source literal, expiry, and open/executed linkage (`docs/tasks/T-013Q-transfer-quote.md:126-135`).
  > - Because execution treats these snapshots as the immutable stale-check authority (`docs/tasks/T-013Q-transfer-quote.md:136-142`), partial or malformed persisted tuples leave execution behavior undefined. Specify exact types and named dependency-integrity checks, then exercise them on SQLite and PostgreSQL DDL compilation.
  >
  > P2 — Overlapping execute conflict precedence is not frozen.
  >
  > - T-013E gives exact messages for executed, expired, and stale states (`docs/tasks/T-013E-transfer-execution.md:52-58`) but does not state which wins when states overlap naturally: an executed quote later expires or becomes stale, or an open quote is both expired and stale.
  > - Freeze and test a deterministic validation order, including exact-boundary expiry plus executed/expired and expired/stale combinations.
  >
  > P3: None.
- Resolution: quote acceptance now requires exact pre-rounding Main-value
  equality and an adversarial aggregate regression; contributor is denied under
  shipped `edit`; dependency tuple types/presence/direction/value checks and
  dialect tests are exact; execute conflict precedence is permissions, then
  executed, then expiry, then staleness. Fresh re-review is required.
- Reviewer checks: direct committed docs/spec/code/test inspection;
  `git diff --check cddefcf 508055f` passed; no application tests run for
  documentation-only readiness.
- Verdict: not ready; corrected and submitted for fresh re-review.

### Pass 3

- Reviewer task name/vendor: `/root/t013_readiness_final`, fresh Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed task-file range: `508055f..7c7b511` (both split tasks).
- Findings (verbatim, P0–P3):

  > P0: None.
  >
  > P1 — Exact leg-value equality still does not guarantee aggregate Total-capital neutrality for legacy divide rates.
  >
  > - T-013Q accepts a quote when outgoing and incoming Main values compare equal before presentation rounding (`docs/tasks/T-013Q-transfer-quote.md:75`), and T-013E treats that as sufficient for arbitrary account balances (`docs/tasks/T-013E-transfer-execution.md:102`).
  > - Canonical multiplication is linear, but legacy valuation uses a 100-significant-digit rounded division (`app/ledger.py:88-92`, `app/ledger.py:149-157`). Account summary values each complete account balance separately and then sums those results (`app/accounts.py:144-163`). Rounded division is not additive.
  > - Counterexample using the shipped helpers and valid modeled values:
  >   - Main has two decimals.
  >   - Two different legacy assets both store `main_to_asset_legacy = 3`.
  >   - Transfer `2 → 2`; both quoted leg values are the identical helper result `2 / 3`, so the new equality check passes.
  >   - Participating balances change from `-20, -9` to `-22, -7`.
  >   - An unrelated legacy account has balance `5797` and stored rate `600`.
  >   - Before: `-0.005000…000`; after: `-0.004999…999`, a `1E-99` difference caused solely by per-account legacy division.
  >   - `ROUND_HALF_UP` to Main precision therefore changes Total capital from `-0.01` to `-0.00`.
  > - Thus the requested adversarial regression would expose a failure even though the quote’s leg values compare equal. The contract must additionally bound legacy behavior—for example by making aggregate legacy valuation genuinely exact, restricting accepted legacy divisors to exact terminating arithmetic, or specifying a balance-dependent neutrality proof and the snapshots/staleness needed to preserve it through execution.
  >
  > P2: None.
  >
  > P3: None.
- Resolution: every quoted command is owner-only; any applicable tagged legacy
  manual row makes quote creation ineligible and requires explicit owner resave
  through T-012. Execution rejects a newly applicable legacy row as stale.
  Cross-asset calculations and the exact equality proof use canonical additive
  multiplication only; same-asset Main/canonical/latest-rate/unvalued paths are
  also additive over the unchanged combined asset balance. Fresh re-review is
  required.
- Reviewer checks: direct committed docs/spec/code/test inspection;
  `git diff --check 508055f..7c7b511` passed; no application tests run for
  documentation-only readiness.
- Verdict: not ready; corrected and submitted for fresh re-review.

### Pass 4

- Reviewer task name/vendor: `/root/t013_readiness_confirmation`, fresh Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed task-file range: final corrective range `7c7b511..dacb871` plus the
  cumulative T-013Q/T-013E readiness history.
- Findings (verbatim, P0–P3):

  > P0: None.
  >
  > P1: None.
  >
  > P2: None.
  >
  > P3: None.
  >
  > The sole Pass 3 P1 is closed:
  >
  > - Quote creation and execution are owner-only for both same-asset and cross-asset paths. Shared editor/contributor/viewer and unrelated-user privacy behavior is explicitly covered, while the existing direct same-asset transfer retains shipped editor behavior.
  > - Same-asset quote creation rejects an applicable `main_to_asset_legacy` row with explicit resave-required `422`; execution treats a newly applicable legacy row as stale.
  > - Same-asset neutrality is sufficient: Main identity, canonical multiplication, workspace-wide latest direct-exchange multiplication, and unvalued exclusion each apply uniformly to both accounts of the same asset. Since the quoted amounts are equal, their combined asset balance is unchanged. Legacy division—the only non-additive path—is excluded.
  > - Cross-asset quotes accept only canonical `asset_to_main` dependencies. For source balance `Bₛ`, target balance `Bₜ`, amounts `a`, `b`, canonical rates `rₛ`, `rₜ`, the summary changes by `−a·rₛ + b·rₜ`. T-013Q requires exact `a·rₛ = b·rₜ` after destination quantization and before Main/presentation rounding, so the delta is exactly zero. Every unrelated valued, legacy, fallback, or unvalued balance remains unchanged; therefore the final aggregate Main quantization is unchanged.
  > - The prior legacy counterexample can no longer enter either path: legacy rows are rejected/resave-required at quote and stale at execute.
  >
  > No earlier P1/P2 regressed:
  >
  > - Canonical-only dependency tuples have exact all-or-none presence rules, positive values, `asset_to_main` direction, identity/cross-asset consistency, and SQLite/PostgreSQL verification requirements.
  > - Quote and execute request/response/OpenAPI contracts are frozen, including strict Decimal strings, ID bounds, nested account shape, timestamps, body defaults, status codes, and exact errors.
  > - State, FK/delete behavior, unique execution linkage, five-minute boundary, immutable dependency snapshots, stale behavior, concurrency guard, permanent single-use lifecycle, and empty-only downgrade are coherent.
  > - Conflict precedence remains permissions/privacy → executed → expired → stale.
  > - Main-ID behavior, changed/deleted dependency behavior, correction/Delete/Undo behavior, router registration, Touches, Out-of-scope, and Verification remain explicit and bounded.
- Resolution: no change required; every prior readiness finding is closed.
- Reviewer checks: `git diff --check 7c7b511 dacb871` passed; worktree clean;
  no application tests run for documentation-only readiness.
- Verdict: ready for repository-owner readiness recording and backlog → todo
  promotion.

### Progress handoff review

- Reviewer task name/vendor: `/root/t013_progress_review`, Codex same-vendor
  fallback; cross-vendor reviewer unavailable in this session.
- Reviewed manifest: HEAD `2d802b7` plus the uncommitted `docs/PROGRESS.md`
  readiness-state diff; no application or database files.
- Findings (verbatim, P0–P3):

  > P0: None.
  > P1: None.
  > P2: None.
  > P3: None.
  >
  > Approved.
  >
  > `docs/PROGRESS.md` matches `BACKLOG.md` and both T-013 task files at `2d802b7`. It makes no T-013 implementation, test, migration, schema, or database-change claims. Links resolve, statuses and blockers are consistent, and `git diff --check` passes. No files edited.
- Resolution: none required.
- Verdict: approved.

### Blocked handoff review

- Reviewer task name/vendor: `/root/t013_blocked_handoff_review`, Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed manifest: HEAD `f026d02` plus the sole uncommitted T-013Q session-log
  block; no application or database files.
- Findings (verbatim, P0–P3):

  > P0: None.
  > P1: None.
  > P2: None.
  > P3: None.
  >
  > Approved.
  >
  > The handoff block accurately reflects HEAD `f026d02`, T-013Q’s `backlog`/unclaimed state, readiness approval, absent task branch, required owner promotion, and the lack of application, schema, migration, test, or database changes. It does not misstate the Phase 14 release status. `git diff --check` passed; no files were edited.
- Resolution: none required.
- Verdict: approved.

### Blocker record review Pass 1

- Reviewer task name/vendor: `/root/t013_blocker_record_review`, Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed manifest: integration HEAD `092b168` plus the uncommitted task/
  PROGRESS blocker record; no application or database files.
- Findings (verbatim, P0–P3):

  > P0: None.
  >
  > P1: None.
  >
  > P2 — Unblock sequence is incomplete.
  >
  > - `T-013Q-transfer-quote.md` correctly requires owner promotion and branching from the promoted integration HEAD, but omits two mandatory `AGENTS.md` safeguards:
  >   - stop if `task/T-013Q-transfer-quote` already exists when claiming;
  >   - in the first task commit, set both task and BACKLOG statuses to `in-progress` and record the implementer, alongside `base-commit`.
  > - Add these steps so the handoff cannot bypass the atomic-claim protocol.
  >
  > P3: None.
- Resolution: the unblock sequence now requires the branch-absence stop and
  the first-commit base/implementer/task+BACKLOG `in-progress` transition.
- Reviewer checks: direct AGENTS/task/BACKLOG/PROGRESS/branch/worktree review;
  `git diff --check` passed; no files edited by reviewer.
- Verdict: not approved; corrected and submitted for fresh re-review.

### Blocker record review Pass 2

- Reviewer task name/vendor: `/root/t013_blocker_record_rereview`, fresh Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed manifest: integration HEAD `092b168` plus corrected uncommitted
  task/PROGRESS blocker record.
- Findings (verbatim, P0–P3):

  > P0: None.
  > P1: None.
  > P2: None.
  > P3: None.
  >
  > Approved.
- Resolution: none required; Pass 1 P2 is closed.
- Reviewer checks: task/BACKLOG/readiness/local+remote branch refs, three-turn
  history, exact AGENTS claim sequence, PROGRESS, session log, and
  `git diff --check`; no files edited by reviewer.
- Verdict: approved.

### Promotion review Pass 1

- Reviewer task name/vendor: `/root/t013_promotion_review`, Codex same-vendor
  fallback; cross-vendor reviewer unavailable in this session.
- Reviewed manifest: integration HEAD `424c441` plus uncommitted owner-authorized
  task/BACKLOG/PROGRESS `backlog` → `todo` promotion.
- Findings (verbatim, P0–P3):

  > P0: None.
  > P1: None.
  > P2: None.
  > P3 — `docs/PROGRESS.md` has duplicated/incorrect wording: “T-013Q is promoted T-013Q to `todo` for exact branch claim”. Replace with “The owner promoted T-013Q…” or equivalent.
- Resolution: removed the duplicated subject and made the owner transition
  explicit; no lifecycle state changed beyond the reviewed promotion.
- Reviewer checks: readiness/dependency/task/BACKLOG/PROGRESS/branch absence,
  exact next claim sequence, scoped diff, and `git diff --check`.
- Verdict: not approved; P3 corrected and submitted for fresh re-review.

### Promotion review Pass 2

- Reviewer task name/vendor: `/root/t013_promotion_rereview`, fresh Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed manifest: integration HEAD `424c441` plus corrected complete
  task/BACKLOG/PROGRESS promotion manifest.
- Findings (verbatim, P0–P3):

  > P0: None.
  > P1: None.
  > P2: None.
  > P3: None.
  >
  > Approved.
- Resolution: none required; Pass 1 P3 is closed.
- Reviewer checks: exact lifecycle states, readiness/dependency ancestry,
  local/remote branch absence, empty pre-claim base/implementer, scoped manifest,
  exact next claim sequence, and `git diff --check`.
- Verdict: approved.

## Resolved blocker

- Cause: repository-owner promotion of T-013Q from `backlog` to `todo` has not
  occurred. AGENTS requires that committed owner transition before the exact
  task branch can be created; an implementer cannot perform or bypass it.
- Repeated audit: the same gate was confirmed on three consecutive goal turns.
  Current accepted integration HEAD is `092b168`; task/backlog both remain
  `backlog`; readiness verdict is `ready` at reviewed commit `dacb871`; T-012 is
  accepted; `task/T-013Q-transfer-quote` does not exist; the worktree was clean.
- Attempts: split the L task; completed four independent readiness passes and
  a clean final confirmation; recorded readiness and PROGRESS handoffs; twice
  rechecked external task/branch state; requested explicit owner promotion.
  No safe implementation, later-task, migration, or branch action is permitted
  while the gate remains unchanged.
- Resolution required: repository owner commits the T-013Q task front matter
  and matching BACKLOG row as `todo`. A later resumed implementer must then
  stop if exact branch `task/T-013Q-transfer-quote` already exists; otherwise
  create it atomically from that promoted integration HEAD. In the first task
  commit, record that HEAD as `base-commit`, record the implementer, and set
  both task front matter and the matching BACKLOG row to `in-progress`.
- Resolved 2026-08-11: repository owner explicitly instructed Codex to continue
  implementation without waiting for further approvals. This commit performs
  the reviewed task/BACKLOG `backlog` → `todo` promotion; exact branch claim is
  next and remains subject to the recorded branch-absence/base safeguards.

## Review

Append-only implementation review passes. A different read-only agent returns
the review; the implementer records it verbatim following
[`../REVIEW_PROTOCOL-v2.md`](../REVIEW_PROTOCOL-v2.md).

### Initial claim review

- Reviewer task name/vendor: `/root/t013q_claim_review`, fresh Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed manifest: branch `task/T-013Q-transfer-quote`, HEAD
  `fc1ce24088941667e1e473adce8fe49385ba63a1`, and the complete tracked
  claim diff in `docs/BACKLOG.md`, `docs/PROGRESS.md`, and this task file;
  no untracked files.
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
  > The claim satisfies the AGENTS initial-claim protocol. Integration commit
  > `fc1ce24088941667e1e473adce8fe49385ba63a1` is the reviewed
  > readiness-approved owner promotion with T-013Q at `todo`; `dacb871` is
  > its ancestor, and T-012 is accepted as `done`. The reflog shows the exact
  > branch was created from `fc1ce24`, and current HEAD remains that base. The
  > task records the full base commit and `Codex` implementer, while both task
  > and matching BACKLOG row are consistently `in-progress`.
  > `docs/PROGRESS.md` names the exact branch, current claimed work, and no
  > blocker without claiming implementation or new test evidence. The
  > append-only session log accurately records the branch claim and next work.
  > No files were edited by the reviewer.
- Resolution: none required.
- Reviewer checks: lifecycle/dependency/ancestry, branch reflog, task/BACKLOG/
  PROGRESS consistency, complete manifest, and `git diff --check` (passed).
- Verdict: approved for the first T-013Q task commit.

### Schema/migration review Pass 1

- Reviewer task name/vendor: `/root/t013q_schema_review`, fresh Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed manifest: task branch HEAD `7263c06` plus modified
  `app/models.py`, modified `tests/test_migrations_v2.py`, and untracked
  `alembic/versions/0004_transfer_quotes.py`.
- Findings (verbatim, P0–P3):

  > P0: None.
  >
  > P1 — SQLite `CAST(... AS NUMERIC)` breaks the required exact Decimal constraints.
  >
  > - Affected: `app/models.py:458-461,508-512` and `alembic/versions/0004_transfer_quotes.py:115-118,165-169`.
  > - Fresh SQLite verification accepted:
  >   - unequal 38-digit identity amounts differing in the last decimal;
  >   - rate `1.0000000000000000001` as equal to `1`;
  >   - malformed values such as `10abc` and `1xyz`;
  >   - exponent-form values such as `1e2`.
  > - This violates the task’s exact identity/value checks and creates SQLite/PostgreSQL behavior drift.
  > - Existing tests omit precision-collision and malformed/exponent cases.
  >
  > P2: None beyond the missing coverage tied to P1.
  > P3: None.
  >
  > No separate findings for dependency tuple null semantics, FK/delete declarations, uniqueness/indexes, downgrade preflight, metadata shape, or PostgreSQL operation compilation.
- Resolution: replaced SQLite NUMERIC casts with canonical positive Decimal
  TEXT grammar and exact TEXT identity equality; retained PostgreSQL Numeric
  arithmetic through dialect-scoped ORM/migration checks; added raw-SQL
  precision-collision, fractional-near-one, junk, exponent, non-finite, and
  dependency-value regressions.
- Tests: targeted migration gate after the fix — `49 passed, 15 deselected`.
- Verdict: not approved; P1 fixed and submitted for fresh re-review.

### Schema/migration review Pass 2

- Reviewer task name/vendor: `/root/t013q_schema_rereview`, fresh Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed manifest: the complete corrected schema/migration manifest at task
  branch HEAD `7263c06`.
- Findings (verbatim, P0–P3):

  > P0: None.
  >
  > P1 — PostgreSQL ORM metadata still permits partial dependency tuples and differs from the migration.
  >
  > - `app/models.py:531-541` and `app/models.py:557-567` omit `source/target_manual_rate_direction IS NOT NULL` in the complete branch. PostgreSQL CHECK treats a NULL result as satisfied, so id/value/updated_at present with direction NULL passes the model-generated constraint, while `alembic/versions/0004_transfer_quotes.py:185-190` and `:198-203` explicitly reject it. Add IS NOT NULL to both model branches and strengthen PostgreSQL compile tests to assert the expressions, not just constraint names.
  >
  > P2 — PostgreSQL `numeric` supports NaN and orders NaN greater than finite values, so current `> 0` checks in model/migration accept NaN for amounts/rate/dependency values, contrary to positive finite Decimal contract. Explicitly exclude non-finite special numeric values in PostgreSQL constraints and assert compiled DDL.
  >
  > P3: None.
  >
  > The prior SQLite exactness P1 is closed. SQLite now uses `String(80)`, canonical positive-Decimal grammar, and exact TEXT identity equality; adversarial exponent, junk, precision, and identity cases are covered.
- Resolution: added explicit non-null directions to both PostgreSQL dependency
  branches and excluded `NaN`, `Infinity`, and `-Infinity` from every Numeric
  amount/rate check in ORM and migration DDL; PostgreSQL compilation tests now
  assert the full expressions.
- Tests: targeted migration gate after the fix — `49 passed, 15 deselected`.
- Verdict: not approved; P1/P2 fixed and submitted for final re-review.

### Schema/migration review Pass 3

- Reviewer task name/vendor: `/root/t013q_schema_final_review`, fresh Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed manifest: complete final schema/migration manifest at task branch
  HEAD `7263c06`.
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
  > Both prior findings are closed. (1) SQLite quote amounts/rates and dependency values use TEXT storage with canonical positive-decimal checks; identity equality is exact text equality and rate `'1'`, with no NUMERIC cast or binary-float comparison path. The canonical grammar makes one stored representation per accepted positive value, so equality cannot collapse distinct high-precision values. (2) PostgreSQL dependency checks explicitly require non-null ID/value/direction/timestamp, positive ID/value, exact `asset_to_main` direction, and reject `NaN`, `Infinity`, and `-Infinity`; the same finite-value exclusion applies to all five Numeric quote fields. ORM dialect-scoped DDL and migration DDL match on types, named checks, conversion shape, FK/delete actions, unique executed link, and composite index.
  >
  > The additive revision is based on `0003_manual_rate_direction`; empty-only downgrade preflight runs before index/table DDL, and the tests verify a populated downgrade leaves both the row and Alembic version unchanged. SQLite coverage exercises canonical-text edge cases, tuple partials, direction/value failures, identity/cross shape failures, FKs/index/uniqueness metadata, empty and blocked downgrade; PostgreSQL compilation covers both ORM and actual migration operations. I relied on the reported targeted result `49 passed, 15 deselected in 19.05s` and did not run a broad suite. `git diff --check` passed (line-ending warnings only). No files edited.
- Resolution: none required; both earlier findings are closed.
- Reviewer checks: complete tracked/untracked manifest, targeted result
  `49 passed, 15 deselected in 19.05s`, and `git diff --check`.
- Verdict: approved with no open P0–P3 findings.

### Domain/API review Pass 1

- Reviewer task name/vendor: `/root/t013q_domain_api_review`, fresh Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed manifest: task branch base HEAD `7e59e88`, modified `app/main.py`,
  `app/models.py`, and `app/schemas.py`, plus untracked
  `app/transfer_quotes.py` and `tests/test_transfer_quotes_v21.py`.
- Findings (verbatim, P0–P3):

  > P0: None.
  >
  > P1: None.
  >
  > P2 — The frozen nested response/OpenAPI contract is not fully asserted. `tests/test_transfer_quotes_v21.py:96-112` checks only the top-level `TransferQuoteOut`; it never resolves/asserts `TransferQuoteAccountOut` or reused `AssetOut`, despite T-013Q acceptance requiring exact nested property/required/type/additional-property/bound sets. `app/schemas.py:149-154` has the intended compact account shape, but regression coverage would not catch it becoming permissive or gaining private fields.
  >
  > P2 — The required owner-private permission matrix is incomplete for unrelated users. `tests/test_transfer_quotes_v21.py:419-435` covers owner same/cross and shared editor/contributor/viewer same/cross, but `:437` exercises the unrelated user only against the same-asset pair. T-013Q explicitly requires unrelated users on both identity and cross-asset paths, so an unrelated cross-asset request could regress to a rate/pair-sensitive response without this test detecting it.
  >
  > P3: None.
  >
  > Verdict: Not approved until both P2 coverage gaps are closed and the focused quote test is rerun. I found no domain arithmetic, persistence, privacy-implementation, TTL-clock, or direct-operation regression defect in the inspected manifest.
- Resolution: closed the nested output contracts with `extra="forbid"` and
  exact account/Asset OpenAPI property, required, primitive, enum, bound, and
  additional-property assertions; added unrelated-user cross-asset privacy and
  mutation-neutrality coverage alongside the existing identity case.
- Tests: focused quote file after corrections — `8 passed in 3.45s`.
- Verdict: not approved; both P2 findings fixed and submitted for fresh review.

### Domain/API review Pass 2

- Reviewer task name/vendor: `/root/t013q_domain_api_rereview`, fresh Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed manifest: complete corrected domain/API manifest from base HEAD
  `7e59e88`, including the quote-only canonical SQLite bind type.
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
  > The two prior coverage findings are closed:
  >
  > - `TransferQuoteAccountOut` and nested `AssetOut` now have exact property and required sets, `additionalProperties: false`, expected primitive/enum types, and the positive account-ID bound asserted in OpenAPI.
  > - Privacy coverage now rejects an unrelated user with the generic `404 Workspace not found` for both same-asset and cross-asset pairs, while confirming no quote-row mutation.
  >
  > Adding `extra="forbid"` to shared `AssetOut` causes no response-contract defect: it remains an output model validated from ORM attributes, preserves its existing fields/types, and supplies the required closed nested OpenAPI shape.
  >
  > No regression found in Decimal-only arithmetic, destination quantization/effective-rate handling, immutable dependency snapshots, write neutrality, persistence, or the single-clock five-minute TTL. Focused verification rerun: `8 passed in 3.30s`. No files edited.
- Resolution: none required; both P2 findings are closed.
- Reviewer checks: full tracked/untracked manifest and focused quote rerun
  `8 passed in 3.30s`; no broad suite repeated.
- Verdict: approved with no open P0–P3 findings.

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
- 2026-08-11 Codex: readiness Pass 2 returned three P1 and one P2. Quote
  neutrality now requires exact Main-value equality before rounding; same-asset
  permissions match shipped owner/editor rules; dependency tuple constraints
  and execution conflict precedence are exact. Fresh readiness re-review
  remains; no application code or database was changed.
- 2026-08-11 Codex: readiness Pass 3 exposed non-additive legacy divide
  valuation at an aggregate rounding boundary. Both quote paths are now
  owner-only and reject applicable legacy rows until explicit canonical resave;
  the neutrality proof uses additive canonical multiplication. Fresh readiness
  re-review remains; no application code or database was changed.
- 2026-08-11 Codex: readiness Pass 4 approved committed task `dacb871` with no
  P0–P3 findings. Owner promotion and exact T-013Q branch claim are next; no
  application code or database was changed.
- 2026-08-11 Codex: updated the concise release-state handoff after readiness;
  a fresh read-only reviewer approved its exact backlog/task consistency with
  no P0–P3. T-013Q remains unclaimed pending owner promotion.
- 2026-08-11 Codex: resumed the active backend goal and rechecked integration
  HEAD `f026d02`, task/backlog status, readiness, dependencies, branch absence,
  and clean worktree. T-013Q is still `backlog`, so the repository-owner
  promotion gate remains unchanged and implementation cannot be claimed or
  started; no application, migration, test, schema, or database file changed.
- 2026-08-11 Codex: third consecutive goal audit at integration HEAD `092b168`
  found the identical owner-only promotion gate. Recorded the blocker, prior
  attempts, and exact unblock condition in task/PROGRESS; no implementation,
  branch, schema, migration, test, or database change was authorized.
- 2026-08-11 repository owner: explicitly authorized continuing implementation
  and owner lifecycle transitions without further approval waits. Promoted
  readiness-approved T-013Q task/BACKLOG from `backlog` to `todo`; exact branch
  claim from this committed integration HEAD is next.
- 2026-08-11 Codex: confirmed the exact task branch was absent and atomically
  claimed `task/T-013Q-transfer-quote` from promoted integration
  `fc1ce24088941667e1e473adce8fe49385ba63a1`. Recorded base/implementer and
  task+BACKLOG `in-progress`; schema/domain/API implementation is next.
- 2026-08-11 Codex: resumed the claimed task and completed the additive
  TransferQuote ORM/Alembic schema block. Three read-only review passes exposed
  and closed SQLite precision/coercion and PostgreSQL NULL/non-finite CHECK
  gaps; the final reviewer approved with no P0–P3. Targeted migration gate is
  `49 passed, 15 deselected`; domain/API implementation remains.
- 2026-08-11 Codex: implemented strict owner-private quote creation, exact
  same/cross-asset Decimal calculation through canonical Asset-to-Main rates,
  capital-neutral destination quantization, immutable dependency snapshots,
  normalized private response shapes, and a single-clock five-minute TTL.
  Domain/API re-review approved with no P0–P3; focused quote `8 passed`,
  adjacent valuation/operations `43 passed`, and migration/metadata `47 passed`.
  ADR and final T-013Q gates remain.
