---
id: T-008
title: Synchronize the period API and lifecycle response surface
status: in-progress
size: M
spec: specs/ACCOUNT_PERIODS-v2.1.md §6–§9; design/MOBILE-BACKEND-GAP-AUDIT.md period API rows
blocked-by: [T-004, T-005, T-006, T-007]
branch: task/T-008-period-api-lifecycle-surface
base-commit: 16cb6b59b337b65f6551a67337a8eba76f982c09
implementer: Codex
readiness-reviewed-by: /root/t008_readiness_rereview (Codex same-vendor fallback)
readiness-reviewed-commit: c6a1b8f
readiness-verdict: ready
---

## Goal

The owner-facing period API exposes the accepted current/history lifecycle,
live ledger balance, and both exact allowance policies through the existing
`/api/v1` routes, while leaving only the bounded legacy-field removal to T-009.

## Acceptance

- [ ] `AccountPeriodCreate` accepts required `end_date`, optional
      `start_date`, and optional `rollover_policy`; omitted Start resolves to
      the route's captured workspace-local today and omitted policy resolves to
      `redistribute_remaining_days`. Explicit null, future Start, invalid date
      order, and unknown/null policy return deterministic `422` without a row.
- [ ] Create no longer requires `funding_amount`; `snapshot_at` and exact
      `opening_balance` remain server-derived by the accepted T-004/T-007
      transaction. During T-008 only, optional non-null Decimal
      `funding_amount` parses and is ignored; explicit null/invalid Decimal is
      `422`. It cannot affect storage or response values. T-009 deletes that
      schema member, making every supplied `funding_amount` an extra-field
      `422` without changing T-008 domain behavior.
- [ ] Explicit create policy `carry_next_day` or
      `redistribute_remaining_days` persists exactly; omission persists
      redistribution. Existing atomic current-period, predecessor,
      chronological-boundary, and Decimal snapshot guards remain unchanged.
- [ ] PATCH accepts optional `start_date`, `end_date`, and `rollover_policy`,
      requires at least one of those three business fields, rejects null or an
      unknown policy, and preserves T-007 atomic Start replay and lifecycle
      rules. Transitional PATCH `funding_amount` always returns `422` detail
      `Funding amount is not editable`, alone or combined. Transitional
      `confirm_ended_period` is ignored when a valid business field exists,
      does not bypass lifecycle rules, and alone returns `422` for no business
      field. T-009 deletes both schema members.
- [ ] Create and PATCH use `extra="forbid"`. Except for the two frozen
      transitional members above, client-supplied `snapshot_at`,
      `opening_balance`, `closing_balance`, `current_balance`,
      `account_balance`, `remaining`, `planned`, `account_id`, `asset_id`,
      `created_by_user_id`, `status`, `created_at`, or `closed_at` returns
      deterministic `422` and persists no period/ledger mutation. Focused tests
      cover every forbidden key on create and PATCH.
- [ ] The response union has exactly three status shapes. Common fields use
      these existing names/types: `id: int`, `account_id: int`,
      `asset: AssetOut`, `created_by_user_id: int`, `start_date: date`,
      `end_date: date`, `snapshot_at: datetime`, `opening_balance: Decimal`,
      `rollover_policy`, `status`, `created_at: datetime`, `closed_at`, and
      `closing_balance`.
- [ ] `current` has `status="current"`, `closed_at=null`,
      `closing_balance=null`, and additionally includes non-null
      `current_balance` and `available_today`. `ended` has `status="ended"`
      with both close fields null and omits the live keys entirely. `closed`
      has `status="closed"`, non-null `closed_at`/`closing_balance`, and omits
      the live keys entirely. Omission, not JSON null, is required for history
      live keys. Create/detail/list/PATCH/close use this union, including an
      immediately-ended create/PATCH response. Current lookup uses only
      `current|null` and returns null after that transition.
