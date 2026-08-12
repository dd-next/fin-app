---
id: T-009
title: Remove legacy period money contracts
status: done
size: S
spec: specs/ACCOUNT_PERIODS-v2.1.md §3, §9–§10
blocked-by: [T-008]
branch: task/T-009-remove-legacy-period-contracts
base-commit: 79fb477fa42397b0d4fa4ffe2cdf6ec52595d185
implementer: Codex
readiness-reviewed-by: /root/t009_readiness_review (Codex same-vendor fallback)
readiness-reviewed-commit: 6c8d9cf
readiness-verdict: ready
---

## Goal

The period API and its existing desktop consumer expose only ledger-derived
opening/current/closing facts and allowance, with every T-008 transitional
`funding_amount`, `remaining`, `planned`, and period-confirmation contract
removed.

## Acceptance

- [x] `AccountPeriodCreate` contains only optional `start_date`, required
      `end_date`, and optional `rollover_policy`; `AccountPeriodPatch` contains
      only those same three optional business fields. Create preserves T-008:
      omitted Start resolves to the captured workspace-local today, omitted
      policy selects redistribution, explicit null Start/policy, unknown
      policy, future Start, missing end, and reversed dates are `422`. PATCH
      preserves T-008: at least one business field is required, explicit null
      or unknown policy is `422`, and valid Start/end/policy combinations keep
      their accepted lifecycle and replay behavior.
- [x] Both schemas keep `extra="forbid"`. The newly forbidden create
      `funding_amount` and PATCH `funding_amount`/`confirm_ended_period` are
      each tested with exactly these JSON representatives: null, false, zero,
      valid-looking string `"1"`, empty string, malformed string
      `"not-a-value"`, empty array, and empty object. Every value is tested
      alone and combined with an otherwise valid business field; create
      persists no period or ledger mutation and PATCH leaves the complete
      period snapshot/policy/lifecycle and ledger row set unchanged.
- [x] Current, ended, and closed response schemas and every create/current/
      list/detail/PATCH/close response omit `funding_amount`, `remaining`, and
      `planned`. OpenAPI asserts exact period component properties:
      `AccountPeriodCreate={start_date,end_date,rollover_policy}` with only
      `end_date` required; `AccountPeriodPatch={start_date,end_date,
      rollover_policy}`; current response equals the T-008 common fact set
      `{id,account_id,asset,created_by_user_id,start_date,end_date,snapshot_at,
      opening_balance,rollover_policy,created_at,status,closed_at,
      closing_balance}` plus `{current_balance,available_today}`; ended and
      closed equal only the common fact set. Period components contain no
      confirmation member, while transaction request components retain their
      existing `confirm_ended_period` and Plan components retain
      `planned_amount`.
- [x] Final lifecycle shapes otherwise remain exactly as accepted in T-008:
      current returns `opening_balance`, `current_balance`, and
      `available_today`; ended returns the historical opening snapshot and
      null close pair without live fields; closed returns opening and closing
      snapshots without live fields. Asset-precision `ROUND_HALF_UP`, exact
      internal Decimal invariants, one route cutoff T, policy behavior, and
      current/null lookup do not change.
- [x] Period serialization and routes have no `PlanRule`, `PlanOccurrence`, or
      `RebaseEvent` query/import and no legacy zero/alias assignment. The Plan
      subsystem and its `planned_amount` contracts remain unchanged and no
      planned event affects balance or allowance.
- [x] The existing desktop SPA stops submitting or reading the removed period
      members. It removes the Funding control, help/status/history copy and
      selector; removes the period Planned card and its DOM identifier while
      preserving the unrelated Plan UI; renames the Remaining card and DOM
      identifier to Current balance and reads `current_balance`; and submits
      only Start/end on create/PATCH without the ended-period confirmation
      helper. History renders current as opening/current, ended as opening
      with no invented closing value, and closed as opening/closing. This is a
      mechanical compatibility update, not a Phase 15 visual redesign.
