---
id: T-019
title: Expose the mobile Plan-rule contract
status: done
size: M
spec: design/MOBILE-BACKEND-GAP-AUDIT.md Plan rule shape
blocked-by: [T-001]
branch: task/T-019-mobile-plan-contract
base-commit: 9d60864
implementer: Codex GPT-5
readiness-reviewed-by: owner fast-track exception
readiness-reviewed-commit: 9d60864
readiness-verdict: ready
---

## Goal

Phase 15 can create, edit, and read a Plan rule through the existing API using
the mobile kind and single dynamic account field without weakening the richer
desktop Plan contract.

## Acceptance

- [x] Existing PlanRule storage and routes remain authoritative; no migration,
  ledger movement, or new Plan subsystem is added.
- [x] Frozen mobile camelCase kinds (including `expectedIncome`) map to the
  existing stored kinds; every response exposes a stable
  mobile kind plus `to_account` for income and `from_account` otherwise.
- [x] Mobile `account_id` maps to the destination for income and source for
  expense/transfer kinds while conflicting directional fields fail with 422.
- [x] The existing create/PATCH routes and a single owner-private detail GET
  return the adapter fields and preserve the required toggle and Decimal amount.
- [x] Existing occurrence Skip/Link semantics remain occurrence-scoped;
  archival skips open items, retains resolved history/transactions, and blocks
  future active selection/materialization.
- [x] Asset/category/direction validation and foreign-workspace privacy remain
  server-enforced.

## Touches

`app/schemas.py`, `app/plan.py`, Plan-focused tests, this task file, backlog and
progress state.

## Out of scope

No category merge/delete, transaction conversion, account restoration, schema
change, ledger change, Plan rewrite, or Phase 15 UI.

## Verification

```bash
.venv/bin/python -m pytest -q tests/test_mobile_plan_contract_v21.py tests/test_plan_v2.py tests/test_planned_transaction_feed_v21.py
git diff --check
```

## Review

### Pass 1

- Reviewer task name/vendor: `/root/t019_review`, Codex GPT-5.6 Terra medium;
  same-vendor fallback because a cross-vendor reviewer was unavailable.
- Reviewed base/head or working-tree manifest: base `9d60864`; modified
  `app/plan.py`, `app/schemas.py`, `docs/BACKLOG.md`; untracked task file and
  `tests/test_mobile_plan_contract_v21.py`.
- Findings (P0–P3): P2 — add mobile-adapter create/PATCH coverage for
  `reserve_transfer`, including preservation of its separate destination.
- Resolution: added the exact source-alias and preserved-destination regression;
  behavior did not change, so ADR-0010 fast-track does not require re-review.
- Reviewer checks: inspected the bounded tracked/untracked manifest and named
  specs; `git diff --check` passed.
- Verdict: P2 closed; no open P0–P3.

### Pass 2

- Reviewer task name/vendor: `/root/t019_review`, Codex GPT-5.6 Terra medium.
- Reviewed base/head or working-tree manifest: limited final diff after the
  exact camelCase mobile-kind correction and transfer regression.
- Findings (P0–P3): no findings.
- Resolution: none.
- Reviewer checks: inspected schema/route/test changes, legacy input
  compatibility, exact mobile output mapping, transfer source/destination test,
  OpenAPI coverage, and `git diff --check` (passed).
- Verdict: clean; no open P0–P3.

## Session log

- 2026-08-12 Codex GPT-5: claimed under the owner-approved fast-track from
  `9d60864`; implementing the bounded mobile adapter, detail read, and focused
  regressions. Review and acceptance remain.
- 2026-08-12 Codex GPT-5: implementation and focused privacy/Plan regressions
  passed; independent Terra/medium review found one P2 transfer-coverage gap,
  closed with a no-behavior-change test. Commit and owner fast-forward remain.
- 2026-08-12 Codex GPT-5: aligned kinds to the frozen camelCase contract,
  passed limited re-review with no findings, and completed the task with
  `17 passed`; nothing remains for T-019.