- [ ] T-008's exact transitional response matrix is mechanical to remove in
      T-009: all three status shapes include `funding_amount`, `remaining`, and
      `planned`; `funding_amount` equals presented `opening_balance`;
      `remaining` equals presented `current_balance` for current,
      `closing_balance` for closed, and JSON null for ended; `planned` is
      presented zero and performs no Plan query. None drives any new field.
      T-009 deletes exactly these keys/schema assignments and the dormant
      compatibility input members.
- [ ] `GET /api/v1/accounts/{account_id}/periods/current` returns the one
      current object or HTTP `200` JSON `null`. It performs no lifecycle write,
      ignores ended/closed rows, preserves owner 404 redaction, and never
      fabricates zero/N/A values.
- [ ] `GET /accounts/{account_id}/periods?scope=history`, account-period detail,
      PATCH, close, and create return the lifecycle-appropriate schema.
      Existing `scope=all|current` behavior may remain as a desktop-compatible
      superset, but every item uses the same status-aware response rules.
- [ ] Every route captures one naive-UTC reference `T` after authorization (and
      after writer reservation for mutations), derives workspace-local today
      from that exact T, and reuses T for status selection, all list items,
      current lookup, account balance, movement cutoff, effective-day clamping,
      and response serialization. Close uses the same T as `closed_at`. No
      single response can mix pre/post-midnight lifecycle or ledger cutoffs.
- [ ] Current allowance integration calls the accepted pure
      `compute_allowance` dispatcher with `calculation_opening_balance` from
      T-003, the stored policy, asset quantum, and signed posted window effects
      exactly once. `app/budget.py` remains unchanged and free of DB/framework
      imports.
- [ ] Effective financial days clamp every window effect before dispatch:
      dates before `start_date` map to Start, dates after the current replay day
      map to that replay day, and in-range dates remain unchanged. Boundary
      equality stays in opening only; voided/non-window legs do not enter
      effects; reconciliation delta enters only through the calculation
      opening pool.
- [ ] Internal `opening_balance`, `current_balance`, `closing_balance`, window
      net, reconciliation delta, and AllowanceResult values remain exact
      Decimal. Before response quantization,
      `AllowanceResult.current_balance == PeriodBalanceInputs.current_balance`
      exactly. At the API boundary, all returned money (new and transitional)
      uses asset precision and `ROUND_HALF_UP`; 18-decimal assets lose no
      supported precision.
- [ ] The dated Asia/Ho_Chi_Minh VND fixture returns exact
      `opening_balance=6000000`, `current_balance=5980000`, redistribution base
      `5672269/15`, and API `available_today=685882` at VND precision, without
      Planned input or hard-coded response constants.
- [ ] Both policies cover current-day income/outflow exactly once, pre-period
      correction reconciliation, negative balances, one-day periods,
      timezone/boundary clamping, and 18-place Decimal precision. Dispatch
      results are derived on read and persist no daily aggregate.
- [ ] T-008 stops importing/querying `RebaseEvent` and never passes ad-hoc
      rebase days to the new dispatcher. The preserved table/relationships and
      T-002 migration identity remain dormant and unchanged. T-009 removes only
      any remaining public/query compatibility contract; no T-009 model or
      migration work is implied.
- [ ] Spending above `available_today`, including repeated overspend, remains
      accepted under normal Operations permissions; account/current balance
      changes normally and the recalculated allowance may be negative. No
      period value is used as an authorization limit.
- [ ] `GET /api/v1/transactions?period_id=...` uses the same canonical
      timestamp window as the period: account leg, posted status,
      `created_at > snapshot_at`, and lifecycle cutoff (`<= T` current,
      `<= closed_at` closed, `< period_end_boundary` ended). It does not filter
      membership by `Transaction.local_date`; back/future financial dates are
      included and map to the same effective clamped day used by allowance.
      Snapshot/cutoff equality and void exclusion match the period window.
- [ ] Existing privacy is regression-tested for both a shared user and a
      foreign owner: create/list/current/detail/PATCH/close and
      `transactions?period_id` return owner-private `404` without revealing
      existence. T-010 may harden permission semantics but T-008 cannot weaken
      current redaction.
