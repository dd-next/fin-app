# ADR-0008 — Manual valuation rates use canonical Asset-to-Main direction

Status: accepted · 2026-08-11

## Context

The frozen mobile settings flow describes a manual pair as `Asset → Main` and
asks how much Main currency one unit of the source Asset is worth. The shipped
backend exposed and stored the reciprocal (`1 Main = X Asset`). Persisting only
a rounded reciprocal cannot preserve every finite Decimal input or guarantee
that valuation uses the exact public rate.

## Decision

The public manual-rate boundary accepts only a positive plain Decimal JSON
string named `rate`. JSON numbers are rejected before they can pass through a
binary float. New and updated rows store that exact `Asset → Main` value and
valuation multiplies the balance by it.

Storage uses a neutral `rate_value` plus a constrained direction discriminator.
Existing values are retained without numeric rewriting and tagged
`main_to_asset_legacy`; canonical writes use `asset_to_main`. Upgrade preflight
rejects any legacy value that cannot produce a supported nonzero 18-place
public rate before schema or data changes begin. Empty and legacy-only tables
can downgrade losslessly; a canonical row makes downgrade fail before mutation.

T-013 may consume the canonical direction when it defines transfer quoting,
but it must not change this setting's storage meaning or reinterpret captured
transaction exchange rates.

## Consequences

- PUT, GET, and LIST share one exact `Asset → Main` contract and never expose
  the reciprocal legacy field names.
- Legacy rows remain readable and keep their historical valuation arithmetic;
  updating one converts only that row to canonical storage.
- The schema change needs an Alembic revision and a guarded conditional
  downgrade, but avoids lossy bulk inversion and preserves existing pair IDs,
  timestamps, and values.
- SQLite and PostgreSQL enforce the same modeled Numeric(38,18) public domain,
  even though SQLite stores exact decimals as text locally.
