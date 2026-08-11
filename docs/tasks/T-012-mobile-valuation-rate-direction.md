---
id: T-012
title: Expose manual valuation rates in mobile asset-to-Main direction
status: backlog
size: M
spec: design/MOBILE-BACKEND-GAP-AUDIT.md rate direction
blocked-by: [T-001]
branch: task/T-012-mobile-valuation-rate-direction
base-commit:
implementer:
readiness-reviewed-by:
readiness-reviewed-commit:
readiness-verdict:
---

## Goal

The owner-facing manual valuation-rate API speaks the frozen mobile contract
directly: a pair is `Asset → Main currency`, and its rate is the amount of Main
currency obtained for one unit of the source Asset. No public field exposes or
asks for the opposite legacy direction.

## Acceptance

- [ ] Existing owner-only routes remain
      `GET /api/v1/workspaces/{workspace_id}/valuation-rates`,
      `PUT /api/v1/workspaces/{workspace_id}/valuation-rates/{asset_code}`,
      and `DELETE` on the same item route. The path `asset_code` is the source
      asset; the workspace's current Main currency is the target asset.
- [ ] PUT accepts exactly `{"rate": <positive Decimal>}` in source-to-target
      direction. `displayed_rate`, `effective_valuation_rate`, unknown members,
      null, booleans, zero, negative, non-finite, over-38-digit, over-18-place,
      and canonical values outside Numeric(38,18) return input-derived `422`
      and mutate no row or account valuation. Canonical PUT never validates or
      stores a reciprocal.
- [ ] Save and list responses expose exact keys `id`, `workspace_id`,
      `from_asset`, `to_asset`, `rate`, `source`, `created_at`, and
      `updated_at`. `from_asset` is the path asset, `to_asset` is the current
      Main currency, `source` is exactly `manual`, and `rate` is the normalized
      source-to-Main Decimal. Legacy `main_asset`, `asset`, `displayed_rate`,
      `effective_valuation_rate`, and redundant `active` keys are absent from
      the public contract and OpenAPI.
- [ ] `from_asset` and `to_asset` are full `AssetOut` objects; `id` and
      `workspace_id` are integers; `source` is the single literal `manual`;
      `created_at`/`updated_at` are ISO datetime strings; and response `rate` is
      always an exact Decimal JSON string. The request `rate` uses the existing
      positive Decimal input domain (JSON string is canonical; a JSON number is
      parsed without application `float`). Both fields are required and the
      OpenAPI components freeze their exact property/required/type sets.
- [ ] Exact save/list JSON includes, modulo generated IDs/timestamps:

      ```json
      {
        "id": 1,
        "workspace_id": 1,
        "from_asset": {"id": 3, "code": "VND", "name": "Vietnamese dong", "decimals": 0},
        "to_asset": {"id": 1, "code": "USD", "name": "US Dollar", "decimals": 2},
        "rate": "0.000038",
        "source": "manual",
        "created_at": "2026-08-11T00:00:00",
        "updated_at": "2026-08-11T00:00:00"
      }
      ```
- [ ] The visible sample `VND → USD`, rate `0.000038`, round-trips in the same
      direction without float conversion. A VND balance is valued by
      `balance × rate` before the existing Main-currency `ROUND_HALF_UP`
      presentation boundary; no intermediate money value is quantized.
- [ ] The shipped precision regression remains exact in the new direction:
      public `VND → USD` rate `0.000038034383082306` values
      `15,258,400 VND` to `580.34 USD`. The shorter frozen-screen sample and
      this mandatory valuation fixture are separate, both tested, and neither
      is replaced with a hard-coded total.
- [ ] New/updated rows store the submitted canonical source-to-Main `rate`
      exactly; valuation multiplies the exact balance by it. The implementation
      never replaces the authoritative input with a rounded reciprocal. Public
      Decimal equality and derived valuation are stable across PUT, GET,
      reload, repeated upsert, SQLite, and the declared PostgreSQL Numeric
      boundary.
- [ ] A forward-only Alembic revision renames the internal
      `displayed_rate` column to neutral `rate_value` and adds a constrained
      direction discriminator with exactly `asset_to_main` and
      `main_to_asset_legacy`. Existing rows retain IDs, pair keys, numeric
      values, timestamps, and uniqueness byte-for-value and are tagged legacy;
      they are not inverted or rounded during migration. Fresh creates and
      updates use `asset_to_main`; updating a legacy row preserves its ID and
      converts that row to canonical storage.
