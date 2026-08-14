# ADR-0010 — Fast-track Phase 14 on disposable pre-production data

Status: accepted · 2026-08-12

## Context

FinApp is not yet used as the owner's permanent financial store. The current
database contains disposable test data, while the unusable desktop UI blocks
real adoption. Preserving intermediate test rows and completing non-critical
backend conveniences before the mobile redesign costs more than the protected
data is worth.

## Decision

Until Phase 15 is accepted and the owner explicitly starts permanent use, the
migration/data-preservation gates are limited as follows:

- only a fresh `alembic upgrade head`, one Alembic head, schema constraints,
  application startup, and `/health` are release gates;
- populated-database upgrades, migration downgrades, and preservation of the
  current test rows are unsupported and do not block Phases 14 or 15;
- the known ambient-Decimal rounding risk in the populated `0002` migration is
  accepted because that migration path will not be used for permanent data;
- T-015 transaction-type conversion, T-016 category merge/delete, and T-017
  archived-account restoration are deferred to the post-Phase-15 backlog;
- Phase 15 omits the deferred edit controls and does not promise restoration.
  Existing supported desktop/backend behavior is not removed;
- T-021 is a lean acceptance task for the backend contracts that remain in the
  Phase 14 critical path, not a new exhaustive compatibility programme.

Targeted runtime tests, the final full suite, JavaScript syntax, diff/status,
fresh-schema constraints, Decimal/ledger behavior, and permission checks remain
required under the build plan.

Once permanent use starts, every later schema change must again preserve the
then-current database or provide an explicit backup/reset decision. This ADR
does not relax Decimal, ledger, atomicity, permission, or fresh-schema
correctness for runtime behavior.

## Consequences

- T-019 is the last product backend task in Phase 14; T-021 and T-022 close the
  phase.
- Existing migration tests may remain, but agents do not add populated or
  downgrade work unless the owner brings it back into scope.
- T-015/T-016/T-017 remain visible and ordered in backlog rather than being
  discarded.