- [x] Dormant RebaseEvent storage/relationships and Alembic revision
      `0002_period_snapshot_model` remain unchanged. No schema migration,
      model removal, legacy-row migration, or database reset is introduced.
- [x] Focused tests prove the exact removed-input matrix is mutation
      neutral, exact key omission for current/ended/closed and every period
      route, the exact OpenAPI component sets and preserved unrelated
      transaction/Plan members, unchanged VND/18-decimal presentation,
      unchanged Plan behavior, and absence of removed SPA request/response
      references. Existing lifecycle, allowance, Transactions-filter,
      operations, frontend, and full-suite regressions pass.

## Touches

- `app/schemas.py`
- `app/periods.py`
- `app/static/app.js`
- `app/static/index.html`
- `tests/test_period_contract_removal_v21.py`
- `tests/test_period_api_v21.py`
- `tests/test_periods_v2.py` and existing period/operations/frontend tests
  only where a T-008 transitional request, response, or UI assertion is
  mechanically superseded
- `docs/tasks/T-009-remove-legacy-period-contracts.md`
- `docs/BACKLOG.md` and `docs/PROGRESS.md` for task lifecycle only

## Out of scope

- Permission or shared-account behavior changes — T-010.
- Models, migrations, dormant RebaseEvent storage, ledger commands, allowance
  formulas, lifecycle/snapshot boundaries, Transactions period membership,
  Plan semantics, or new API fields.
- Phase 15 mobile UI, desktop visual redesign, new planning/forecasting
  concepts, deployment, or push.

## Verification

```bash
.venv/bin/python -m pytest tests/test_period_contract_removal_v21.py -q
.venv/bin/python -m pytest tests/test_period_api_v21.py tests/test_periods_v2.py tests/test_period_lifecycle_v2.py tests/test_period_start_replay_v2.py -q
.venv/bin/python -m pytest tests/test_transactions_phase12_v2.py tests/test_phase12_privacy_v2.py tests/test_operations_v2.py tests/test_operations_undo_v2.py -q
.venv/bin/python -m pytest tests/test_plan_v2.py tests/test_frontend_v2.py -q
.venv/bin/python -m pytest -q
node --check app/static/app.js
git diff --check
git status --short
```

All DB-backed tests use isolated in-memory fixtures. Any migration/manual DB
command must set an explicit scratch `DATABASE_URL`; `finapp.db` is never used.

## Readiness review

Append-only readiness passes against ACCOUNT_PERIODS-v2.1 §§3, 9–10, the
accepted T-008 transition matrix, ADR-0005, AGENTS, BACKLOG, and
REVIEW_PROTOCOL. Readiness must confirm this remains a mechanical S removal,
including the bounded existing-desktop consumer update, and does not absorb
T-010 permissions or schema/model work.

### Pass 1

- Reviewer task name/vendor: `/root/t009_readiness_review`, Codex same-vendor
  fallback; cross-vendor reviewer unavailable in this session.
