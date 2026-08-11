---
id: T-010
title: Keep owner-private periods non-authorizing for shared users
status: backlog
size: M
spec: specs/ACCOUNT_PERIODS-v2.1.md §11
blocked-by: [T-008, T-009]
branch: task/T-010-owner-private-period-permissions
base-commit:
implementer:
readiness-reviewed-by: /root/t010_readiness_rereview (Codex same-vendor fallback)
readiness-reviewed-commit: 23825eb
readiness-verdict: ready
---

## Goal

Account periods remain fully owner-private and never change which otherwise
permitted financial actions a shared-account user can perform or which generic
permission/confirmation result that user receives.

## Acceptance

- [ ] For each `editor`, `contributor`, and `viewer`, valid collection requests
      to `POST /accounts/{account_id}/periods`, default and explicit
      `scope=all|current|history` variants of
      `GET /accounts/{account_id}/periods`, and
      `GET /accounts/{account_id}/periods/current` return the same owner-private
      `404 Account not found` as a foreign user. Detail/PATCH/close routes for
      known current, ended, and closed IDs return the same
      `404 Account period not found` as an unknown ID. Responses never contain
      lifecycle, date, balance, policy, allowance, or creator facts, and every
      rejected write is mutation-neutral.
- [ ] `GET /transactions?period_id=...` is owner-private for every shared role
      and foreign user. A known period ID, an unknown period ID, and a known ID
      combined with matching or mismatching `account_id` all return the same
      `404 Account period not found` before account-filter validation, without
      returning transaction rows or period facts.
- [ ] A shared `editor` can Spend, Add funds, Transfer, and Exchange on the
      same participating accounts permitted by the existing role matrix, and a
      shared `contributor` can Spend. Each allowed create has the same HTTP
      status and public transaction shape when the account owner's relevant
      period state is absent, current, naturally ended, or manually closed.
      Hidden ended periods require no period confirmation from a shared user;
      current balances remain ledger-derived and closed snapshots remain
      immutable.
- [ ] `POST /transactions/{transaction_id}/assign-account` has the same hidden
      period invariance. A shared contributor may assign their own unassigned
      expense to an expense-permitted shared account; an editor may assign
      their own expense or income to a role-permitted shared account. With an
      absent, current, ended, or closed hidden period, the same valid request
      succeeds without period confirmation. Creator, transaction-state,
      workspace, asset, role, hidden-account, and foreign-account failures keep
      their accepted exact `403`/`404`/`409`/`422` result and leave the
      transaction, legs, rates, Undo state, periods, and snapshots unchanged.
- [ ] Shared transaction correction, Delete, and Operations Undo retain their
      existing generic shared confirmation contract regardless of absent,
      current, ended, or closed hidden period state: an unconfirmed permitted
      mutation returns exactly `409 Shared transaction correction requires
      explicit confirmation`, a confirmed mutation follows the existing
      success path, and neither response mentions a period or differs because
      of one. No shared response returns the owner-only `Ended account period
      change requires explicit confirmation` or the transitional hidden-state
      string `Transaction change requires explicit confirmation`.
- [ ] The generic shared-mutation matrix remains exact. An editor may
      correction/Delete only when every root and fee-child leg is editable,
      and may Undo only their own eligible Operations candidate with all
      required account permissions. A contributor may Undo their own Spend
      but may not correction/Delete or Undo income/transfer/exchange; a viewer
      may not mutate. Hidden or foreign root/child/fee legs return `404`, and
      role-insufficient visible accounts return `403`, before generic
      confirmation or hidden-period evaluation for absent/current/ended/closed
      states. Existing one-leg visibility and `has_hidden_legs` redaction do
      not change.
- [ ] Existing role and participating-account authorization remains the first
      effective boundary: contributor Add funds/Transfer/Exchange/edit/Delete,
      all viewer writes, and any Transfer/Exchange with a forbidden or foreign
      source, target, or fee account retain their accepted `403`/`404` result
      with or without a hidden period and do not mutate any transaction, leg,
      rate, Undo, period, or snapshot row.
