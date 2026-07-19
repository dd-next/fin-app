# FinApp v2 — release progress ledger

This is the active progress file for the new FinApp v2 release. Read
[`specs/FinnApp-v2.md`](specs/FinnApp-v2.md),
[`BUILD_PLAN-v2.md`](BUILD_PLAN-v2.md), and
[`REVIEW_PROTOCOL-v2.md`](REVIEW_PROTOCOL-v2.md) before resuming work.

Status legend: `[ ]` not started · `[~]` in progress · `[x]` completed · `[!]` blocked

## Current release plan

- [x] Phase 8 — Documentation and specification reset
- [x] Phase 9 — Clean release schema
- [ ] Phase 10 — Financial correctness
- [ ] Phase 11 — Operations and account periods UI
- [ ] Phase 12 — Transactions and Plan
- [ ] Phase 13 — Docker and release verification

## Starting point — 2026-07-19

- The repository contains a prior Tracker/commitment prototype and its prior
  completion ledger. It is historical evidence only and does not meet this
  release's Operations/account-period/Plan requirements.
- This documentation package defines the new release boundary. No application
  code, migration, database, or runtime behavior is changed by this setup.
- Clarification locked for future implementation: ended-period funding/date
  edits and correction/soft void require explicit confirmation; a closed period
  remains read-only. Phase 10 must test this distinction.
- Before Phase 9, create and verify a timestamped backup of local `finapp.db`.
  Record its path, SHA-256 checksum, and open/restore verification here.

## Phase log

### Phase 8 — Documentation and specification reset (2026-07-19)

- Status: [x]
- Completed: consolidated all active documents under `docs/`, with active and
  historical specifications under `docs/specs/`; root v2 files are
  compatibility pointers and root `specs/` is removed. Defined Main currency,
  Operations/Undo, account periods, revised Transactions/Plan, clean reset,
  Docker delivery, manual acceptance, and the mandatory review protocol.
- Reviewer blocks: authority map → `phase8_authority_review` → APPROVED with no
  findings; specification → `phase8_spec_review` → two P1 findings (ended
  confirmation and exchange neutrality) fixed → `phase8_spec_rereview`
  APPROVED; execution/acceptance → `phase8_execution_review` → restore-proof,
  coverage, fresh-path, and Docker-command findings fixed →
  `phase8_execution_rereview` APPROVED with no unresolved P0–P2.
- Tests: `env -u DATABASE_URL PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m
  pytest -p no:cacheprovider -q` — **81 passed in 7.87s**;
  `node --check app/static/app.js` — passed; `PYTHONDONTWRITEBYTECODE=1
  .venv/bin/python -m compileall -q app tests` — passed; `.venv/bin/pip check`
  — no broken requirements; `git diff --check` — passed.
- Checks: active document targets exist, root `specs/` is absent, no stale
  pre-relocation active paths remain, and the documentation authority map is
  internally consistent.
- Decisions / assumptions: ended-period funding/date edits and financial
  correction/soft void require confirmation; closed periods are read-only.
  Only same-asset internal transfers are required to stay neutral to Total
  capital; cross-asset exchange valuation follows active rates.
- Blocker: none.

### Phase 9 — Clean release schema (2026-07-19)

- Status: [x]
- Completed: created and independently restored the timestamped legacy backup;
  replaced the five-revision prototype history with clean head
  `0001_release_v2`; introduced workspace/manual rates, workspace exchange
  rates, strict `Transaction.origin`, immutable leg timestamps,
  account-specific periods, and persisted Operations Undo state. Removed
  Tracker/commitment/frozen-valuation models, routes, clients, and obsolete
  Plan Pay/Receive; seeded exactly eight release assets and created a clean
  runtime `finapp.db` with zero users.
- Reviewer blocks: backup/reset → `phase9_backup_review` → APPROVED, no P0–P3;
  schema/migration → `phase9_schema_review` → P1 unrestricted origin fixed
  with DB constraint → `phase9_schema_rereview` APPROVED; runtime cleanup →
  `phase9_runtime_cleanup_review` → APPROVED; legacy SPA clients →
  `phase9_legacy_client_review` → P3 stale wording fixed; migration/regression
  tests → `phase9_regression_review` → three P2 coverage gaps fixed →
  `phase9_regression_rereview` APPROVED with all P2 closed.
- Tests: `env -u DATABASE_URL PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m
  pytest -p no:cacheprovider -q` — **66 passed**; targeted Phase 9 regression
  set — **18 passed in 2.15s**; `node --check app/static/app.js` — passed;
  `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m compileall -q app tests` —
  passed; `.venv/bin/pip check` — no broken requirements; `env -u DATABASE_URL
  .venv/bin/alembic check` — no new upgrade operations; `git diff --check` —
  passed.
