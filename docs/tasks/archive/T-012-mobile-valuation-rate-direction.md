---
id: T-012
title: Expose manual valuation rates in mobile asset-to-Main direction
status: done
size: M
spec: design/MOBILE-BACKEND-GAP-AUDIT.md rate direction
blocked-by: [T-001]
branch: task/T-012-mobile-valuation-rate-direction
base-commit: b592bfacaf868d522159b8602e2df2467aaab20c
implementer: Codex
readiness-reviewed-by: /root/t010_readiness_rereview (Codex same-vendor fallback)
readiness-reviewed-commit: e0f7e27
readiness-verdict: ready
---

## Goal

The owner-facing manual valuation-rate API speaks the frozen mobile contract
directly: a pair is `Asset → Main currency`, and its rate is the amount of Main
currency obtained for one unit of the source Asset. No public field exposes or
asks for the opposite legacy direction.

## Acceptance

- [x] Existing owner-only routes remain
      `GET /api/v1/workspaces/{workspace_id}/valuation-rates`,
      `PUT /api/v1/workspaces/{workspace_id}/valuation-rates/{asset_code}`,
      and `DELETE` on the same item route. The path `asset_code` is the source
      asset; the workspace's current Main currency is the target asset.
- [x] PUT accepts exactly `{"rate": "<positive plain Decimal string>"}` in
      source-to-target direction. JSON numbers are rejected so Starlette cannot
      materialize a binary float before Decimal validation. `displayed_rate`,
      `effective_valuation_rate`, unknown members, null, booleans, exponent/
      signed/non-plain strings, zero, negative, non-finite, over-38-digit,
      over-18-place, and canonical values outside Numeric(38,18) return
      input-derived `422` and mutate no row or account valuation. Canonical PUT
      never validates or stores a reciprocal.
- [x] Save and list responses expose exact keys `id`, `workspace_id`,
      `from_asset`, `to_asset`, `rate`, `source`, `created_at`, and
      `updated_at`. `from_asset` is the path asset, `to_asset` is the current
      Main currency, `source` is exactly `manual`, and `rate` is the normalized
      source-to-Main Decimal. Legacy `main_asset`, `asset`, `displayed_rate`,
      `effective_valuation_rate`, and redundant `active` keys are absent from
      the public contract and OpenAPI.
- [x] `from_asset` and `to_asset` are full `AssetOut` objects; `id` and
      `workspace_id` are integers; `source` is the single literal `manual`;
      `created_at`/`updated_at` are ISO datetime strings; and response `rate` is
      always an exact Decimal JSON string. Request `rate` is OpenAPI type
      `string` with the frozen plain-decimal pattern and the existing positive
      max-38-digit/max-18-place domain applied after exact Decimal parsing.
      Response `rate` is also OpenAPI type `string`; both are required and the
      components freeze their exact property/required/type sets.
- [x] Exact save/list JSON includes, modulo generated IDs/timestamps:

      ```json
      {
        "id": 1,
        "workspace_id": 1,
        "from_asset": {"id": 3, "code": "VND", "name": "Vietnamese dong", "kind": "fiat", "decimals": 0, "is_active": true},
        "to_asset": {"id": 1, "code": "USD", "name": "US dollar", "kind": "fiat", "decimals": 2, "is_active": true},
        "rate": "0.000038",
        "source": "manual",
        "created_at": "2026-08-11T00:00:00",
        "updated_at": "2026-08-11T00:00:00"
      }
      ```
- [x] The visible sample `VND → USD`, rate `0.000038`, round-trips in the same
      direction without float conversion. A VND balance is valued by
      `balance × rate` before the existing Main-currency `ROUND_HALF_UP`
      presentation boundary; no intermediate money value is quantized.
- [x] The shipped precision regression remains exact in the new direction:
      public `VND → USD` rate `0.000038034383082306` values
      `15,258,400 VND` to `580.34 USD`. The shorter frozen-screen sample and
      this mandatory valuation fixture are separate, both tested, and neither
      is replaced with a hard-coded total.
- [x] New/updated rows store the submitted canonical source-to-Main `rate`
      exactly; valuation multiplies the exact balance by it. The implementation
      never replaces the authoritative input with a rounded reciprocal. Public
      Decimal equality and derived valuation are stable across PUT, GET,
      reload, repeated upsert, SQLite, and the declared PostgreSQL Numeric
      boundary.
