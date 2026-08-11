# ADR-0009 — Persist exact, short-lived Transfer quotes

Status: accepted · 2026-08-11

## Context

The mobile Transfer flow accepts one source amount and a destination account,
including a destination in another asset. The shipped backend instead requires
both amounts for an explicit exchange. Recalculating a destination amount at
execution time would let rate or Main-currency changes silently alter a command
the owner already reviewed, while independently rounded legs could change
aggregate Total capital.

Legacy manual-rate rows also store the reciprocal direction and value balances
through finite-precision division. That arithmetic is not additive across
accounts and therefore cannot prove aggregate neutrality for an arbitrary
Transfer.

## Decision

- A quote is an immutable persisted command snapshot with a five-minute
  lifetime. Its lifecycle is permanently `open → executed`; execution is
  single-use and T-013E binds the resulting transaction atomically.
- Quote creation and execution are owner-only and return the generic
  owner-private workspace `404` to shared or unrelated users.
- Cross-asset calculation uses only current canonical manual
  `Asset → Main` rows. Source value multiplies into Main; a non-Main target is
  solved through exact high-precision division.
- A tagged `main_to_asset_legacy` row is never inverted or silently upgraded
  for quoting. The owner must resave the displayed `Asset → Main` value through
  the T-012 endpoint before a quote can be created.
- The source amount is validated once at source precision. The exact target is
  quantized once, `ROUND_HALF_UP`, to destination precision. The effective
  public rate is derived from the two stored amounts and quantized separately
  to 18 places.
- A quote is persisted only when exact outgoing Main value equals exact
  incoming Main value before presentation rounding. Canonical multiplication
  is additive, so this preserves aggregate Total capital for any unrelated
  balances.
- Same-asset quotes use identity amounts and rate `1`, with no rate dependency
  snapshots. An applicable legacy row is still rejected because its valuation
  path is non-additive; Main, canonical, latest-exchange multiplication, and
  unvalued paths remain neutral when the combined asset balance is unchanged.
- Each non-Main cross side snapshots the manual-rate row ID, exact stored
  value, direction, and update timestamp, together with account, asset, Main,
  amount, and creator identities. T-013E rejects execution as stale if a
  dependency is changed/deleted, Main changes, or an applicable legacy row
  appears; it never recalculates the destination amount.
- Expired rows remain as audit evidence. There is no cleanup queue, worker,
  scheduler, Redis dependency, or external rate provider.
- Downgrade to `0003_manual_rate_direction` is permitted only when the quote
  table is empty; otherwise it aborts before DDL or Alembic-version mutation.

## Consequences

- The quote table is additive and does not rewrite the existing ledger,
  transactions, rates, periods, or Undo state.
- SQLite stores quote Decimals as canonical exact text with strict constraints;
  PostgreSQL uses `Numeric(38,18)` and explicitly excludes non-finite numeric
  values. Both dialects enforce the same dependency and lifecycle shapes.
- Rate/Main changes deliberately invalidate an open quote instead of changing
  its amounts. The owner must request a new quote.
- Quote creation alone never moves money. T-013E owns atomic execution,
  concurrency, expiry/staleness precedence, signed legs, periods, and Undo.