- [ ] Focused tests cover create defaults/explicit policies/validation and
      ignored transitional funding; policy-only and combined PATCH with
      mutation-neutral ledger assertions; current object/null; ended/closed
      response separation; history/detail/create/patch/close schemas; VND
      fixture; signed/clamped/reconciled effects; both policies and Decimal
      edges; overspend; coherent-midnight cutoff; exact forbidden-input matrix;
      canonical transaction-filter membership; enumerated 404 isolation; and
      legacy regression boundaries.

## Touches

- `app/schemas.py`
- `app/periods.py`
- `app/transactions.py`
- `tests/test_period_api_v21.py`
- `tests/test_transactions_phase12_v2.py`
- existing period tests only where the additive/status-aware API supersedes an
  assertion
- `docs/tasks/T-008-period-api-lifecycle-surface.md`
- `docs/BACKLOG.md` and `docs/PROGRESS.md` for task lifecycle state only

## Out of scope

- Final rejection/removal of `funding_amount`, `remaining`, `planned`, and the
  legacy confirmation input — T-009. Dormant RebaseEvent storage and migration
  identity remain preserved; no model/schema migration is assigned to T-009.
- New permission semantics or shared-role redaction changes — T-010; existing
  owner-private behavior must not regress.
- Models, migrations, ledger command semantics, Plan behavior, UI, Phase 15,
  or changes to accepted T-004/T-007 lifecycle/snapshot rules.
- Changes to pure formulas in `app/budget.py`; T-005/T-006 are consumed as-is.

## Verification

```bash
.venv/bin/python -m pytest tests/test_period_api_v21.py -q
.venv/bin/python -m pytest tests/test_budget_carry_v2.py tests/test_budget_redistribute_v2.py -q
.venv/bin/python -m pytest tests/test_periods_v2.py tests/test_period_lifecycle_v2.py tests/test_period_start_replay_v2.py -q
.venv/bin/python -m pytest tests/test_transactions_phase12_v2.py -q
.venv/bin/python -m pytest -q
node --check app/static/app.js
git diff --check
git status --short
```

All DB-backed tests use isolated in-memory or `tmp_path` file-backed fixtures.
Any migration/manual database command must set an explicit scratch
`DATABASE_URL`; `finapp.db` is never used.

## Readiness review

Append-only readiness passes against `specs/ACCOUNT_PERIODS-v2.1.md`
§6–§9 and acceptance scenarios 3, 9–15, 19–20, 22, 25; the audit rows for
source of money, allowance fixture, rollover selection, and informational
Available today; ADR-0005; accepted T-003–T-007; AGENTS; BACKLOG; and
REVIEW_PROTOCOL. Scenario 23 and final §10 separation remain assigned to
T-009, and scenario 24 permission hardening remains assigned to T-010.

### Pass 1

- Reviewer task name/vendor: `/root/t008_readiness_review`, Codex same-vendor
  fallback; cross-vendor reviewer unavailable in this session.