- [x] A new Alembic revision renames the internal
      `displayed_rate` column to neutral `rate_value` and adds a constrained
      direction discriminator with exactly `asset_to_main` and
      `main_to_asset_legacy`. Existing rows retain IDs, pair keys, numeric
      values, timestamps, and uniqueness byte-for-value and are tagged legacy;
      they are not inverted or rounded during migration. Fresh creates and
      updates use `asset_to_main`; updating a legacy row preserves its ID and
      converts that row to canonical storage.
- [x] Before any rename, constraint, Alembic-version update, or row mutation,
      migration preflight validates every legacy row is positive/finite and
      that `ROUND_HALF_UP_18(1 / rate_value)` is a nonzero supported canonical
      response. It reports the incompatible row ID deterministically and aborts
      with schema, data, indexes, timestamps, and version unchanged. Tests cover
      an underflowing old maximum, invalid stored values, repeating/terminating
      successful legacy values, and atomic failure.
- [x] `direction` is non-null with named check constraint
      `ck_manual_valuation_rate_direction` permitting only the two specified
      literals. Legacy backfill is atomic; any temporary server default is
      removed afterward so future omitted directions cannot be mis-tagged.
      The unique `(workspace_id, main_asset_id, asset_id)` constraint and all
      accepted indexes survive SQLite table-copy/alter behavior and PostgreSQL
      DDL unchanged.
- [x] Legacy rows remain readable and usable during the transition: output
      derives a supported 18-place asset-to-Main Decimal with the shared
      high-precision quotient/quantization helpers, and valuation divides only
      legacy rows. Canonical rows multiply. No float, ambient Decimal context,
      double inversion, or intermediate money quantization is allowed.
- [x] Downgrade is safe and explicit. Empty or legacy-only tables downgrade to
      `0002` by removing the tag and renaming `rate_value` back to
      `displayed_rate`, preserving every value/ID/pair/timestamp exactly. If any
      `asset_to_main` row exists, downgrade preflight aborts before DDL/data/
      version mutation; it never silently reinterprets or inverts canonical
      values. Migration tests prove all three states.
- [x] Exact boundaries are regression-protected: `rate=1` for a non-Main pair;
      minimum `0.000000000000000001`; maximum modeled Numeric value
      `99999999999999999999.999999999999999999`; one over-38-digit value; one
      19-place value; and high-precision terminating/repeating legacy
      conversions. The API enforces the modeled Numeric(38,18) portability
      domain even when SQLite TEXT could store more. Rejected boundary requests
      preserve the previous stored rate/direction and derived summary exactly.
- [x] Saving the Main currency as its own source remains `422 Main currency
      always values itself at exactly 1`; an unknown/inactive asset remains
      `422 Unknown asset`. A successful repeated PUT updates the same pair row,
      and DELETE removes only that current Main/source pair before the accepted
      direct-exchange fallback or `Unvalued` behavior applies.
- [x] Main-currency switching retains pair isolation. Rates saved for
      `VND → USD` disappear while EUR is Main, a separately saved `VND → EUR`
      row uses that direction, and switching back to USD returns the original
      row/rate unchanged. No old pair is converted, copied, or used under the
      new Main currency.
- [x] Workspace ownership and privacy remain exact. Shared editor/contributor/
      viewer and foreign users receive the accepted owner-private `404
      Workspace not found` for list/save/delete against the owner's workspace,
      cannot infer its pair or rate, and cannot mutate stored rows or summaries.
      Each owner sees and uses only their own workspace pairs.
- [x] Manual rates remain first in accepted valuation precedence; latest posted
      direct exchange remains fallback after delete; voided exchange rates and
      multi-hop/foreign-workspace rates remain ineligible. Ledger values,
      signed exchange legs, and Main-currency display quantization do not
      change.
- [x] The ledger and API share one canonical conversion helper: canonical rows
      use `decimal_product(balance, rate_value)`, legacy rows use the one
      explicit high-precision quotient path, and API output uses the same
      direction logic. Focused source assertions forbid `float(` and prevent
      the old unconditional `balance / displayed_rate` path from surviving.