- Reviewed task-file commit: `d0c37f2`.
- Findings (verbatim, P0–P3):

  > Read-only readiness review of commit `d0c37f26b447ed05b229114ce779f25cfb1af0e9`.
  >
  > P0: None.
  >
  > P1 — The final request contract is not fully frozen. `docs/tasks/T-009-remove-legacy-period-contracts.md:25-31` lists the three remaining fields and removed-field rejection, but does not explicitly preserve T-008’s required semantics for omitted create Start/policy, explicit-null rejection, PATCH requiring at least one business field, and unknown-policy rejection. “Final lifecycle shapes otherwise remain exactly as accepted in T-008” at `:36-42` describes responses/lifecycle, not these request rules. An implementation could therefore alter nullable/no-op behavior and still satisfy the written checklist. Add the exact final create/PATCH validation matrix and regression expectations from accepted T-008.
  >
  > P1 — The desktop compatibility result is not checkable enough and permits stale legacy presentation. `docs/tasks/T-009-remove-legacy-period-contracts.md:47-51` requires no Funding input and says the consumer reads `current_balance`, but it does not explicitly require removal/renaming of the existing `Remaining` and `Planned` cards, DOM identifiers, status copy, and Funding copy, nor freeze status-aware history values. That could leave legacy period concepts visibly exposed while technically no longer reading their JSON members, contradicting the goal at `:18-21` and ACCOUNT_PERIODS §3/§10. Define the mechanical result exactly: remove Funding control/help/status copy and the period Planned card; present current balance under non-legacy copy/identifier; render current as opening/current, ended as opening with no invented close value, and closed as opening/closing; preserve unrelated Plan UI.
  >
  > P2 — The “exhaustive removed-input matrix” is not actually enumerated. `docs/tasks/T-009-remove-legacy-period-contracts.md:28-31,55-58` says “including” null, malformed text, arrays, and objects, leaving reviewers and implementers to choose what exhaustive means. Freeze representative JSON-type cases for each newly forbidden period member—null, boolean, number, valid-looking string, malformed/empty string, array, and object—alone and combined with a valid business field, with create row absence or unchanged PATCH period/ledger state.
  >
  > P2 — OpenAPI verification does not explicitly cover the removed period confirmation member or protect same-named concepts outside the period contract. `docs/tasks/T-009-remove-legacy-period-contracts.md:32-35,55-59` names only `funding_amount`, `remaining`, and `planned` for OpenAPI removal, while the task also removes `confirm_ended_period` from `AccountPeriodPatch`; globally, transaction schemas must retain `confirm_ended_period` and Plan must retain `planned_amount`. Require exact AccountPeriodCreate/AccountPeriodPatch property sets and exact current/ended/closed response property sets in OpenAPI, while asserting unrelated transaction-confirmation and Plan components remain unchanged.
  >
  > P3: None.
  >
  > Dependencies and boundaries are otherwise coherent: T-008 is accepted, T-009 remains an S-sized mechanical producer/consumer removal, dormant RebaseEvent storage and revision `0002_period_snapshot_model` stay untouched, Plan semantics remain separate, and T-010 permissions plus Phase 15 design remain out of scope. Touches and verification commands are appropriately bounded.
  >
  > `git diff --check d0c37f2^ d0c37f2` passed. No tests were needed for this documentation-only review. No files were edited, no branch was switched, and HEAD remained `d0c37f2` on `finapp-v2-develop`.
  >
  > Verdict: **NOT READY**.
- Resolution: froze the complete accepted create/PATCH validation matrix,
  exact representative JSON values and mutation assertions, exact period and
  preserved non-period OpenAPI components, and exact mechanical desktop copy,
  DOM, history, and request result.
- Verdict: not ready; fresh readiness re-review required.

### Pass 2

- Reviewer task name/vendor: `/root/t009_readiness_review`, Codex same-vendor
  fallback; cross-vendor reviewer unavailable in this session.
- Reviewed task-file commit: `6c8d9cf`.
- Findings (verbatim, P0–P3):

  > Read-only readiness re-review of commit `6c8d9cf`.
  >
  > P0: None.
  >
  > P1: None.
  >
  > P2: None.
  >
  > P3: None.
  >
  > All prior findings are fully closed:
  >
  > - Final create/PATCH schemas and validation semantics are exact: omitted create Start/policy defaults, explicit-null/unknown/future/reversed/missing validation, PATCH at-least-one rule, and accepted lifecycle/replay behavior are frozen at `docs/tasks/T-009-remove-legacy-period-contracts.md:25-33`.
  > - The newly forbidden inputs have an exact representative JSON matrix—null, boolean, number, valid-looking string, empty/malformed strings, array, and object—alone and combined, with create and PATCH mutation-neutral assertions at `:34-41`.
  > - Effective OpenAPI property sets are exact for create, patch, current, ended, and closed; period confirmation is absent while transaction `confirm_ended_period` and Plan `planned_amount` remain protected at `:42-54`.
  > - The desktop change is mechanical and checkable: Funding control/copy/selector and period Planned card are removed, Remaining becomes Current balance backed by `current_balance`, period requests send only Start/end without period confirmation, lifecycle-aware history facts are exact, and unrelated Plan UI remains intact at `:66-74`.
  > - Exact response omission, Decimal presentation, one-cutoff behavior, current/null lookup, Plan separation, and dormant Rebase/migration invariants remain preserved at `:55-65,75-84`.
  >
  > The task remains a coherent S-sized producer/consumer contract removal. It does not absorb T-010 permission changes, model or migration work, dormant RebaseEvent removal, Plan semantics, Transactions membership, Phase 15 design, deployment, or push.
  >
  > `git diff --check 6c8d9cf^ 6c8d9cf` passed. No tests were needed for this documentation-only re-review. No files were edited, no branch was switched, and HEAD remained `6c8d9cf` on `finapp-v2-develop`.
  >
  > Verdict: **READY**.