- Reviewed task-file commit: `5fff4d8`.
- Findings (verbatim, P0–P3):

  > Read-only readiness review of commit `5fff4d8786b71c1599daccfc83c3cb36572475a5`.
  >
  > P0: None.
  >
  > P1 — The T-008/T-009 transition is not yet a deterministic contract. T-008 deliberately permits ignored create `funding_amount` (`docs/tasks/T-008-period-api-lifecycle-surface.md:29-34`) and may retain `funding_amount`, `remaining`, and `planned` response members (`:54-58`), despite the final §9 contract rejecting/removing them (`docs/specs/ACCOUNT_PERIODS-v2.1.md:402-404,485-489`). A staged departure can be coherent until T-009, but “may remain” does not say which current/ended/closed shapes contain each field or what each value means. It also leaves PATCH behavior for legacy `funding_amount`/`confirm_ended_period`, including when combined with a valid business field, undefined (`task:39-43,109-111`). Freeze the transitional request and response matrix explicitly so T-009 is a mechanical bounded removal: exact accepted/ignored/rejected legacy inputs, exact shapes carrying legacy outputs, and exact derivation of every retained value; no legacy value may drive the new fields.
  >
  > P1 — The T-009 handoff assigns work that is not bounded by the backlog row. T-008 defers “RebaseEvent contract/storage” to T-009 (`task:109-111`), while BACKLOG defines T-009 only as S removal of `funding_amount`/`remaining`/`planned` contracts (`docs/BACKLOG.md:40`) and §7.3 only removes the public ad-hoc rebase concept, not necessarily the preserved table (`spec:356-358`). T-002 intentionally preserved dependent rebase identities. State that T-008 stops consuming RebaseEvent and T-009 removes only its public/query contract while dormant storage remains, or separately authorize a model/migration task; otherwise the claimed S split is not coherent.
  >
  > P1 — The lifecycle response schema is not exact enough to implement or review. “asset” and “creator” (`task:44-48`) do not choose the existing names/types (`asset` versus `asset_id`, `created_by_user_id`), and the task does not define three concrete status shapes. Require an exact field matrix: `current` with non-null live fields and null close pair, `ended` with both close fields null and live keys omitted, and `closed` with both close fields non-null and live keys omitted; say whether omission, not JSON null, is required; define the response union used by create/detail/list/PATCH/close/current; and place every transitional field explicitly. This is especially necessary because create/PATCH may return an immediately ended shape under accepted T-007.
  >
  > P1 — Required forbidden-input validation is missing. §8 requires PATCH to accept only Start/end/policy and reject snapshots, balances, ownership, and removed fields (`spec:369-375`); §9 likewise rejects client snapshot/balance/account/planned values on create (`spec:402-404`). T-008 acceptance only names null/date/policy validation and the temporary create-funding exception (`task:24-43`). Enumerate deterministic `422` and no-row/no-mutation coverage for every forbidden create/PATCH field, with only the explicitly frozen transitional exceptions from the first finding.
  >
  > P1 — Acceptance scenario 13 cannot be completed within Touches/verification. The canonical rule requires the Transactions period filter to expose the same timestamp-window movement set as allowance, regardless of out-of-range financial dates (`spec:172-180,544-545`). Current code still filters by `TransactionLeg.created_at > period.created_at` and `Transaction.local_date` inside Start/end (`app/transactions.py:486-493`), while T-008 claims clamping/scenario 13 (`task:72-77,136-139`) but excludes `app/transactions.py` and its regression module (`task:97-105,120-127`). T-007 explicitly deferred public membership to T-008. Add the transaction filter and `tests/test_transactions_phase12_v2.py` to scope/gates, proving snapshot/reference/end cutoffs, equality, void exclusion, and backdated/future-dated financial-date inclusion with the same effective-day clamping.
  >
  > P1 — API quantization contradicts the accepted T-003 boundary. T-008 calls `current_balance` “exact” and quantizes only `available_today` (`task:49-50`), but §2 requires API display money at asset precision with `ROUND_HALF_UP` (`spec:33-38`), and T-003 records exact Accounts equality before API quantization (`docs/tasks/T-003-ledger-derived-balance.md:25-28`). Define exact internal Decimal invariants separately from response-boundary quantization for opening/current/closing and transitional money fields, and require `AllowanceResult.current_balance == PeriodBalanceInputs.current_balance` before presentation rounding.
  >
  > P2 — One coherent read cutoff/local day is not required. The current serializer obtains workspace today and `reference_time` from separate clocks, and list serializes rows independently (`app/periods.py:405-410,586`), so a local-midnight read can select a current row and serialize it as ended, or mix statuses/cutoffs in one response. The task requires timezone boundaries but does not state the invariant (`task:59-77,82-85`). Require one captured UTC T per route response, derive workspace-local today/effective replay day from T, and reuse T for status selection, every item, account balance, window effects, and clamping.
  >
  > P2 — Privacy regression verification is too vague for an API-surface rewrite. “route 404 isolation” (`task:90-95`) should enumerate existing shared-user and foreign-owner 404 redaction across create/list/current/detail/PATCH/close and `transactions?period_id`; T-010 may add permission semantics later, but T-008 must prove it did not weaken the currently owner-private guards.
  >
  > P2 — T-008 contains at least three written logical blocks (allowance/effect integration, response/request schemas and routes, and Transactions-filter membership) but its review section requests one generic implementation pass (`task:143-147`). Record the block boundaries so AGENTS/REVIEW_PROTOCOL can enforce targeted tests and a fresh read-only reviewer after each.
  >
  > Verdict: **NOT READY**. Dependencies T-004–T-007 are accepted, no blocker exists, the owner/private and T-010 boundary is otherwise reasonable, and the staged T-008/T-009 approach can remain M→S after the transition and RebaseEvent scope are made exact. `git diff --check 5fff4d8^ 5fff4d8` passed. No tests were needed for this documentation-only review. No files were edited and no branch was switched; HEAD remained `5fff4d8` on `finapp-v2-develop`.
