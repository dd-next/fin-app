---
id: T-014F
title: Expose a stable financial-date feed for persisted transactions
status: done
size: M
spec: design/MOBILE-BACKEND-GAP-AUDIT.md feed ordering and adjustment/exchange rows
blocked-by: [T-001]
branch: task/T-014F-financial-date-transaction-feed
base-commit: a6ffca9a209147e857a2aa625ecf9f0f62a1fb3c
implementer: Codex
readiness-reviewed-by: /root/t014_split_final_review (Codex same-vendor fallback)
readiness-reviewed-commit: 5b47c9288b0a7dc9d65f270e8b4a8cd36275cc3b
readiness-verdict: ready
---

## Goal

The mobile adapter can page visible persisted ledger transactions in stable
financial-date order and render every domain transaction type without changing
the richer existing desktop transaction API.

## Acceptance

- [x] Add authenticated `GET /api/v1/transaction-feed` with query parameters
      `filter` (default `all`, exact enum `all|income|expense|transfer`),
      `cursor` (optional opaque versioned string), and `limit` (integer default
      `50`, inclusive `1..100`). Unknown/duplicate parameters, malformed or
      unsupported-version cursors, non-integer limits, and invalid filter
      values are `422` and perform no database write.
- [x] The response is exactly `{items, next_cursor}` with no extra properties.
      Every item in this task is a closed discriminated transaction projection:
      `kind="transaction"`, stable `key="transaction:<positive id>"`,
      `financial_date`, `mobile_type`, `transaction_type`, and the existing
      full `TransactionOut` under `transaction`. IDs and Decimal values are
      never copied into an alternative lossy representation.
- [x] Mapping is exact: domain `income|expense|transfer` keeps the same
      `mobile_type`; `exchange` maps to mobile `transfer` while retaining
      `transaction_type="exchange"` and both exact signed amount legs in the nested
      detail; `adjustment` maps to mobile `adjustment`, remains identifiable as
      a non-convertible balance correction, and retains its signed leg.
      Exchange and adjustment appear only under `filter=all`; the three named
      filters select only their matching domain transaction type.
- [x] Feed visibility and redaction exactly reuse the accepted transaction
      list/detail rules: primary-workspace rows, visible shared-account legs,
      and creator-owned unassigned rows are eligible; inaccessible legs stay
      redacted through `has_hidden_legs`; foreign/hidden detail IDs return the
      generic `404 Feed item not found`. The nested accepted `TransactionOut`
      preserves owner-visible `plan_occurrence_id` and its existing serializer
      lookup, while shared/redacted projections keep that value `null`. This
      task performs no Plan materialization and adds no Plan projection/detail
      field beyond that existing compatibility value; private period/rate state
      is neither queried nor exposed.
- [x] Persisted items order descending by the stable total key
      `(financial_date, sort_at, kind_rank, item_id)`, where
      `financial_date=Transaction.local_date`, `sort_at=occurred_at`,
      `kind_rank=1`, and `item_id=Transaction.id`. The opaque cursor encodes
      that complete last-item key plus version `1`; continuation applies a
      strict lexicographic `<` predicate. A fixed dataset produces no duplicate
      or omitted items across pages, including equal dates/timestamps.
- [x] A correction that changes `local_date` or `occurred_at` moves the row to
      its new financial position on a fresh read regardless of ID. Soft Delete
      keeps the row in the same financial position with nested status
      `deleted`; it never removes or re-dates history. Account/period filters on
      the existing `/api/v1/transactions` route retain their accepted snapshot
      and financial-date-independent membership semantics.
- [x] Add authenticated
      `GET /api/v1/transaction-feed/transaction/{transaction_id}` using the
      same closed transaction projection as the list. This is the common
      Transaction-details data route that T-014P extends with a `planned`
      discriminator; a positive integer ID is required and hidden/foreign IDs
      return `404 Feed item not found`.
- [x] OpenAPI freezes the list/detail query/path bounds, exact item/page
      property and required sets, `additionalProperties: false`, discriminator
      constant, enum mappings, cursor string/null shapes, existing nested
      `TransactionOut` reference, and documented `404`/`422` errors.