- [x] OpenAPI has one exact mobile-direction request/response schema and no
      opposite-direction public properties. Migration tests prove clean install,
      accepted `0002` upgrade, legacy-row preservation, canonical new writes,
      constraints, application lifespan, and no schema drift beyond the one
      reviewed manual-rate revision. They inspect SQLite columns/checks/indexes
      and compile/bind the Numeric(38,18) and constraint DDL for PostgreSQL (or
      an equivalent explicit dialect portability check). No reset or
      `finapp.db` access occurs.
- [x] ADR-0008 records the canonical asset-to-Main storage direction, legacy
      discriminator/preflight, conditional downgrade, Decimal-string public
      boundary, and the explicit T-013 handoff; `docs/DECISIONS.md` indexes it.
- [x] Focused API/source tests, valuation/ledger/privacy/migration regressions,
      full pytest, Node syntax, and diff checks pass on isolated fixtures.

## Touches

- `app/schemas.py`
- `app/valuation_rates.py`
- `app/models.py`
- `app/ledger.py`
- `alembic/versions/0003_manual_rate_direction.py`
- `tests/test_valuation_rate_direction_v21.py`
- `tests/test_valuation_v2.py` and precision/privacy tests only where their
  old public direction is mechanically superseded
- `tests/test_migrations_v2.py`
- `docs/decisions/ADR-0008-canonical-manual-rate-direction.md`
- `docs/DECISIONS.md`
- `docs/tasks/T-012-mobile-valuation-rate-direction.md`
- `docs/BACKLOG.md` and `docs/PROGRESS.md` for task lifecycle only

## Out of scope

- Automatic/external rate providers, background refresh, freshness metadata,
  network dependencies, or enabling the mobile `Auto` placeholder.
- T-013 Transfer quote/execute semantics, rate-source selection for a command,
  quote expiry/binding, or changes to explicit Exchange inputs and captured
  exchange-rate rows.
- Cross-workspace or multi-hop valuation, changes to valuation precedence,
  account/transaction/period/Plan behavior, new assets, or display formatting.
- Any legacy-row numeric inversion, database reset, unrelated schema change,
  desktop/mobile UI implementation, Phase 15, push, PR, or deployment.