- Resolution: all P0–P2 findings are closed; no further changes required.
- Verdict: ready.

## Review

Append-only implementation review passes. A different read-only agent returns
the review; the implementer records it verbatim following
[`../REVIEW_PROTOCOL-v2.md`](../../REVIEW_PROTOCOL-v2.md).

### Pass 1

- Reviewer task name/vendor: `/root/t009_implementation_review`, Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed base/head or working-tree manifest: base/HEAD `8c36f24`; all 13
  tracked modifications and untracked
  `tests/test_period_contract_removal_v21.py`.
- Findings (verbatim, P0–P3):

  > Read-only implementation review of working tree at `8c36f24414860a18c07d3c74a528b9a9e93433d2`, including all 13 tracked modifications and untracked `tests/test_period_contract_removal_v21.py`.
  >
  > P0: None.
  >
  > P1: None.
  >
  > P2: None.
  >
  > P3 — Legacy test terminology remains in the shared period helper and two assertions.
  >
  > - `tests/test_periods_v2.py:22` still accepts an unused `funding` argument, and 72 test call sites continue passing funding-looking values. This no longer affects requests, but makes fixtures appear to exercise a removed contract.
  > - `tests/test_periods_v2.py:772,783` use `.get("remaining") is None`; that expression accepts both the intended absent key and the removed legacy `remaining: null` shape. Exact omission is independently covered by the new removal suite, so this is a clarity/maintainability issue rather than a meaningful coverage gap. Prefer `"remaining" not in payload`.
  >
  > All required runtime behavior is otherwise coherent:
  >
  > - `app/schemas.py:198-248` has exact create/PATCH and lifecycle response fields with `extra="forbid"`; transaction confirmation and Plan `planned_amount` schemas remain intact.
  > - `app/periods.py:450-505` emits only opening/current/closing lifecycle facts and retains ledger-derived Decimal quantization. No Plan/Rebase imports or queries were introduced.
  > - `app/static/app.js:547-625,676-693` and `app/static/index.html:126-130,246-257` remove Funding/Remaining/period-Planned consumption, submit only Start/end, and render current/ended/closed history correctly.
  > - The forbidden-input matrix is complete and mutation-neutral; OpenAPI and all period routes receive exact-key assertions.
  > - No model, migration, Alembic, or dormant `RebaseEvent` storage change is present.
  >
  > Reviewer checks:
  >
  > - Full suite with UTF-8 mode: `224 passed, 246 warnings in 48.41s`.
  > - The initial run without `PYTHONUTF8=1` produced three pre-existing Windows locale decoding failures; this was environmental, not a T-009 behavior failure.
  > - `git diff --check`: passed.
  > - Existing reported targeted suites, JS syntax check, and full-suite result are consistent with the inspected manifest.
  >
  > Verdict: **APPROVED with one non-blocking P3 finding; no P0–P2 findings.**
- Resolution: removed the obsolete helper funding parameter and all 71
  funding-looking call arguments, and strengthened both ended-response checks
  to require exact key omission. Fresh limited re-review follows.
