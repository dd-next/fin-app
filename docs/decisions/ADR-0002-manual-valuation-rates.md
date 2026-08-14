# ADR-0002 — Valuation uses workspace-scoped manual rates only

Status: accepted · 2026-07-19 · Phases 9–10

## Context

Total capital and Available must be comparable across assets, but the release
excludes crypto sync and any external rate source, and two workspaces must not
be able to see or influence each other's valuation.

## Decision

Each workspace owns its manual valuation rates. Rates are isolated per
workspace, support override and delete with a defined fallback, and quantize
with `ROUND_HALF_UP` at the presentation boundary only.

Money and rates are `Decimal` everywhere; stored ledger values stay exact and
are quantized to asset precision only when serialized. Calculation helpers use
an explicit high-precision `Decimal` context or context-free sign operations.

Only same-asset internal transfers are required to stay neutral to Total
capital; cross-asset exchange valuation follows the active rates.

## Consequences

- No network dependency and no rate provider to operate.
- A workspace with stale rates shows stale totals. That is visible to the user
  and is preferred over a hidden external source of truth.
- Quantization is a presentation step, never a storage step.