- [ ] Account owners retain the accepted T-008 behavior. A financial change
      inside their naturally ended period returns `409 Ended account period
      change requires explicit confirmation` until the retained transaction
      `confirm_ended_period` member is true; current/closed/no-period behavior,
      period route access, exact Decimal ledger effects, and closed snapshot
      immutability do not change.
- [ ] Owner-only `POST /accounts/{account_id}/reconcile` retains its accepted
      exact Decimal adjustment and no-period/current/closed behavior under the
      centralized guard change. Editor/contributor/viewer and foreign attempts
      retain the same `403`/`404` permission result before period evaluation,
      including with an ended hidden period, and rejected requests are
      mutation-neutral.
- [ ] The shared-user privacy decision is centralized in the period-impact
      guard rather than duplicated per command. Period read/write routes still
      use owner-only account lookup; no public schema, model, migration,
      rollover formula, lifecycle boundary, transaction visibility/redaction,
      sharing-role definition, or desktop UI contract changes.
- [ ] Focused tests cover all period routes and Transactions period filtering,
      the create/correction/Delete/Undo matrix, every shared role, multi-account
      source/target/fee permissions, owner regression, mutation neutrality, and
      exact error text. Existing period, operations, transactions, sharing,
      privacy, frontend, and full-suite regressions pass.

## Touches

- `app/periods.py`
- `tests/test_period_permissions_v21.py`
- `tests/test_periods_v2.py`, `tests/test_operations_v2.py`,
  `tests/test_operations_undo_v2.py`, `tests/test_sharing_v2.py`, and existing
  privacy/transaction tests only where an old hidden-period shared-user
  expectation is mechanically superseded
- `docs/tasks/T-010-owner-private-period-permissions.md`
- `docs/BACKLOG.md` and `docs/PROGRESS.md` for task lifecycle only

## Out of scope

- New roles, changes to the accepted Viewer/Contributor/Editor action matrix,
  account ownership transfer, workspace permissions, invitation behavior, or
  transaction visibility/redaction changes.
- Period schemas, lifecycle/snapshot/allowance math, transaction confirmation
  field removal/rename, models, migrations, database reset, or dormant
  RebaseEvent cleanup.
- T-012 rates, T-013 transfer quote/execution, later Phase 14 tasks, Phase 15
  mobile UI, deployment, push, or PR creation.