- Reviewer checks: full suite `224 passed`; `git diff --check` passed.
- Verdict: approved with one P3; P3 resolved and re-reviewed below.

### Pass 2 — P3 resolution

- Reviewer task name/vendor: `/root/t009_p3_rereview`, Codex same-vendor
  fallback; cross-vendor reviewer unavailable in this session.
- Reviewed base/head or working-tree manifest: limited post-Pass-1 helper,
  call-site, and exact-assertion diff over base/HEAD `8c36f24`.
- Findings (verbatim, P0–P3):

  > Read-only limited re-review of the post-P3 cleanup.
  >
  > P0: None.
  > P1: None.
  > P2: None.
  > P3: None.
  >
  > Verified:
  >
  > - `create_period(client, account_id, start=None, end=None)` no longer accepts or submits funding.
  > - AST comparison matched all 71 call sites against `HEAD`: each change is exactly the removal of the former funding argument; all original start/end expressions and keywords remain unchanged.
  > - Current arities are `{2: 21, 4: 50}` with only `start`/`end` keywords. No legacy funding-looking argument remains.
  > - The two post-mutation ended-response checks now require `"remaining"` to be absent, strengthening rather than weakening coverage.
  > - Dedicated forbidden-input matrix coverage remains in `test_period_contract_removal_v21.py`.
  > - All 12 modified Python files parse successfully.
  > - Focused removal/period suites: `93 passed in 25.57s`.
  > - `git diff --check`: passed.
  > - Supplied post-cleanup full gate: `224 passed`; Node syntax passed.
  > - No files edited, no branch switched, no commits created.
  >
  > Verdict: **APPROVED — prior P3 is fully resolved; no P0–P3 findings.**
- Resolution: no further changes required; all findings are closed.
- Reviewer checks: focused `93 passed`; full suite `224 passed`; Node syntax
  and diff-check passed.
- Verdict: approved; no P0–P3 findings.

## Session log

Append-only. Every session that touches this task adds one entry before it
ends. Date · agent · what landed · what is left · open questions.

- 2026-08-09 Codex: specified the bounded final removal immediately after
  local T-008 acceptance. Readiness, owner promotion, exact branch claim,
  implementation, review, and acceptance remain; no open question.
- 2026-08-09 Codex: readiness Pass 1 returned two P1 and two P2 findings. The
  final request matrix, JSON-type rejection matrix, exact OpenAPI component
  sets, and mechanical desktop result are now frozen. Fresh readiness
  re-review remains; no open question.
- 2026-08-09 Codex: readiness Pass 2 approved T-009 with no P0–P3 findings.
  Owner promotion, exact branch claim, implementation, and review remain; no
  open question.
- 2026-08-09 repository owner: promoted T-009 from backlog to todo after READY
  evidence at `6c8d9cf`. Exact task-branch claim is next; no open question.
- 2026-08-09 Codex: atomically claimed exact branch
  `task/T-009-remove-legacy-period-contracts` from promotion HEAD
  `79fb477fa42397b0d4fa4ffe2cdf6ec52595d185`. No implementation code was
  started. Next session should read this task and implement the one mechanical
  producer/consumer removal block, then run the listed gates and obtain a
  fresh read-only implementation review; no open question.
- 2026-08-11 Codex: removed all transitional period request/response aliases,
  synchronized the existing desktop consumer, and added the exact forbidden
  input/OpenAPI/route/UI regression matrix. Independent Pass 1 found one P3
  test-terminology issue; it was fully resolved and Pass 2 approved with no
  P0–P3 findings. Focused suites passed `51`, `42`, `22`, and `13` tests;
  final full suite passed `224`, Node syntax and diff-check passed. Task is
  ready for owner acceptance; no open question.
- 2026-08-11 repository owner: accepted T-009 by fast-forwarding verified
  commit `cb5a853` into local `finapp-v2-develop` after both implementation
  reviews closed all P0–P3 findings and the final `224 passed` gate. T-010 is
  next for specification/readiness; no open question.
