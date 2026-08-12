# FinApp — Phase 14 close evidence

Phase 14: backend contract synchronization · accepted 2026-08-12.

## Outcome

- Replaced editable period funding/remaining/planned contracts with exact
  ledger-derived opening/current/closing snapshots, reconciliation input,
  optional lifecycle, Start-date replay, two Decimal allowance policies, and
  owner-private API/permission behavior.
- Added canonical Asset-to-Main manual rates, exact bound transfer quote and
  atomic execution, stable financial-date persisted/planned feed, and the
  minimal mobile Plan-rule adapter.
- Consolidated the accepted contracts into `specs/FinnApp-v2.md`. ADR-0010
  explicitly defers T-015/T-016/T-017 and limits pre-production migration gates
  to a fresh database while preserving runtime financial/security invariants.
- Every task passed independent read-only review; all P0–P2 findings were
  closed. The accepted task files are archived below.

## Final gates

```text
retained-contract smoke                    7 passed in 1.06s
full pytest                                341 passed in 32.45s
node --check app/static/app.js             passed
git diff --check                           passed
alembic heads                              0004_transfer_quotes (single head)
fresh alembic upgrade head                 0001 -> 0002 -> 0003 -> 0004
fresh alembic check                        no new upgrade operations
scratch FastAPI /health                    200 {"status":"ok"}
scratch SPA /                              200 text/html
```

The full suite emitted 246 existing Python 3.12 SQLite date/datetime adapter
deprecation warnings. No populated upgrade, downgrade, or preservation gate was
run under ADR-0010. T-021 contains the exact command/evidence record.

## Accepted tasks

- [T-001](../tasks/archive/T-001-mobile-backend-contract-sync.md)
- [T-002](../tasks/archive/T-002-period-model-migration.md)
- [T-003](../tasks/archive/T-003-ledger-derived-balance.md)
- [T-004](../tasks/archive/T-004-period-lifecycle.md)
- [T-005](../tasks/archive/T-005-carry-next-day-policy.md)
- [T-006](../tasks/archive/T-006-redistribute-policy.md)
- [T-007](../tasks/archive/T-007-period-start-replay.md)
- [T-008](../tasks/archive/T-008-period-api-lifecycle-surface.md)
- [T-009](../tasks/archive/T-009-remove-legacy-period-contracts.md)
- [T-010](../tasks/archive/T-010-owner-private-period-permissions.md)
- [T-012](../tasks/archive/T-012-mobile-valuation-rate-direction.md)
- [T-013Q](../tasks/archive/T-013Q-transfer-quote.md)
- [T-013E](../tasks/archive/T-013E-transfer-execution.md)
- [T-014F](../tasks/archive/T-014F-financial-date-transaction-feed.md)
- [T-014P](../tasks/archive/T-014P-planned-feed-projection.md)
- [T-019](../tasks/archive/T-019-mobile-plan-contract.md)
- [T-021](../tasks/archive/T-021-phase14-acceptance.md)
- [T-022](../tasks/archive/T-022-phase14-spec-merge.md)

## Decisions and handoff

- Period authority: [ADR-0005](../decisions/ADR-0005-periods-are-optional-and-ledger-derived.md)
- Mobile backend-first order: [ADR-0007](../decisions/ADR-0007-mobile-design-is-frozen-and-backend-first.md)
- Canonical rates: [ADR-0008](../decisions/ADR-0008-canonical-manual-rate-direction.md)
- Bound quotes: [ADR-0009](../decisions/ADR-0009-bound-transfer-quotes.md)
- Pre-production fast-track: [ADR-0010](../decisions/ADR-0010-preproduction-fast-track.md)

Phase 15 was not started. Its first task is T-023: specify/readiness-review the
approved-token import and responsive mobile shell, then claim it from the
accepted `finapp-v2-develop` head.