- Resolution: all six P1 and three P2 findings are addressed by an exact
  transitional request/response matrix, dormant Rebase storage boundary,
  concrete three-shape response union, exhaustive forbidden inputs,
  canonical Transactions-filter scope, exact-versus-presentation invariants,
  one route cutoff T, enumerated privacy gates, and three sequential reviewed
  implementation blocks.
- Verdict: not ready; fresh readiness re-review required.

### Pass 2

- Reviewer task name/vendor: `/root/t008_readiness_rereview`, Codex same-vendor
  fallback; cross-vendor reviewer unavailable in this session.
- Reviewed task-file commit: `c6a1b8f`.
- Findings (verbatim, P0–P3):

  > Read-only readiness re-review of commit `c6a1b8fb7336dbbb333cd7fdb816ca9f29a6555e`.
  >
  > P0: None.
  >
  > P1: None.
  >
  > P2: None.
  >
  > P3 — Minor wording ambiguity at `docs/tasks/T-008-period-api-lifecycle-surface.md:67-68`: “including immediately-ended create/PATCH responses” grammatically follows the `current|null` clause, although lines 77–80 correctly require current lookup to ignore ended rows. Intended behavior remains recoverable: create/PATCH may return `ended`; subsequent current lookup returns JSON `null`. Rephrasing would improve clarity but does not block readiness.
  >
  > All Pass-1 findings are closed:
  >
  > - The T-008/T-009 request and output transition is deterministic, including create funding behavior, PATCH funding/confirmation behavior, exact three-shape legacy outputs, derivations, and mechanical T-009 removal (`:24-76`).
  > - T-008 stops RebaseEvent consumption while preserving dormant storage/migration identity; T-009 has no model or migration work (`:117-121,161-163`).
  > - The current/ended/closed union, exact common names/types, live-field omission, close-pair nullability, and route usage are defined (`:55-80`).
  > - Create/PATCH use `extra="forbid"` with an exhaustive named forbidden-input regression matrix and mutation-neutral `422` behavior (`:48-54`).
  > - Transactions period-filter parity is in Touches, acceptance, focused coverage, and verification, with exact snapshot/lifecycle boundaries and financial-date independence (`:126-145,151-155,176`).
  > - Internal exact Decimal values and pre-quantization Allowance equality are separated from asset-precision `ROUND_HALF_UP` API presentation (`:102-112`).
  > - One route reference `T` governs lifecycle, ledger cutoff, effective day, list serialization, and close timestamp (`:85-90`).
  > - Shared-user and foreign-owner `404` regression coverage is enumerated for every period route and `transactions?period_id` (`:133-137`).
  > - Three sequential logical blocks each require targeted tests and a fresh independent read-only review (`:233-252` in the current task file).
  >
  > The T-009 final legacy-contract removal and T-010 permission-hardening boundaries are coherent. Dependencies T-004–T-007 are accepted. The three cohesive, sequential blocks remain feasible at the upper end of size M. Verification commands are exact; existing named test modules exist, and the new focused T-008 module is explicitly scoped.
  >
  > `git diff --check c6a1b8f^ c6a1b8f` passed. No tests were needed for this documentation-only review.
  >
  > Verdict: **READY**.
  >
  > No files were edited and no branch was switched. HEAD remained `c6a1b8f` on `finapp-v2-develop`.