- [x] Existing `GET /api/v1/transactions` filters, integer ID cursor,
      `TransactionPageOut`, detail/correction/Delete routes, explicit
      adjustment/exchange identity, and desktop behavior remain byte-shape
      compatible and regression protected. No existing route is repurposed.
- [x] Focused feed ordering/mapping/pagination/privacy/OpenAPI tests, existing
      transaction/period tests, full pytest, Node syntax, and diff/status gates
      pass on isolated fixtures.

## Touches

- `app/transaction_feed.py`
- `app/schemas.py`
- `app/main.py` only to register the new router
- `tests/test_transaction_feed_v21.py`
- existing transaction tests only for direct compatibility assertions
- `docs/tasks/T-014F-financial-date-transaction-feed.md`
- `docs/BACKLOG.md` and `docs/PROGRESS.md` for lifecycle only

## Out of scope

- Plan occurrence materialization/projection/detail/actions (T-014P), fake or
  posted planned movements, transaction type conversion (T-015), category or
  account lifecycle, mobile UI, migrations, or `finapp.db` mutation.
- Changing the existing `/transactions` cursor/filter/response contract,
  ledger math, captured rates, period membership, or Undo behavior.

## Verification

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_transaction_feed_v21.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_ledger_v2.py tests/test_transactions_phase12_v2.py tests/test_periods_v2.py -q
.\.venv\Scripts\python.exe -m pytest -q
node --check app/static/app.js
git diff --check
git status --short
```

All database-backed tests use isolated fixtures and never open, replace, or
delete `finapp.db`.

## Readiness review

Append-only readiness passes against the audit, frozen Transactions screens/tap
map/data model, accepted transaction/period/privacy behavior, AGENTS, BUILD_PLAN,
and REVIEW_PROTOCOL.

### Split-contract review Pass 1

- Reviewer task name/vendor: `/root/t014_split_review`, fresh Codex same-vendor
  fallback; cross-vendor reviewer unavailable in this session.
- Reviewed manifest: integration HEAD `36f3366` plus modified BACKLOG and both
  untracked T-014 split task files.
- Findings (verbatim, P0–P3): the complete combined findings block is recorded
  under [`T-014P` Split-contract review Pass 1](T-014P-planned-feed-projection.md#split-contract-review-pass-1).
  T-014F's P1 was the impossible promise that existing `TransactionOut`
  contains captured exchange rates and preserves them after Delete.
- Resolution: the frozen exchange projection now promises the audit-required
  exact two-amount detail through its signed legs only; captured rates remain
  outside this feed contract.
- Verdict: not ready; corrected and submitted for fresh re-review.

### Split-contract review Pass 2

- Reviewer task name/vendor: `/root/t014_split_rereview`, fresh Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed manifest: integration HEAD `36f3366` plus modified BACKLOG and both
  untracked corrected task files.
- Findings (verbatim, P0–P3): the complete block is recorded under
  [`T-014P` Split-contract review Pass 2](T-014P-planned-feed-projection.md#split-contract-review-pass-2).
  The sole P1 was the contradiction between nesting accepted `TransactionOut`
  with its owner-visible `plan_occurrence_id` and forbidding its Plan lookup.
- Resolution: preserve accepted owner-visible `plan_occurrence_id`, retain
  shared/redacted `null`, and prohibit only materialization/new Plan
  projections or detail fields in T-014F.
- Verdict: not ready; corrected and submitted for fresh re-review.

### Split-contract review Pass 3

- Reviewer task name/vendor: `/root/t014_split_final_review`, fresh Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed manifest: integration HEAD `36f3366` plus modified BACKLOG and both
  untracked fully corrected task files.
- Findings (verbatim, P0–P3): the complete final findings block is recorded
  under [`T-014P` Split-contract review Pass 3](T-014P-planned-feed-projection.md#split-contract-review-pass-3).
- Resolution: none required; every prior finding is closed.
- Verdict: readiness-complete with no open P0–P3; T-014F is ready for owner
  promotion after exact committed-task confirmation.

### Exact committed-task confirmation

- Reviewer task name/vendor: `/root/t014_split_final_review`, fresh Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed task-file commit: `5b47c9288b0a7dc9d65f270e8b4a8cd36275cc3b`.
- Findings (verbatim, P0–P3): the complete confirmation is recorded under
  [`T-014P` Exact committed-task confirmation](T-014P-planned-feed-projection.md#exact-committed-task-confirmation).
- Resolution: none required.
- Verdict: ready for owner promotion with no open P0–P3.

### Readiness metadata review

- Reviewer task name/vendor: `/root/t014_split_final_review`, fresh Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Findings (verbatim, P0–P3): the complete lifecycle verdict is recorded under
  [`T-014P` Readiness metadata review](T-014P-planned-feed-projection.md#readiness-metadata-review).
- Resolution: none required.
- Verdict: approved with no open P0–P3.

### Owner promotion review

- Reviewer task name/vendor: `/root/t014_split_final_review`, fresh Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Findings (verbatim, P0–P3):

  > Read-only owner-promotion lifecycle review at HEAD `0e059599727f785d688e4cc1e950053d8d3ede9a`: APPROVED. P0: none. P1: none. P2: none. P3: none. The manifest contains exactly three documentation changes: T-014F task status `backlog`→`todo` plus repository-owner session log, matching BACKLOG `backlog`→`todo`, and PROGRESS stating T-014F is next for exact branch claim. T-014P is unchanged at `backlog`, retains `blocked-by: [T-014F]`, and is described as blocked. Exact readiness metadata is already committed at HEAD for both tasks, naming `/root/t014_split_final_review`, reviewed commit `5b47c9288b0a7dc9d65f270e8b4a8cd36275cc3b`, verdict `ready`. No application, test, schema, migration, or other file changes. No files edited.
- Resolution: none required.
- Verdict: approved with no open P0–P3.

## Review

Append-only implementation review passes. The implementer records each fresh
read-only reviewer response verbatim following `REVIEW_PROTOCOL-v2.md`.

### Initial claim review

- Reviewer task name/vendor: `/root/t014f_claim_review`, fresh Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed manifest: branch/base
  `a6ffca9a209147e857a2aa625ecf9f0f62a1fb3c` plus three documentation changes.
- Findings (verbatim, P0–P3):

  > Read-only initial claim review for T-014F: **APPROVED**.
  >
  > - P0: none.
  > - P1: none.
  > - P2: none.
  > - P3: none.
  >
  > Evidence:
  >
  > - Accepted integration/base is `a6ffca9a209147e857a2aa625ecf9f0f62a1fb3c`; `finapp-v2-develop` and the task branch both point to it.
  > - At that integration commit, T-014F is readiness-approved and `todo`; exact reviewed task commit is `5b47c9288b0a7dc9d65f270e8b4a8cd36275cc3b`, verdict `ready`.
  > - Dependency T-001 is accepted with `status: done`.
  > - Reflog records the exact branch being created from integration HEAD at `a6ffca9`; the claim manifest records the same immutable full base hash and implementer `Codex`.
  > - Task file, BACKLOG, and PROGRESS consistently move only T-014F from `todo` to `in-progress`.
  > - T-014P remains `backlog`, retains `blocked-by: [T-014F]`, and PROGRESS still describes it as blocked.
  > - Manifest is bounded to the expected three documentation files; no application, test, schema, migration, or untracked changes exist.
  > - `git diff --check` passed; only informational LF→CRLF warnings were emitted.
  >
  > No files were edited.
- Resolution: none required.
- Verdict: approved with no open P0–P3.

### Implementation review Pass 1

- Reviewer task name/vendor: `/root/t014f_impl_review`, fresh Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed HEAD: `908f5f2309c8948e3f912f2f75e07dc40417ffd8`.
- Reviewed manifest: modified `app/main.py`, `app/schemas.py`; untracked
  `app/transaction_feed.py`, `tests/test_transaction_feed_v21.py`.
- Findings (verbatim, P0–P3):

  > Read-only implementation review for T-014F at HEAD `908f5f2309c8948e3f912f2f75e07dc40417ffd8`.
  >
  > Verdict: **CHANGES REQUIRED**
  >
  > - P0: none.
  > - P1: none. The initially found permissive Base64 cursor handling is closed in the latest worktree: decoding now validates the URL-safe alphabet and canonical unpadded encoding, with malformed-character and extra-padding regressions.
  > - P2 — The OpenAPI regression does not freeze the full acceptance contract. `tests/test_transaction_feed_v21.py:46-74` verifies only part of the list schema. It does not assert the detail operation and positive-ID bound, detail `404`/`422`, the exact item property-name set, page required set, `mobile_type`/`transaction_type` enums, or cursor request/response `string|null` shapes. An accidental contract drift in any of those explicitly frozen fields would pass.
  > - P2 — Several explicitly required new feed branches lack meaningful regression coverage. `tests/test_transaction_feed_v21.py:78-92` does not exercise an unsupported cursor version; `:126-140` proves `local_date` correction but not `occurred_at` correction/reordering; `:182-200` does not assert the adjustment’s exact signed leg or the `income` filter; and no test exercises creator-owned unassigned visibility, despite its separate predicate at `app/transaction_feed.py:184-188`. Existing transaction tests protect the legacy route but do not protect these new feed behaviors.
  > - P3: none.
  >
  > Evidence: focused `4 passed in 1.69s`; adjacent `29 passed in 10.17s`; combined `33 passed`; `git diff --check` passed with informational line-ending warnings only. No files were edited.
- Resolution: expanded the existing four tests rather than adding optional test
  cases. They now freeze the complete list/detail OpenAPI contract and cover
  unsupported/noncanonical cursors, `occurred_at` reordering, exact adjustment
  sign, every filter, and creator-owned unassigned visibility.
- Verdict: changes required; corrected and submitted for fresh re-review.

### Implementation review Pass 2

- Reviewer task name/vendor: `/root/t014f_impl_review`, same reviewer follow-up
  used to confirm the immediate fixes; this pass does not replace the required
  fresh independent corrected-manifest review below.
- Reviewed HEAD and manifest: the same HEAD and complete corrected worktree as
  Pass 1.
- Findings (verbatim, P0–P3):

  > Read-only T-014F re-review at HEAD `908f5f2309c8948e3f912f2f75e07dc40417ffd8`: **APPROVED**.
  >
  > Exact reviewed manifest:
  >
  > `M app/main.py`, `M app/schemas.py`, `?? app/transaction_feed.py`, `?? tests/test_transaction_feed_v21.py`.
  >
  > - P0: none.
  > - P1: none.
  > - P2: none.
  > - P3: none.
  >
  > Both prior P2 findings are closed. The tests now freeze the list/detail OpenAPI shapes, bounds, enums, required/property sets, nullable cursor shapes, nested `TransactionOut`, and detail errors. They also cover unsupported-version and noncanonical cursors, `occurred_at` reordering, exact signed adjustment preservation, every named filter, and creator-owned unassigned visibility.
  >
  > Production inspection confirms stable lexicographic financial-date pagination, exact Decimal preservation through the existing serializer, exchange/adjustment mapping, accepted visibility/redaction and Plan-link compatibility, generic hidden-detail `404`, soft-delete retention, and no changes to the existing `/transactions` contract.
  >
  > Evidence: focused gate supplied `4 passed in 1.97s`; reviewer rerun `4 passed in 1.82s`; adjacent regression gate `29 passed in 10.17s`; combined evidence `33 passed`; `git diff --check` passed with informational line-ending warnings only. No files were edited.
- Resolution: none required; both Pass 1 P2 findings are closed.
- Verdict: approved with no open P0–P3.

### Cumulative process review Pass 3

- Reviewer task name/vendor: `/root/t014f_impl_review`, original implementation
  reviewer.
- Reviewed HEAD and manifest: HEAD
  `908f5f2309c8948e3f912f2f75e07dc40417ffd8`; modified `app/main.py`,
  `app/schemas.py`, BACKLOG, PROGRESS, and this task; untracked feed module and
  focused test.
- Findings (verbatim, P0–P3):

  > Verdict: **CHANGES REQUIRED — process evidence only**
  >
  > - P0: none.
  > - P1: none.
  > - P2 — The corrected coverage was not reviewed by a fresh reviewer agent as required by `docs/REVIEW_PROTOCOL-v2.md` step 5. Pass 1 and Pass 2 both used the same live identity, `/root/t014f_impl_review`, through successive turns, while `docs/tasks/T-014F-financial-date-transaction-feed.md:256` describes Pass 2 as “fresh Codex.” A new independent read-only reviewer identity must inspect the corrected complete manifest; its verbatim verdict must be recorded, and the inaccurate “fresh” characterization of Pass 2 should be corrected.
  > - P3: none.
  >
  > Technical assessment: all T-014F acceptance items are implemented and covered; the prior cursor and coverage findings are closed. Lifecycle state is now consistent across task, BACKLOG, and PROGRESS: `review`, final gates passed, awaiting owner acceptance, with T-014P still blocked.
  >
  > Gate evidence reviewed: focused `4 passed`; focused + adjacent `33 passed`; full pytest `333 passed in 92.73s`; bundled Node syntax check passed; `git diff --check` passed with informational line-ending warnings only. No files were edited.
- Resolution: corrected Pass 2's reviewer description and assigned the complete
  corrected manifest to a new independent read-only reviewer identity.
- Verdict: changes required; resolved by Pass 4.

### Fresh corrected-manifest review Pass 4

- Reviewer task name/vendor: `/root/t014f_final_review`, fresh Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed branch/base/range: branch
  `task/T-014F-financial-date-transaction-feed`, accepted base
  `a6ffca9a209147e857a2aa625ecf9f0f62a1fb3c`, HEAD
  `908f5f2309c8948e3f912f2f75e07dc40417ffd8`, committed range
  `a6ffca9a209147e857a2aa625ecf9f0f62a1fb3c..908f5f2309c8948e3f912f2f75e07dc40417ffd8`.
- Findings (verbatim, P0–P3):

  > Read-only final corrected-manifest review for T-014F: **APPROVED**.
  >
  > Complete reviewed working-tree manifest: `M app/main.py`, `M app/schemas.py`, `M docs/BACKLOG.md`, `M docs/PROGRESS.md`, `M docs/tasks/T-014F-financial-date-transaction-feed.md`, `?? app/transaction_feed.py` (SHA-256 `9D1E78DE9C0E5FD3CFF16549427EB3F9814A8EDA092D3FF49A4ABB194D0C8111`), `?? tests/test_transaction_feed_v21.py` (SHA-256 `6F04D309B44599121DEE69CB7AB8A1A117502DD9EA15DEAD39B5791B2DC6FDFD`).
  >
  > - P0: none.
  > - P1: none.
  > - P2: none.
  > - P3: none.
  >
  > The previous cursor finding is closed: cursor decoding now enforces the URL-safe alphabet, canonical unpadded Base64, exact versioned payload keys and types, supported version, naive timestamp, valid rank, and positive item ID. The previous coverage findings are also closed: the four focused tests now freeze the list/detail OpenAPI contracts and cover unsupported/noncanonical cursors, both financial-date and timestamp reordering, exact signed adjustment and exchange legs, all filters, creator-owned unassigned visibility, Plan-link compatibility, shared-leg redaction, generic hidden-detail `404`, soft-delete retention, and legacy `/transactions` compatibility.
  >
  > Production inspection confirms the required descending total order and strict continuation predicate, exact nested `TransactionOut` serialization without lossy money conversion, exchange/adjustment mobile mapping, accepted owner/shared visibility boundaries, owner-only Plan occurrence lookup compatibility, and no Plan materialization or private period/rate exposure.
  >
  > Lifecycle state is consistent: task and BACKLOG are `review`, PROGRESS reports final gates passed awaiting owner acceptance, the immutable base/implementer metadata matches the exact branch claim, T-014P remains `backlog` and blocked by T-014F, and the manifest contains no unrelated implementation work.
  >
  > Gate evidence: supplied focused `4 passed`; reviewer rerun focused `4 passed in 1.89s`; supplied combined focused/adjacent `33 passed`; supplied full suite `333 passed in 92.73s`; reviewer rerun `git diff --check` passed with informational line-ending warnings only; supplied Node syntax gate passed. No files were edited.
  >
  > Verdict: **approved with no open P0–P3; ready for evidence transcription, task commit, and owner acceptance.**
- Resolution: none required; the prior process-evidence P2 is closed.
- Verdict: approved with no open P0–P3.

### Owner acceptance lifecycle review

- Reviewer task name/vendor: `/root/t014f_final_review`, read-only Codex
  same-vendor fallback.
- Reviewed HEAD and manifest: `20c37c910b12b2f508c82195563696e416c0debc`
  plus modified BACKLOG, PROGRESS, T-014F, and T-014P documentation only.
- Findings (verbatim, P0–P3):

  > Read-only lifecycle review: **APPROVED**.
  >
  > - P0: none.
  > - P1: none.
  > - P2: none.
  > - P3: none.
  >
  > Verified: `20c37c910b12b2f508c82195563696e416c0debc` exists and is the reviewed T-014F implementation commit, directly descending from claim commit `908f5f2309c8948e3f912f2f75e07dc40417ffd8`. T-014F is consistently changed from `review` to `done`. T-014P is readiness-approved, consistently changed from `backlog` to `todo`, and is unblocked because its sole dependency T-014F is now `done`. T-014P retains blank `base-commit` and `implementer`, as required before its atomic branch claim. The exact T-014P branch does not yet exist, so the documented next action remains valid. BACKLOG, PROGRESS, and both task session logs agree on acceptance, promotion, and next action. No application, test, schema, migration, or unrelated files are changed. `git diff --check` passed with informational line-ending warnings only.
  >
  > Verdict: **approved with no open P0–P3; the owner-acceptance/promotion documentation is ready to commit before the exact T-014P branch claim.**
- Resolution: none required.
- Verdict: approved with no open P0–P3.

## Session log

- 2026-08-11 Codex: split the L-sized T-014 into bounded persisted-feed and
  Planned-projection tasks and drafted this first contract. Readiness review,
  owner promotion, branch claim, implementation, and implementation review
  remain; no application or database file changed.
- 2026-08-11 Codex: three split-contract reviews closed four P1 and two P2
  findings; exact commit `5b47c92` and lifecycle metadata were approved with
  no open P0–P3. T-014F awaits owner promotion; no application or database
  file changed.
- 2026-08-11 repository owner: promoted readiness-approved T-014F from
  `backlog` to `todo`. Exact branch claim from the committed integration HEAD
  is next; T-014P remains blocked.
- 2026-08-11 Codex: confirmed clean promoted integration HEAD
  `a6ffca9a209147e857a2aa625ecf9f0f62a1fb3c`, the exact branch was absent, and
  atomically claimed `task/T-014F-financial-date-transaction-feed`. Recorded
  immutable base/implementer; implementation is next.
- 2026-08-11 Codex: implemented the stable persisted transaction feed, strict
  versioned cursor, exact closed projections, detail route, financial ordering,
  accepted privacy/redaction, and compatibility coverage. Focused/adjacent
  combined gate is `33 passed`; two P2 coverage findings were fixed within the
  existing four tests and the fresh re-review approved with no open P0–P3.
  Full pytest `333 passed in 92.73s`; Node syntax and `git diff --check` passed.
  Final owner acceptance remains.
- 2026-08-11 repository owner: accepted independently approved commit
  `20c37c9`; T-014F is `done`. Promoted readiness-approved, now-unblocked
  T-014P from `backlog` to `todo` for an exact integration-HEAD branch claim.