- Checks: backup SHA-256
  `f2441becb810355345dce10370c6c96a8a8373a416f383dc65f96baaa74b748a`;
  source `.backups/finapp-pre-v2-20260719T035114Z.db` and byte-identical
  scratch restore at
  `/private/tmp/finapp-phase9-restore-20260719T035114Z.db` both report
  `PRAGMA integrity_check` — `ok`, legacy head `0005_v2`, 3 users, and 25
  financial transactions. Fresh migration and runtime DB pass integrity at
  `0001_release_v2`, contain the exact release tables/assets and no users;
  application lifespan and `/health` pass; OpenAPI contains no Tracker,
  commitment, Pay, or Receive routes.
- Decisions / assumptions: retained both the SQLite online backup and exact
  original file for recoverability; Git history retains the removed migration
  chain. The Operations placeholder is intentionally transitional and is
  replaced by the functional Phase 11 surface.
- Blocker: none.

### Phase 10 — Financial correctness (2026-07-19)

- Status: [x]
- Completed: manual valuation rates are workspace/Main-pair scoped with manual
  precedence, posted direct-rate fallback, Main-switch isolation, and no
  multi-hop; Main-currency presentation now rounds once with `ROUND_HALF_UP`
  while exact high-precision Decimal arithmetic is preserved through ledger,
  sign, valuation, reconciliation, and aggregate paths.
  Account-specific periods now provide owner-only create/list/read/edit/close,
  snapshot-bound signed replay, Plan cards, lifecycle confirmation, and closed
  record guards across all financial mutation paths.
- Reviewer blocks: rate isolation/manual precedence →
  `phase10_valuation_review` → P2 missing isolation/latest/void/multi-hop/CRUD
  regressions fixed → `phase10_valuation_rereview` APPROVED; money presentation
  → `phase10_money_presentation_review` → P1 ambient Decimal-context truncation
  and P2 weak precision fixture fixed → `phase10_money_presentation_rereview` →
  P1 unary sign truncation fixed → `phase10_money_presentation_final_review`
  APPROVED; account-period replay → `phase10_period_replay_review` → P2
  movement/Plan matrix gaps fixed → `phase10_period_replay_rereview` → P2
  ambiguous Plan-status assertion fixed → `phase10_period_replay_final_review`
  APPROVED; mutation guards/privacy → `phase10_period_guards_review` → P2
  guard-path/privacy matrix gaps fixed → stalled
  `phase10_period_guards_rereview` stopped without accepting a result →
  `phase10_period_guards_final_review` → four residual P2 rollback/permission
  gaps fixed → `phase10_period_guards_closure_review` APPROVED with no P0–P3.
  Phase commit gate → `phase10_commit_gate_review` → APPROVED with no P0–P3
  and no unrelated changes.
- Tests: valuation block targeted suite — **9 passed in 1.62s**; `env -u
  DATABASE_URL PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p
  no:cacheprovider -q tests/test_valuation_v2.py
  tests/test_phase9_ledger_integrity_v2.py tests/test_ledger_v2.py
  tests/test_plan_v2.py` — **24 passed in 3.41s**; compileall,
  `node --check app/static/app.js`, and `git diff --check` — passed; period,
  budget, ledger, and Plan targeted suite — **41 passed in 2.60s**; mutation
  guard targeted suite — **50 passed in 4.55s**; final period suite — **12
  passed in 1.89s**; `env -u DATABASE_URL PYTHONDONTWRITEBYTECODE=1
  .venv/bin/python -m pytest -p no:cacheprovider -q` — **86 passed in 7.59s**;
  `.venv/bin/python -m compileall -q app tests`, `node --check
  app/static/app.js`, `.venv/bin/pip check`, and `git diff --check` — passed.
- Checks: conflicting workspaces, manual delete fallback, void fallback,
  Unvalued/no-multi-hop, shared-account valuation isolation, VND regression,
  maximum 38-digit crypto plus smallest unit, direct-rate multiplication,
  aggregate-before-rounding, and exact outgoing sign are covered.
  Snapshot funding, strict leg timestamp membership, same-account overlap,
  cross-account transfer/exchange replay, fee/root void, all signed movement
  types, and open/in-range/account-bound Planned selection are also covered.
  `env -u DATABASE_URL .venv/bin/alembic check` reports no new upgrade
  operations; the phase gate independently passed 20 valuation/period tests,
  OpenAPI boundary, `/health`, budget purity, no-float, and diff checks.
- Decisions / assumptions: calculation helpers use an explicit high-precision
  Decimal context or context-free sign operations; API quantization remains a
  separate final presentation step.
- Blocker: none.

## Required phase-entry template

Copy this structure for every phase. Do not mark a phase complete without every
line being evidenced.

```md
### Phase N — <name> (YYYY-MM-DD)

- Status: [~] / [x] / [!]
- Completed: <2–4 concise implementation facts>
- Reviewer blocks: <block → reviewer task name → findings → resolution>
- Tests: `<exact command>` — <exact pass/fail result>
- Checks: <migration/browser/Docker/link/diff evidence required by the phase>
- Decisions / assumptions: <only decisions not already specified>
- Blocker (if any): <cause and attempted fixes>
```

## Historical note

Git history preserves the earlier root-level implementation ledger. The current
root-level `PROGRESS.md` is only a compatibility pointer and must not be used to
skip the phases above.