- Resolution: all P0–P2 are closed; the non-blocking P3 sentence was rephrased
  so ended create/PATCH responses and subsequent current-null lookup are
  grammatically separate.
- Verdict: ready.

## Implementation blocks and review gates

Implement sequentially on the one T-008 branch; after each block run its
targeted commands, pause, and obtain a fresh independent read-only review with
verbatim evidence before continuing.

1. **Canonical allowance projection** — one route reference T, signed effect
   clamping, reconciliation, exact/presentation equality, both policies,
   VND/Decimal/overspend, and removal of Plan/Rebase consumption from new
   allowance. Target: new focused allowance/API module plus T-005/T-006 tests.
2. **Period request/response/routes** — exact transitional request/output
   matrix, three response shapes, create/PATCH policy behavior, current|null,
   lifecycle routes, coherent list cutoff, and enumerated period-route privacy.
   Target: full new API module plus existing period/lifecycle/start tests.
3. **Transactions period-filter parity** — canonical lifecycle timestamp
   membership, financial-date independence/clamping parity, equality/void
   boundaries, and shared/foreign 404. Target:
   `tests/test_transactions_phase12_v2.py` plus the focused API module.

## Review

Append-only implementation review passes. A different read-only agent returns
the review; the implementer records it verbatim following
[`../REVIEW_PROTOCOL-v2.md`](../REVIEW_PROTOCOL-v2.md).

### Block 1 — canonical allowance projection, Pass 1

- Reviewer task name/vendor: `/root/t008_allowance_review`, Codex same-vendor
  fallback; cross-vendor reviewer unavailable in this session.
- Reviewed base/head or working-tree manifest: base/HEAD `ed21e8d`; modified
  `app/periods.py`, directly inspected untracked
  `tests/test_period_api_v21.py`, and bounded legacy assertion update in
  `tests/test_periods_v2.py`.
- Findings (verbatim, P0–P3):

  > Read-only implementation review of T‑008 Block 1 at `ed21e8d`.
  >
  > P0: None.
  >
  > P1: None.
  >
  > P2: None.
  >
  > P3: None.
  >
  > Verdict: **APPROVED**.
  >
  > Evidence:
  >
  > - Canonical movement tuple is captured once in `PeriodBalanceInputs` and reused for `window_net`, reconciliation, clamping, and dispatch (`app/periods.py:371-393`, `419-437`).
  > - Effects retain signed values and clamp financial dates to Start/reference day (`app/periods.py:396-408`).
  > - Snapshot equality and void/non-window exclusions remain enforced by the canonical timestamp query (`app/periods.py:339-355`).
  > - Reconciliation enters only through `calculation_opening_balance`; exact allowance/current-balance equality is enforced before serialization (`app/periods.py:379-385`, `429-439`).
  > - Current API serialization now consumes `compute_allowance`; current Rebase rows are not queried (`app/periods.py:481-490`). Historical compatibility remains outside this block.
  > - Focused coverage verifies both policies, 18-decimal exactness, boundary correction reconciliation, signed clamping, VND `5672269 / 15 → 685882`, repeated permissive overspend, and dormant Rebase neutrality (`tests/test_period_api_v21.py:22-222`).
  > - `app/budget.py`, schemas, transaction filtering, and unrelated routes were unchanged.
  >
  > Checks:
  >
  > - `tests/test_period_api_v21.py`: `4 passed`
  > - carry + redistribution suites: `27 passed`
  > - period/lifecycle/start suites: `31 passed`
  > - `git diff --check`: passed
  >
  > No files were edited and no branch was switched. HEAD remained `ed21e8d` on `task/T-008-period-api-lifecycle-surface`.