## Verification

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_valuation_rate_direction_v21.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_valuation_v2.py tests/test_phase9_ledger_integrity_v2.py tests/test_ledger_v2.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_migrations_v2.py -q
.\.venv\Scripts\python.exe -m pytest -q
node --check app/static/app.js
git diff --check
git status --short
```

All DB-backed tests use isolated in-memory fixtures. Migration/manual DB
commands require an explicit scratch `DATABASE_URL`; `finapp.db` is never used.

## Readiness review

Append-only readiness passes against the frozen mobile rate sheet/data model,
the accepted gap audit, ADR-0002, shipped valuation precision/privacy, AGENTS,
BACKLOG, and REVIEW_PROTOCOL.

### Pass 1

- Reviewer task name/vendor: `/root/t010_readiness_review`, Codex same-vendor
  fallback; cross-vendor reviewer unavailable in this session.
- Reviewed task-file commit: `e6889fd`.
- Findings (verbatim, P0–P3):

  > P0: None.
  >
  > P1 — Canonical PUT validation contradicts both canonical storage semantics and the required maximum boundary.
  >
  > - `docs/tasks/T-012-mobile-valuation-rate-direction.md:30-34` requires rejection when a submitted rate’s reciprocal is outside Numeric(38,18), while `:51-56` says the submitted asset-to-Main value is authoritative and no reciprocal replaces it.
  > - The contradiction is concrete at the required accepted maximum `99999999999999999999.999999999999999999` (`:70-75`): its reciprocal is approximately `1E-20`, below the stated 18-place minimum, although the canonical value itself fits Numeric(38,18) exactly.
  > - Canonical PUT should validate only the submitted finite positive asset-to-Main Decimal against the Numeric(38,18) precision/scale domain. No reciprocal-storage validation belongs on a canonical row because no reciprocal is stored. Move reciprocal representability rules exclusively to legacy-row compatibility/preflight semantics.
  >
  > P1 — Legacy preservation, readable output, and the 18-place public domain are not jointly satisfiable without a migration preflight.
  >
  > - Existing shipped rows may legally contain the old maximum Numeric(38,18) `displayed_rate`. T-012 requires every legacy value to remain byte-for-value unchanged and usable (`:57-69`), while its canonical reciprocal must be emitted as a supported nonzero 18-place rate.
  > - A valid legacy maximum has a reciprocal near `1E-20`; the shared `quantize_exchange_rate()` path rounds that to zero and rejects it. Thus an accepted pre-T-012 row can be preserved yet become unreadable through the required new response.
  > - Define an atomic preflight before any rename, constraint, Alembic-version, or data change. It must identify legacy row IDs whose stored value is invalid or whose canonical output cannot be represented under the chosen response domain, abort deterministically, and leave schema/data/version unchanged. Alternatively, explicitly permit a wider legacy-only response precision and specify how OpenAPI and valuation equality distinguish it; the current “supported 18-place” contract does not.
  > - Migration tests must include the underflowing legacy reciprocal, high-precision terminating/repeating cases, preflight failure atomicity, and a successful preservation case.
  >
  > P1 — Downgrade behavior is undefined and a naïve downgrade would silently corrupt valuation semantics.
  >
  > - The task says “forward-only Alembic revision” at `:57` but neither Acceptance nor Verification defines `downgrade()`.
  > - After any row has been converted to `asset_to_main`, simply dropping the direction column and renaming `rate_value` back to `displayed_rate` makes the shipped application divide by a value that the new application multiplied by. Exact inversion is not generally representable and is explicitly out of scope at `:133`.
  > - Freeze one safe policy:
  >   - permit downgrade only for empty/legacy-only tables, preserving values and timestamps exactly, and abort before DDL when any canonical row exists; or
  >   - declare the revision irreversibly forward-only and make `downgrade()` fail deterministically before mutation in every state.
  > - Tests must prove the chosen empty, legacy-only, and canonical-row behavior, including unchanged schema/data/version after a refused downgrade.
  >
  > P2 — The new request/response/OpenAPI field names lack exact public types and JSON representation.
  >
  > - `:35-41` freezes keys but not whether `from_asset` and `to_asset` are asset codes, `AssetOut` objects, or pair strings. The frozen mobile data model itself describes `pair ("VND → USD")`, while the shipped API currently returns full asset objects.
  > - Freeze the component types explicitly: IDs, `from_asset`, `to_asset`, `rate`, `source`, timestamps, and the JSON serialization of Decimal. Include one exact save/list JSON example and exact OpenAPI property types/required sets. Otherwise incompatible implementations can satisfy the same checklist.
  >
  > P2 — Portable direction-column DDL and preservation mechanics need tighter acceptance criteria.
  >
  > - The task requires a constrained discriminator but does not say whether the legacy backfill default is temporary. Leaving a database default of `main_to_asset_legacy` would silently mis-tag future writes that omit the column.
  > - Require a non-null direction column, a named check constraint allowing only the two values, atomic legacy backfill, and removal of any temporary server default after backfill. Preserve the existing unique pair and indexes through both SQLite’s table/alter limitations and PostgreSQL DDL.
  > - Verification should inspect SQLite columns/checks/indexes and exercise PostgreSQL Numeric(38,18) bind/DDL compilation or another explicit dialect-level portability check. “Declared PostgreSQL Numeric boundary” alone does not verify migration portability.
  >
  > P3: None.
- Resolution: canonical validation now ignores reciprocals; atomic legacy
  preflight, exact safe downgrade policy, public types/JSON/OpenAPI, and portable
  discriminator/default/constraint/index checks are explicit.
- Verdict: not ready; fresh readiness re-review required.

### Pass 2A

- Reviewer task name/vendor: `/root/t010_readiness_review`, Codex same-vendor
  fallback.
- Reviewed task-file commit: `595e8c8`.
- Findings (verbatim, P0–P3):

  > P0: None.
  >
  > P1: None.
  >
  > P2 — The exact response example is incompatible with the required `AssetOut` type, so the Pass 1 public-schema finding is not fully closed.
  >
  > - `docs/tasks/T-012-mobile-valuation-rate-direction.md:43-49` requires `from_asset` and `to_asset` to be full `AssetOut` objects and freezes exact property/required/type sets.
  > - At commit `595e8c8`, `app/schemas.py:55-63` defines `AssetOut` with required `id`, `code`, `name`, `kind`, `decimals`, and `is_active`.
  > - The task’s supposedly exact JSON at `:56-57` omits `kind` and `is_active` from both assets. An implementation returning the documented example therefore cannot also return full `AssetOut`.
  > - Add `"kind": "fiat"` and `"is_active": true` to both nested objects and require the focused schema/example test to assert those exact nested keys, or explicitly introduce and name a narrower public asset schema and freeze that instead.
  >
  > P3 — “Forward-only Alembic revision” conflicts editorially with the explicit supported downgrade.
  >
  > - `docs/tasks/T-012-mobile-valuation-rate-direction.md:79` calls revision `0003` forward-only, while `:106-111` requires successful downgrade for empty and legacy-only tables.
  > - The downgrade policy itself is sufficiently exact and safe; replace “forward-only” with “new” or “forward upgrade” to avoid contradictory implementation guidance.
- Resolution: exact nested `AssetOut` keys/spelling and conditional-downgrade
  wording are corrected; concurrent Pass 2B found the stricter Decimal-input
  and ADR gaps below.
- Verdict: not ready; fresh review required.

### Pass 2B

- Reviewer task name/vendor: `/root/t010_readiness_rereview`, Codex same-vendor
  fallback.
- Reviewed task-file commit: `595e8c8`.
- Findings (verbatim, P0–P3):

  > P0: None.
  >
  > P1 — Exact canonical Decimal input is incompatible with the allowed JSON-number path.
  >
  > - `docs/tasks/T-012-mobile-valuation-rate-direction.md:43-49` says a JSON number is accepted and parsed without application `float`, while `:73-78` requires the submitted canonical Decimal to be stored exactly.
  > - Default FastAPI/Starlette JSON decoding materializes fractional JSON numbers as Python `float` before Pydantic constructs the `Decimal`. A high-precision value such as `0.123456789012345678` can therefore arrive as a changed value, and large 38-digit boundaries can also be rounded or rejected based on the altered number.
  > - This contradicts the hard rule that rates are always Decimal and the task’s exact PUT/reload/repeated-upsert equality.
  > - Require rate inputs to be JSON strings only, rejecting JSON numbers, or explicitly authorize and test a custom Decimal-preserving request parser. “JSON string is canonical” does not make the simultaneously accepted numeric path exact.
  >
  > P2 — The claimed exact response example is not a valid full-`AssetOut` response.
  >
  > - `docs/tasks/T-012-mobile-valuation-rate-direction.md:43-49` requires `from_asset` and `to_asset` to be full `AssetOut` objects.
  > - The exact example at `:50-63` omits required `AssetOut.kind` and `AssetOut.is_active` from both objects. `AssetOut` requires `id`, `code`, `name`, `kind`, `decimals`, and `is_active` (`app/schemas.py:55-63`).
  > - The example also uses `"US Dollar"`, while the accepted seed value is `"US dollar"` (`alembic/versions/0001_release_v2.py:71-74`).
  > - Add the missing properties and exact accepted seed spelling so the example, JSON assertions, and OpenAPI reference cannot disagree.
  >
  > P2 — “Forward-only” still contradicts the required safe downgrade.
  >
  > - `docs/tasks/T-012-mobile-valuation-rate-direction.md:79` calls `0003` a “forward-only Alembic revision”.
  > - `:106-111` requires successful downgrade for empty and legacy-only tables and refusal only when canonical rows exist.
  > - The later policy is technically safe and closes the original downgrade gap, but the earlier label still permits an implementer to make every downgrade fail. Remove “forward-only” or replace it with the exact conditional-downgrade wording.
  >
  > P2 — The costly storage/downgrade decision has no ADR in scope.
  >
  > - Direction-tagged dual semantics, legacy preflight refusal, and conditional downgrade materially change the persistent schema and would cost real work to reverse.
  > - AGENTS requires such a decision to live in `docs/decisions/` and be indexed in `docs/DECISIONS.md`.
  > - ADR-0002 establishes workspace isolation, Decimal arithmetic, and presentation-only quantization, but does not record canonical asset-to-Main storage, the legacy direction discriminator, or downgrade policy.
  > - Touches should include a new ADR plus `docs/DECISIONS.md`, or an explicitly justified amendment to ADR-0002.
  >
  > P3: None.
- Resolution: request rate is now a plain Decimal JSON string only with exact
  string OpenAPI; the exact `AssetOut` example and wording are corrected; a new
  indexed ADR is required.
- Verdict: not ready; fresh readiness re-review required.

### Pass 3

- Reviewer task name/vendor: `/root/t010_readiness_rereview`, Codex same-vendor
  fallback; cross-vendor reviewer unavailable in this session.
- Reviewed task-file commit: `e0f7e27`.
- Findings (verbatim, P0–P3):

  > P0: None.
  > P1: None.
  > P2: None.
  > P3: None.
- Resolution: every prior readiness finding is closed; no further change
  required.
- Verdict: ready.

## Review

Append-only implementation review passes. A different read-only agent returns
the review; the implementer records it verbatim following
[`../REVIEW_PROTOCOL-v2.md`](../../REVIEW_PROTOCOL-v2.md).

### Pass 1

- Reviewer task name/vendor: `/root/t012_implementation_review` (Codex
  same-vendor fallback, fresh read-only agent).
- Reviewed base/head or working-tree manifest: `HEAD fbd590a` plus every
  tracked/untracked T-012 path in the paused working tree.
- Findings (verbatim, P0–P3):

  > P0: None.
  >
  > P1 — API and ledger do not share the single direction-aware conversion
  > helper required by Acceptance.
  >
  > - `app/ledger.py:130` and `app/ledger.py:141` implement two separate
  >   `direction` branches.
  > - API output calls `manual_rate_asset_to_main()`, while ledger valuation
  >   calls `apply_manual_valuation()`. Their canonical/legacy dispatch can
  >   therefore drift independently.
  > - `tests/test_valuation_rate_direction_v21.py:185` only forbids old source
  >   fragments; it does not freeze the required shared dispatch.
  > - Consolidate the direction decision into one operation used by both API
  >   output and ledger valuation, retaining legacy output quantization only at
  >   the public-rate boundary.
  >
  > P2 — Mandatory migration-state and portability regressions are incomplete.
  >
  > - `tests/test_migrations_v2.py:504` proves a legacy-only round trip using
  >   repeating reciprocal `26292`, but does not prove the required empty-table
  >   downgrade or a terminating legacy reciprocal.
  > - `tests/test_migrations_v2.py:581` does not assert timestamps and unique
  >   constraints remain unchanged after failed upgrade, although atomic
  >   preservation of both is explicit Acceptance.
  > - `tests/test_migrations_v2.py:670` compiles only the ORM model for
  >   PostgreSQL, not the actual `0003` upgrade/downgrade operations. The
  >   migration DDL compiled correctly in my read-only check, but no automated
  >   regression protects it.
  > - The named direction check is inspected but never exercised with an
  >   invalid inserted direction.
  >
  > P2 — The focused API tests do not freeze several explicit contract/security
  > requirements.
  >
  > - `tests/test_valuation_rate_direction_v21.py:25` does not assert the exact
  >   request pattern, integer ID types, `AssetOut` references/property sets, or
  >   timestamp types/formats promised by Acceptance.
  > - `tests/test_valuation_rate_direction_v21.py:110` checks rejected requests
  >   preserve the listed row, but not the required derived account summary.
  > - The suite has a valuation-rate privacy check for a viewer, but not the
  >   explicit editor/contributor/viewer plus unrelated-foreign-user matrix.
  >   Unknown and inactive asset behavior is also not focused-regression
  >   protected.
  >
  > P3: None.
- Resolution: P1 is fixed by the single `manual_rate_semantics()` direction
  dispatch consumed by both API projection and ledger application, with a
  source regression. P2 coverage now includes terminating/repeating/empty/
  canonical migration states, failed-upgrade row/timestamp/constraint/index
  neutrality, exercised direction CHECK, actual PostgreSQL operation
  compilation, exact OpenAPI nested/type/pattern checks, rejected-summary
  neutrality, the complete shared-role/foreign privacy matrix, and unknown/
  inactive assets. Focused re-run: `48 passed`; behavior/coverage changed, so
  fresh read-only re-review remains mandatory.
- Reviewer checks: focused API/ledger/migration `60 passed`; `git diff --check`
  passed; actual PostgreSQL migration operations compiled read-only.
- Verdict: not approved; P1/P2 fixes implemented, re-review pending.

### Pass 2

- Reviewer task name/vendor: `/root/t012_implementation_rereview` (Codex
  same-vendor fallback; cross-vendor reviewer unavailable).
- Reviewed base/head or working-tree manifest:
  `b592bfacaf868d522159b8602e2df2467aaab20c..81d6afaf5492d8be76aeb26a9cc27962df06adcb`
  on `task/T-012-mobile-valuation-rate-direction`; worktree clean at dispatch.
- Findings (verbatim, P0–P3):

  > Reviewer: `/root/t012_implementation_rereview` — Codex same-vendor fallback; cross-vendor reviewer unavailable.
  >
  > Reviewed range: `b592bfacaf868d522159b8602e2df2467aaab20c..81d6afaf5492d8be76aeb26a9cc27962df06adcb` on `task/T-012-mobile-valuation-rate-direction`.
  >
  > P0: None.
  >
  > P1: None.
  >
  > P2: None.
  >
  > P3: None.
  >
  > Missing tests: None for the bounded T-012 implementation.
  >
  > Pass 1 closure verified:
  >
  > - `app/ledger.py:130-157` centralizes direction dispatch in `manual_rate_semantics()`, consumed by both API projection and ledger valuation. Canonical rows multiply exactly; legacy rows divide, with quantization only for legacy public output.
  > - `app/schemas.py:85-106` and `app/valuation_rates.py:28-113` enforce the exact Decimal-string contract, canonical storage, normalized string output, and no reciprocal validation for canonical PUT.
  > - `alembic/versions/0003_manual_rate_direction.py:50-138` runs deterministic upgrade/downgrade preflights before DDL, preserves legacy values, removes the temporary default, and refuses canonical downgrade before mutation.
  > - `tests/test_migrations_v2.py:500-774` covers repeating and terminating legacy values, empty downgrade, canonical refusal, failed-upgrade neutrality, SQLite constraint/index preservation and invalid-direction rejection, plus actual PostgreSQL upgrade/downgrade operation compilation.
  > - `tests/test_valuation_rate_direction_v21.py:27-265` freezes OpenAPI/property types and patterns, rejected-request row/summary neutrality, canonical boundaries, legacy conversion, editor/contributor/viewer/foreign privacy, and unknown/inactive assets.
  > - ADR-0008 records the canonical direction, legacy policy, conditional downgrade, Decimal-string boundary, and T-013 handoff; `docs/DECISIONS.md` indexes it.
  > - The bounded diff contains no unrelated implementation and no `finapp.db` access.
  >
  > Independent checks:
  >
  > - `$env:PYTHONUTF8='1'; .\.venv\Scripts\python.exe -m pytest tests\test_valuation_rate_direction_v21.py tests\test_valuation_v2.py tests\test_phase9_ledger_integrity_v2.py tests\test_ledger_v2.py tests\test_migrations_v2.py -q` — `68 passed`.
  > - `git diff --check b592bfacaf868d522159b8602e2df2467aaab20c..81d6afaf5492d8be76aeb26a9cc27962df06adcb` — passed.
  > - Worktree remained clean at reviewed HEAD `81d6afaf5492d8be76aeb26a9cc27962df06adcb`.
  >
  > Non-finding environment note: the first test invocation without `PYTHONUTF8=1` produced `67 passed, 1 failed` only at the pre-existing locale-sensitive `Path.read_text()` assertion in `tests/test_migrations_v2.py:830-833`. Both that test and `docs/history/PROGRESS-phases-8-13.md` are unchanged from the reviewed base; the UTF-8 run passed.
  >
  > Verdict: **APPROVED**. All Pass 1 P1/P2 findings are closed; no open P0–P3 findings remain in the reviewed range.
- Resolution: every Pass 1 finding is closed; no further behavior or coverage
  change was required.
- Reviewer checks: focused API/ledger/migration `68 passed`; reviewed-range
  `git diff --check` passed; no `finapp.db` access.
- Verdict: approved; no open P0–P3 findings.

## Final gate evidence

- Scratch migration and E2E used only a temporary absolute `DATABASE_URL` and
  upgraded cleanly through `0003_manual_rate_direction`; `finapp.db` was not
  opened, replaced, or removed. The scratch server and directory were removed
  after verification.
- Scratch API round-trip saved `VND → USD` rate
  `0.000038034383082306`, listed the same canonical pair/rate, and valued
  `15,258,400 VND` as `580.34 USD`.
- Scratch SPA loaded as `FinApp v2`; browser login displayed the same
  `580.34 USD` total and account value with no console warnings/errors.
- `$env:PYTHONUTF8='1'; .\.venv\Scripts\python.exe -m pytest -q` —
  `268 passed, 246 warnings in 63.45s`.
- bundled `node.exe --check app/static/app.js` — passed.
- `git diff --check b592bfacaf868d522159b8602e2df2467aaab20c..81d6afa`
  and `git diff --check` — passed.

## Session log

Append-only. Every session that touches this task adds one entry before it
ends. Date · agent · what landed · what is left · open questions.

- 2026-08-11 Codex: drafted the bounded asset-to-Main manual-rate contract
  after local T-010 acceptance. Independent gap analyses and readiness review,
  owner promotion, exact branch claim, implementation, and review remain.
- 2026-08-11 Codex: independent storage analysis found that a finite canonical
  rate can have a non-terminating reciprocal. The task now stores new canonical
  values exactly and migrates existing inverse rows with a direction tag and no
  numeric rewrite; readiness review remains.
- 2026-08-11 Codex: readiness Pass 1 returned three P1 and two P2 migration/
  type gaps. Canonical validation, legacy preflight, downgrade refusal,
  response/OpenAPI types, and portable DDL mechanics are now exact. Fresh
  readiness re-review remains.
- 2026-08-11 Codex: concurrent readiness Pass 2 reviews found exact JSON,
  JSON-number precision, downgrade wording, and ADR gaps. The task now requires
  Decimal strings only, a valid full-AssetOut example, conditional wording, and
  ADR-0008. Fresh readiness re-review remains.
- 2026-08-11 Codex: readiness Pass 3 approved committed task `e0f7e27` with no
  P0–P3 findings. Owner promotion and exact branch claim are next.
- 2026-08-11 Owner: promoted readiness-approved T-012 from backlog to todo.
  Exact accepted-integration branch claim is next.
- 2026-08-11 Codex: claimed the task from exact accepted integration
  `b592bfacaf868d522159b8602e2df2467aaab20c`; implementation is in progress.
- 2026-08-11 Codex: implemented canonical Decimal-string Asset-to-Main API,
  direction-tagged storage/migration, shared valuation semantics, ADR-0008,
  and focused API/privacy/migration coverage. Pre-review full suite was
  `260 passed`; Pass 1 returned one P1 and migration/API P2 coverage gaps, all
  implemented and rechecked as `48 passed`. Handoff remains on the exact task
  branch. Next: fresh read-only re-review, retry scratch SPA E2E (the API
  scenario reached the SPA request, where PowerShell `Invoke-WebRequest`
  itself threw; scratch was cleaned), then full pytest/Node/diff, complete task
  evidence/status, and create the final T-012 task commit. No open product
  question; no push/PR/deploy is authorized.
- 2026-08-11 Codex: fresh implementation Pass 2 approved the exact committed
  range with no P0–P3 findings; independent focused checks passed `68` tests.
  Scratch migration/API/SPA E2E passed on a temporary database, including the
  exact `580.34 USD` browser value; full pytest passed `268`, Node syntax and
  diff checks passed. The task is in review and awaits local owner acceptance;
  no open question, and nothing was pushed, deployed, or run against
  `finapp.db`.
- 2026-08-11 Owner: accepted reviewed task commit `437b5fa` by fast-forward
  into local `finapp-v2-develop`. T-012 is done; T-013 is next; nothing was
  pushed, deployed, or run against `finapp.db`.
