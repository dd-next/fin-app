# ADR-0011 — Fast-track Phase 15 to a usable local preview

Status: accepted · 2026-08-12

## Context

Phase 14 closed the backend contract gap for the frozen mobile design, but the
current desktop-first SPA still prevents comfortable daily use. Development is
local and the owner will push and deploy only after the mobile UI is usable.
Long broad reviews before every visible increment would delay feedback, while
skipping bounded review entirely would make financial, privacy, and desktop
regressions too easy to ship unnoticed.

## Decision

Phase 15 follows a local **usable-preview fast-track**:

- no Phase 15 task pushes, deploys, or changes production; the owner will
  publish the integrated UI later;
- every task keeps a checkable task file, targeted tests, and one independent
  read-only review of only that task's bounded diff;
- reviewers do not reopen accepted Phase 14 backend design or perform a broad
  repository audit unless the bounded diff supplies evidence of a regression;
- fixes receive a limited re-review only when they change behavior or test
  coverage, as required by the existing protocol;
- P0 and P1 findings block every preview and task acceptance; an individual P2
  may become preview debt only when it does not affect financial correctness,
  permissions/privacy, destructive actions, core navigation, or basic
  accessibility and the owner explicitly accepts it in that task record; P3
  may be deferred with a recorded disposition; Phase 15 is not formally closed
  until all P0–P2 findings are resolved;
- task verification is targeted during implementation. The complete pytest,
  JavaScript syntax, fresh-schema/runtime, 390×844 acceptance, and preserved
  desktop matrix run once in the T-030/T-031 close path;
- each implemented screen gets a scratch-database 390×844 browser smoke before
  task acceptance so visual defects are found before the final matrix;
- T-024, T-027, and T-030 are split before implementation. After shared mobile
  primitives are accepted, independent screen tasks may use separate Git
  worktrees, but integration and owner acceptance remain serialized.

The fast-track does not relax the frozen mobile geometry, English copy,
accessibility targets, desktop preservation, Decimal/ledger derivation,
permissions, privacy, or the Phase 14 API contracts. Native `select`, `alert`,
`confirm`, and `prompt` are removed from the completed build, not hidden behind
mobile-only styling.

## Usable-preview boundary

A local preview may be used for feedback after T-025 through T-028 are
integrated and their P0/P1 findings are closed. It is not a Phase 15 release:
T-029 interaction/accessibility integration, T-030 acceptance/regression, and
T-031 documentation/close still remain.

## Consequences

- T-023 is the only initial `todo` task.
- T-024 becomes T-024A/T-024B, T-027 becomes T-027A/T-027B, and T-030 becomes
  T-030A/T-030B.
- T-025, T-026, T-027A, and T-028 may be prepared in parallel worktrees only
  after T-024B is accepted. Because the SPA is intentionally small and uses one
  stylesheet, merge conflicts are resolved and reverified on the feature task
  branch before serialized acceptance into `finapp-v2-develop`.
- The owner may inspect and use intermediate local previews without treating
  them as accepted, pushed, deployed, or safe for permanent financial data.