- Resolution: none required.
- Reviewer checks: focused `4 passed`; pure policies `27 passed`; period
  regressions `31 passed`; diff-check passed.
- Verdict: approved; no P0–P3 findings.

### Block 2 — period request/response/routes, Pass 1

- Reviewer task name/vendor: `/root/t008_api_routes_review`, Codex same-vendor
  fallback; cross-vendor reviewer unavailable in this session.
- Reviewed base/head or working-tree manifest: base/HEAD `93e7297`; complete
  uncommitted manifest in `app/schemas.py`, `app/periods.py`,
  `tests/test_period_api_v21.py`, and bounded superseded assertions in
  `tests/test_periods_v2.py`, `tests/test_period_start_replay_v2.py`,
  `tests/test_operations_v2.py`, and `tests/test_operations_undo_v2.py`.
- Findings (verbatim, P0–P3):

  > Read-only implementation review of T-008 Block 2 at uncommitted manifest over `93e7297`.
  >
  > P0: None.
  >
  > P1 — Transitional PATCH `funding_amount` does not always return the frozen exact error contract. `AccountPeriodPatch.funding_amount` is validated as `DecimalAmount` before the handler, so a supplied invalid Decimal such as `"not-a-decimal"` returns Pydantic’s structured `decimal_parsing` response instead of HTTP `422` detail `Funding amount is not editable`. The task explicitly requires that detail for transitional PATCH `funding_amount` always, alone or combined. Accept the dormant value without Decimal pre-validation so the handler can reject every supplied value uniformly, and add invalid-value coverage alongside valid/null/combined cases.
  >
  > P2 — Required policy-request coverage is incomplete. The focused tests prove omitted-policy create, explicit `carry_next_day` create, and a redistribution PATCH combined with ignored `confirm_ended_period`, but they do not prove explicit `redistribute_remaining_days` create, a genuinely policy-only PATCH without the compatibility flag, or a combined multi-business-field PATCH containing policy with Start/end. The task explicitly requires create defaults/explicit policies plus policy-only and combined PATCH coverage. Add those cases with persistence, immediate response, and ledger/transaction/Rebase mutation-neutral assertions.
  >
  > P3: None.
  >
  > Verdict: CHANGES REQUIRED. The response unions and exact current/ended/closed key separation, `current|null` route, one captured naive UTC reference per route, close cutoff/timestamp reuse, Decimal presentation including 18 places, removal of Plan/Rebase consumption, lifecycle guards, owner-private 404 behavior, and Block 2 scope boundaries otherwise match the reviewed contract.
  >
  > Evidence:
  >
  > - `56 passed`:
  >   `tests/test_period_api_v21.py`, `tests/test_periods_v2.py`,
  >   `tests/test_period_lifecycle_v2.py`,
  >   `tests/test_period_start_replay_v2.py`,
  >   `tests/test_operations_v2.py`,
  >   `tests/test_operations_undo_v2.py`.
  > - `git diff --check` passed.
  > - Schema probe confirmed `"not-a-decimal"` fails before the route with `decimal_parsing`.
  > - No files edited, no branch switched, no commit created.
- Resolution: PATCH keeps the legacy member dormant as `object | None`, so
  every supplied JSON value reaches the one exact handler rejection while
  create retains Decimal validation. Focused coverage now includes invalid
  PATCH funding, explicit redistribution create, a policy-only PATCH, and a
  combined Start/end/policy PATCH with response, persistence, and
  transaction/leg/Rebase neutrality assertions.
- Verdict: changes required; fresh re-review completed below.

### Block 2 — period request/response/routes, Pass 2