- [ ] Before any rename, constraint, Alembic-version update, or row mutation,
      migration preflight validates every legacy row is positive/finite and
      that `ROUND_HALF_UP_18(1 / rate_value)` is a nonzero supported canonical
      response. It reports the incompatible row ID deterministically and aborts
      with schema, data, indexes, timestamps, and version unchanged. Tests cover
      an underflowing old maximum, invalid stored values, repeating/terminating
      successful legacy values, and atomic failure.
- [ ] `direction` is non-null with named check constraint
      `ck_manual_valuation_rate_direction` permitting only the two specified
      literals. Legacy backfill is atomic; any temporary server default is
      removed afterward so future omitted directions cannot be mis-tagged.
      The unique `(workspace_id, main_asset_id, asset_id)` constraint and all
      accepted indexes survive SQLite table-copy/alter behavior and PostgreSQL
      DDL unchanged.
- [ ] Legacy rows remain readable and usable during the transition: output
      derives a supported 18-place asset-to-Main Decimal with the shared
      high-precision quotient/quantization helpers, and valuation divides only
      legacy rows. Canonical rows multiply. No float, ambient Decimal context,
      double inversion, or intermediate money quantization is allowed.
- [ ] Downgrade is safe and explicit. Empty or legacy-only tables downgrade to
      `0002` by removing the tag and renaming `rate_value` back to
      `displayed_rate`, preserving every value/ID/pair/timestamp exactly. If any
      `asset_to_main` row exists, downgrade preflight aborts before DDL/data/
      version mutation; it never silently reinterprets or inverts canonical
      values. Migration tests prove all three states.
- [ ] Exact boundaries are regression-protected: `rate=1` for a non-Main pair;
      minimum `0.000000000000000001`; maximum modeled Numeric value
      `99999999999999999999.999999999999999999`; one over-38-digit value; one
      19-place value; and high-precision terminating/repeating legacy
      conversions. The API enforces the modeled Numeric(38,18) portability
      domain even when SQLite TEXT could store more. Rejected boundary requests
      preserve the previous stored rate/direction and derived summary exactly.
- [ ] Saving the Main currency as its own source remains `422 Main currency
      always values itself at exactly 1`; an unknown/inactive asset remains
      `422 Unknown asset`. A successful repeated PUT updates the same pair row,
      and DELETE removes only that current Main/source pair before the accepted
      direct-exchange fallback or `Unvalued` behavior applies.
- [ ] Main-currency switching retains pair isolation. Rates saved for
      `VND → USD` disappear while EUR is Main, a separately saved `VND → EUR`
      row uses that direction, and switching back to USD returns the original
      row/rate unchanged. No old pair is converted, copied, or used under the
      new Main currency.
- [ ] Workspace ownership and privacy remain exact. Shared editor/contributor/
      viewer and foreign users receive the accepted owner-private `404
      Workspace not found` for list/save/delete against the owner's workspace,
      cannot infer its pair or rate, and cannot mutate stored rows or summaries.
      Each owner sees and uses only their own workspace pairs.
- [ ] Manual rates remain first in accepted valuation precedence; latest posted
      direct exchange remains fallback after delete; voided exchange rates and
      multi-hop/foreign-workspace rates remain ineligible. Ledger values,
      signed exchange legs, and Main-currency display quantization do not
      change.
- [ ] The ledger and API share one canonical conversion helper: canonical rows
      use `decimal_product(balance, rate_value)`, legacy rows use the one
      explicit high-precision quotient path, and API output uses the same
      direction logic. Focused source assertions forbid `float(` and prevent
      the old unconditional `balance / displayed_rate` path from surviving.
- [ ] OpenAPI has one exact mobile-direction request/response schema and no
      opposite-direction public properties. Migration tests prove clean install,
      accepted `0002` upgrade, legacy-row preservation, canonical new writes,
      constraints, application lifespan, and no schema drift beyond the one
      reviewed manual-rate revision. They inspect SQLite columns/checks/indexes
      and compile/bind the Numeric(38,18) and constraint DDL for PostgreSQL (or
      an equivalent explicit dialect portability check). No reset or
      `finapp.db` access occurs.
- [ ] Focused API/source tests, valuation/ledger/privacy/migration regressions,
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

### Pass 2

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