## Verification

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_period_permissions_v21.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_period_api_v21.py tests/test_period_contract_removal_v21.py tests/test_periods_v2.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_operations_v2.py tests/test_operations_undo_v2.py tests/test_transactions_phase12_v2.py tests/test_phase12_privacy_v2.py tests/test_sharing_v2.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_migrations_v2.py -q
.\.venv\Scripts\python.exe -m pytest -q
node --check app/static/app.js
git diff --check
git status --short
```

All DB-backed tests use isolated in-memory fixtures. Any migration/manual DB
command must set an explicit scratch `DATABASE_URL`; `finapp.db` is never used.

## Readiness review

Append-only readiness passes against ACCOUNT_PERIODS-v2.1 §11, the accepted
T-008/T-009 privacy and transaction-confirmation contracts, AGENTS, BACKLOG,
and REVIEW_PROTOCOL. Readiness must confirm that private period state becomes
non-authorizing only for shared users, while owner confirmation and the
existing generic shared correction confirmation remain intact.

### Pass 1

- Reviewer task name/vendor: `/root/t010_readiness_review`, Codex same-vendor
  fallback; cross-vendor reviewer unavailable in this session.
- Reviewed task-file commit: `75f3ce1`.
- Findings (verbatim, P0–P3):

  > Read-only readiness review of committed task file `75f3ce1`.
  >
  > P0: None.
  >
  > P1 — The financial-route inventory is incomplete, so §11 can remain violated while every written acceptance item passes.
  >
  > - T-010 enumerates Spend, Add funds, Transfer, Exchange, correction, Delete, and Undo (`docs/tasks/T-010-owner-private-period-permissions.md:37-53,71-75`) but omits `POST /transactions/{transaction_id}/assign-account`. That route is an existing financial mutation, accepts `confirm_ended_period`, and calls the same period guard (`app/transactions.py:809-849`). A shared contributor may assign their own unassigned expense to an expense-permitted shared account, and an editor may assign their own expense or income; hidden ended-period state must neither block nor change that accepted result.
  > - The task also does not explicitly include owner-only `POST /accounts/{account_id}/reconcile`, another direct caller of `enforce_transaction_period_impact` (`app/accounts.py:244-279`). It cannot become shared, but the centralized guard change requires a focused owner regression proving its existing no-period/current/closed behavior and Decimal ledger result remain unchanged.
  > - Add both routes to the acceptance/test matrix. `assign-account` needs absent/current/ended/closed shared-user cases, role/creator/account permission failures, exact responses, and mutation neutrality. Reconcile needs owner regression and shared `403` precedence. No additional application module necessarily needs modification if the centralized `app/periods.py` fix is sufficient.
  >
  > P1 — The correction/Delete/Undo and participating-account matrix is not exact enough to preserve existing authorization and privacy ordering.
  >
  > - “Unconfirmed permitted mutation” and “every shared role” (`docs/tasks/T-010-owner-private-period-permissions.md:45-59,71-75`) do not identify which role/type combinations are permitted. Current Undo is creator-scoped and derives rights from transaction type: a contributor may Undo their own Operations Spend, while income requires editor, transfer/exchange require editor on every participating account, and adjustment remains owner-only (`app/operations.py:84-129,132-169`). The task explicitly denies contributor edit/Delete but never says that contributor own-Spend Undo remains permitted and must receive the generic shared confirmation contract.
  > - The task also does not freeze the existing hidden-leg boundary for correction/Delete/Undo. A shared editor who sees a transaction through one shared leg but lacks another root or fee-child account must receive the existing owner-private `404` before either generic confirmation or period evaluation; current coverage demonstrates this boundary for patch/Delete (`tests/test_sharing_v2.py:221-264`). The source/target/fee language at task lines 54-59 can be read as create-only and does not explicitly cover visible transactions with hidden legs or Undo child legs.
  > - Enumerate the matrix: editor correction/Delete only when every root and child leg is editable; editor Undo only for their own eligible Operations candidate with all required accounts; contributor own-Spend Undo is permitted but correction/Delete and other Undo types retain their existing denials; viewers cannot mutate; hidden or foreign root/child/fee legs return `404`, role-insufficient visible accounts return `403`, and both precede generic confirmation and hidden-period evaluation. Cover absent/current/ended/closed states and confirmed/unconfirmed paths without weakening redaction.
  >
  > P2 — The period-route privacy matrix does not explicitly cover every accepted list route variant.
  >
  > `GET /accounts/{account_id}/periods` supports `scope=all|current|history` (`app/periods.py:584-610`), but T-010 names only the collection route generically (`docs/tasks/T-010-owner-private-period-permissions.md:24-31`). “All period routes” at lines 71-75 can be satisfied with the default scope alone, leaving history/current list variants untested even though their result sets reveal lifecycle existence. Require each shared role and a foreign user to receive exact `404 Account not found` for default/all/current/history, plus the already specified create/current/detail/PATCH/close matrix and rejected-write neutrality.
  >
  > P2 — Dependency metadata does not match the contract the task says it consumes.
  >
  > Front matter and BACKLOG list only `blocked-by: [T-008]` (`docs/tasks/T-010-owner-private-period-permissions.md:7`), while the readiness scope and acceptance explicitly depend on the accepted T-009 final confirmation/schema contract (`:93-95,116-120`) and verification runs T-009’s removal suite. T-009 is already accepted and is an ancestor of `75f3ce1`, so this is not a live blocker, but the durable dependency should be `T-009` or `[T-008, T-009]` in both task and backlog.
  >
  > P2 — The Python verification commands are not runnable in the recorded Windows/PowerShell workspace.
  >
  > Lines 102-105 invoke `.venv/bin/python`, but that path does not exist here; `.venv\Scripts\python.exe` does. Replace those commands with the workspace-valid PowerShell path, or document and verify an available Bash environment. The remaining named existing test modules, Node check, diff check, and status check are valid; the new focused test module is appropriately expected to be created during implementation.
  >
  > P3: None.
  >
  > Additional checks:
  >
  > - `git diff --check 75f3ce1^ 75f3ce1` passed.
  > - T-008 and T-009 are accepted ancestors of the reviewed commit.
  > - The Touches/Out-of-scope boundary is otherwise coherent: the intended behavior can remain centralized in `app/periods.py`, with no schema, model, migration, formula, visibility/redaction, role-definition, or UI change.
  > - Size M is plausible after the route and role matrices are explicitly frozen and implemented with parameterized tests; as written, the missing cases prevent reliable sizing and acceptance.
  > - No tests were run because this was a documentation readiness review; no files were edited and no branch was switched.
  >
  > Verdict: **NOT READY**.
- Resolution: added assign-account and reconcile matrices, exact editor/
  contributor/viewer correction/Delete/Undo permissions, hidden root/child/fee
  precedence, every list scope, T-009 dependency, and runnable Windows gates.
- Verdict: not ready; fresh readiness re-review required.

### Pass 2

- Reviewer task name/vendor: `/root/t010_readiness_rereview`, Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed task-file commit: `23825eb`.
- Findings (verbatim, P0–P3):

  > Read-only readiness re-review of commit `23825eb`.
  >
  > P0: None.
  > P1: None.
  > P2: None.
  > P3: None.
  >
  > All Pass 1 findings are closed:
  >
  > - `assign-account` now covers absent/current/ended/closed lifecycle invariance, contributor-own-expense and editor-own-expense/income success cells, creator/state/workspace/asset/role/privacy failures, exact accepted response preservation, and mutation neutrality.
  > - Reconcile preserves owner Decimal/no-period/current/closed behavior and shared-role `403` versus foreign `404` precedence before hidden-period evaluation.
  > - Correction/Delete/Undo explicitly preserves editor permissions, creator-scoped editor Undo, contributor own-Spend Undo, contributor/viewer denials, generic confirmation text, and confirmed/unconfirmed behavior.
  > - Hidden or foreign root/child/fee legs remain `404`; visible but role-insufficient accounts remain `403`; both precede confirmation and period evaluation. Existing one-leg visibility and `has_hidden_legs` redaction are frozen.
  > - Period-route privacy includes default plus explicit `scope=all|current|history`, current lookup, create, detail, PATCH, and close across shared roles and foreign users.
  > - Transactions filtering requires the same private `404` for known/unknown period IDs and matching/mismatching account filters before account-filter validation.
  > - T-009 is recorded in both task front matter and BACKLOG and is an accepted ancestor.
  > - Every direct period-impact path is represented: create operations through the shared helpers, correction, assign-account, Delete/Undo, and reconcile.
  > - The PowerShell verification paths exist; every named existing test module and `app/static/app.js` exists. The focused T-010 test file is correctly implementation-created.
  > - The centralized `app/periods.py` change, bounded test updates, Touches, and Out-of-scope sections are coherent. No schema, model, migration, role, redaction, formula, or UI change is authorized.
  > - Size M is plausible with parameterized role/lifecycle matrices.
  > - `git diff --check 23825eb^ 23825eb` passed.
  > - Worktree remained clean on `finapp-v2-develop`; no files were edited and no branch was switched.
  > - No implementation tests were run for this documentation-only review.
  >
  > Verdict: **READY**.
- Resolution: all P0–P2 findings are closed; no further changes required.
- Verdict: ready.

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

- 2026-08-11 Codex: drafted the bounded owner-private permission task after
  local T-009 acceptance. Independent readiness review, owner promotion, exact
  branch claim, implementation, and review remain; no open question.
- 2026-08-11 Codex: readiness Pass 1 returned two P1 and three P2 findings.
  The task now freezes assign/reconcile, every role/type Undo cell, hidden-leg
  precedence, list scopes, durable dependencies, and runnable Windows gates.
  Fresh readiness re-review remains; no open question.
- 2026-08-11 Codex: readiness Pass 2 approved the corrected task with no
  P0–P3 findings. Owner promotion and exact branch claim are next; no open
  question.