- Reviewer task name/vendor: `/root/t008_api_routes_review`, Codex same-vendor
  fallback; cross-vendor reviewer unavailable in this session.
- Reviewed base/head or working-tree manifest: base/HEAD `93e7297`; complete
  corrected Block 2 working-tree manifest listed in Pass 1.
- Findings (verbatim, P0–P3):

  > Read-only re-review of T-008 Block 2 fixes over `93e7297`.
  >
  > P0: None.
  >
  > P1: None.
  >
  > P2: None.
  >
  > P3: None.
  >
  > Verdict: APPROVED.
  >
  > Both prior findings are closed:
  >
  > - `AccountPeriodCreate.funding_amount` remains `DecimalAmount | None`, and invalid create funding still fails Decimal validation with `decimal_parsing`.
  > - `AccountPeriodPatch.funding_amount` is now a dormant `object | None`; strings, mappings, arrays, null, and numbers preserve `model_fields_set` and reach the handler, which uniformly returns HTTP `422` detail `Funding amount is not editable`. Focused coverage includes invalid Decimal text, valid, null, and combined cases.
  > - Explicit redistribution create now checks immediate response, persisted policy, and unchanged transaction/leg/Rebase counts.
  > - A genuine policy-only PATCH checks immediate recalculated response, persistence, and unchanged financial state.
  > - Combined Start/end/policy PATCH checks immediate response, persisted fields/snapshot state, and unchanged transaction/leg/Rebase counts; ignored `confirm_ended_period` is also exercised.
  >
  > Evidence:
  >
  > - `tests/test_period_api_v21.py`: `11 passed`.
  > - Bounded lifecycle/period/operations regression set: `45 passed`.
  > - Combined reviewed total: `56 passed`.
  > - `git diff --check` passed.
  > - No files edited, no branch switched, no commit created.
- Resolution: all P0–P2 findings are closed; no further changes required.
- Reviewer checks: focused `11 passed`; bounded regressions `45 passed`;
  diff-check passed.
- Verdict: approved; no P0–P3 findings.

## Session log

Append-only. Every session that touches this task adds one entry before it
ends. Date · agent · what landed · what is left · open questions.

- 2026-08-09 Codex: drafted bounded T-008 API/lifecycle integration after
  local T-007 acceptance. The new contract is additive until T-009 removes the
  three legacy fields; permission changes remain T-010. Readiness, promotion,
  claim, implementation, and review remain; no open question.
- 2026-08-09 Codex: readiness Pass 1 returned six P1 and three P2 findings.
  The task now freezes the transition matrix and response union, stops Plan and
  Rebase consumption, adds canonical Transactions-filter parity, quantization,
  one-cutoff and privacy invariants, and splits implementation into three
  separately reviewed blocks. Fresh readiness re-review remains.
- 2026-08-09 Codex: readiness Pass 2 approved T-008 with no P0–P2 findings;
  its wording-only P3 was resolved. Readiness evidence is complete. Owner
  promotion, exact branch claim, and implementation remain; no open question.
- 2026-08-09 Codex: owner promoted T-008 at `16cb6b5`; exact branch
  `task/T-008-period-api-lifecycle-surface` was atomically claimed from that
  promotion HEAD and records the full base hash above. Block 1 allowance
  projection is next; no open question.
- 2026-08-09 Codex: Block 1 canonical allowance projection implemented and
  independently approved with no P0–P3 findings. Focused `4 passed`, pure
  policies `27 passed`, period regressions `31 passed`, and diff-check passed.
  Block 2 request/response/routes remains; no open question.
- 2026-08-09 Codex: Block 2 period request/response/routes implemented. Review
  Pass 1 found one P1 uniform legacy-funding rejection defect and one P2
  policy-coverage gap; both were fixed and Pass 2 approved with no P0–P3.
  Focused `11 passed`, bounded regressions `45 passed`, full suite
  `171 passed`, node syntax and diff-check passed. Block 3 Transactions-filter
  parity remains; no open question.
