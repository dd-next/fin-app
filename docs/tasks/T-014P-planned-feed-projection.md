---
id: T-014P
title: Project open Plan occurrences through Transaction details
status: backlog
size: M
spec: design/MOBILE-BACKEND-GAP-AUDIT.md planned ledger rows
blocked-by: [T-014F]
branch: task/T-014P-planned-feed-projection
base-commit:
implementer:
readiness-reviewed-by:
readiness-reviewed-commit:
readiness-verdict:
---

## Goal

The stable financial-date feed includes owner-private open Plan occurrences as
explicit non-ledger projections whose rows open the common Transaction-details
data route with Plan-specific actions.

## Acceptance

- [ ] Extend `GET /api/v1/transaction-feed` with exact `filter=planned` and a
      closed `kind="planned"` item branch. `filter=planned` returns only Plan
      projections; `filter=all` unions persisted T-014F items with Plan
      projections; the persisted `income|expense|transfer` filters remain
      unchanged and never return planned items.
- [ ] Before the feed query, synchronously materialize the authenticated user's
      primary workspace through the accepted idempotent Plan horizon logic.
      Strictly validate the complete query shape and decode/version-check the
      cursor before materialization or any write. Then capture one server clock
      for materialization/status/order decisions.
      Repeated reads at the same clock create no duplicate occurrence and no
      transaction, leg, exchange-rate, account-period, balance, summary, or
      Undo mutation. Materialized `PlanOccurrence` rows are not fake ledger
      rows and never affect capital or Available today.
- [ ] Include only unresolved occurrence states `planned|overdue`. Completed
      occurrences are represented by their linked persisted transaction;
      skipped occurrences are absent. Inactive/archived rules generate no new
      projections. Archiving a rule marks every existing open occurrence
      `skipped`, so those occurrences are absent from both `all` and `planned`
      feeds and cannot open through feed detail.
- [ ] Every planned list item is exactly: `kind="planned"`, stable
      `key="planned:<positive occurrence id>"`,
      `financial_date=due_date`, `mobile_type="planned"`, required property
      `mobile_status` with exact enum `planned|required|overdue`: `overdue`
      when the occurrence is overdue, otherwise `required` when
      `rule.is_required`, otherwise `planned`; and the existing full
      `PlanOccurrenceOut` under `occurrence`. Planned amount/asset/account/rule
      data stays Decimal/exact and owner-private.
- [ ] Planned ordering uses the T-014F total cursor key with
      `sort_at=workspace_day_boundary(due_date)`, `kind_rank=0`, and
      `item_id=PlanOccurrence.id`. Transaction and planned keys merge under one
      descending comparator and one opaque version-1 continuation cursor.
      Same-date/timestamp/kind ties are deterministic; fixed-dataset paging has
      no duplicates or omissions across the union.
- [ ] Extend the common detail route with authenticated
      `GET /api/v1/transaction-feed/planned/{occurrence_id}`. It returns the
      closed planned projection plus exact ordered
      `available_actions=["edit_rule","skip","link_transaction"]` for an
      unresolved item. It never returns transaction Edit/Delete actions and
      never redirects to a Plan route. Completed/skipped, foreign, hidden, or
      unknown occurrences return generic `404 Feed item not found` without
      revealing owner-private Plan state.
- [ ] The action names bind to existing accepted commands: Edit rule uses the
      occurrence's `plan_rule_id`; Skip affects only this occurrence; Link
      transaction attaches an eligible posted root. Executing those existing
      commands changes subsequent feed/detail results through domain state; the
      feed adds no duplicate write command and performs no action itself.
- [ ] Shared-account editor/contributor/viewer and unrelated users never see or
      infer another workspace's Plan projections through `filter=all`,
      `filter=planned`, cursor contents, counts, ordering gaps, detail IDs, or
      errors. They continue to see persisted shared-leg transactions according
      to T-014F without gaining Plan access.
- [ ] OpenAPI freezes the expanded filter enum, discriminated page union,
      exact planned list/detail property/required/type/format/enum/bound sets,
      `additionalProperties: false`, nested `PlanOccurrenceOut` reference,
      ordered action enum, common cursor shape, and documented `404`/`422`.
- [ ] Invalid/duplicate/unknown query parameters and malformed or unsupported
      cursors are rejected before Plan materialization. Those `422` responses
      leave rules, occurrences, transactions, legs, periods, balances,
      captured rates, and Undo rows unchanged.
- [ ] Correction/Delete of persisted transactions and Skip/Link/rule archival
      of Plan occurrences produce the exact next fresh feed order/content.
      Deleting a transaction linked to a Plan occurrence keeps the deleted
      transaction history row and reopens the occurrence as `planned` or
      `overdue`; `filter=all` therefore returns both rows, ordered solely by the
      common total key even when they share a financial date.
      Pagination tests cover transaction/planned interleaving at equal dates,
      page boundaries, and owner-private filtering without creating ledger
      movements.
- [ ] Existing `/workspaces/{workspace_id}/plan-occurrences`, rule endpoints,
      Skip/Link commands, `/transactions`, T-014F transaction-only projections,
      richer desktop filters, balances, periods, and Undo remain compatible.
- [ ] Focused union/detail/privacy/no-ledger/pagination/OpenAPI tests, existing
      Plan/transaction tests, full pytest, Node syntax, and diff/status gates
      pass on isolated fixtures.

## Touches

- `app/transaction_feed.py`
- `app/schemas.py`
- `app/plan.py` only for bounded reuse/extraction of existing materialization
  and owner-private occurrence projection helpers if necessary
- `tests/test_planned_transaction_feed_v21.py`
- existing Plan/feed tests only for direct compatibility assertions
- `docs/tasks/T-014P-planned-feed-projection.md`
- `docs/BACKLOG.md` and `docs/PROGRESS.md` for lifecycle only

## Out of scope

- Fake financial transactions, automatic Plan payment/receipt, new Skip/Link
  semantics, Plan-rule mobile create/edit mapping (T-019), type conversion
  (T-015), category/account lifecycle, mobile UI, migrations, background jobs,
  or `finapp.db` mutation.
- Replacing the Plan screen/detail APIs or altering persisted T-014F transaction
  mapping and the existing desktop `/transactions` contract.

## Verification

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_planned_transaction_feed_v21.py tests/test_transaction_feed_v21.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_plan_v2.py tests/test_ledger_v2.py tests/test_periods_v2.py -q
.\.venv\Scripts\python.exe -m pytest -q
node --check app/static/app.js
git diff --check
git status --short
```

All database-backed tests use isolated fixtures and never open, replace, or
delete `finapp.db`.

## Readiness review

Append-only readiness passes against the audit, frozen Transactions/Plan tap
map/data model, accepted Plan/ledger/privacy behavior, T-014F, AGENTS,
BUILD_PLAN, and REVIEW_PROTOCOL.

### Split-contract review Pass 1

- Reviewer task name/vendor: `/root/t014_split_review`, fresh Codex same-vendor
  fallback; cross-vendor reviewer unavailable in this session.
- Reviewed manifest: integration HEAD `36f3366` plus modified BACKLOG and both
  untracked T-014 split task files.
- Findings (verbatim, P0–P3):

  > Read-only T-014 split review verdict: NOT READY; P0 none, three P1 and two P2 contract gaps.
  >
  > P0: none.
  >
  > P1 — T-014F promises exchange data that its frozen payload cannot contain, and that deleted exchanges no longer retain. `docs/tasks/T-014F-financial-date-transaction-feed.md:30-40` closes each item to the listed projection with the existing full `TransactionOut` under `transaction`, yet also requires “both exact legs/rates in the nested detail.” Existing `TransactionOut` has legs but no rates (`app/schemas.py:360-386`; `app/ledger.py:389-443`); rates are a separate `ExchangeRateOut`/`GET /exchange-rates` contract (`app/schemas.py:462-467`; `app/transactions.py:953-973`). More importantly, soft Delete physically removes the exchange’s captured-rate rows (`app/transactions.py:890-915`), while T-014F also requires deleted history to remain at the same position (`T-014F:56-59`) and places captured-rate behavior out of scope (`:95-96`). The implementer therefore cannot meet the closed item shape, exact rates, deletion, and out-of-scope clauses simultaneously. The audit only requires preservation of the two-amount detail. Resolve explicitly: either require the exact nested signed legs only, or define an additional exact captured-rate field/schema, privacy behavior, and deleted-history persistence and widen scope accordingly.
  >
  > P1 — T-014P does not name the required planned-status property, so the supposedly closed schema is not executable. `docs/tasks/T-014P-planned-feed-projection.md:42-48` lists exact fields, then says only “mobile status `overdue|required|planned`” without saying whether the JSON property is `status`, `mobile_status`, or something else; `:73-76` nevertheless requires OpenAPI to freeze exact property/required sets. Name the property and its exact enum/requiredness in list and detail.
  >
  > P1 — Cursor validation/write neutrality conflicts with Plan materialization sequencing. T-014F requires every malformed/unsupported cursor to return 422 with no database write (`T-014F:24-29`). T-014P says to materialize before the feed query (`T-014P:29-35`), while cursor version/payload validation must occur in application code and the existing `materialize_workspace` commits (`app/plan.py:419-435`). A direct implementation can persist occurrences before discovering a bad cursor, violating the inherited T-014F contract. Require strict unknown/duplicate/query/cursor validation and cursor decoding before any materialization/write, and add a T-014P regression proving malformed/unsupported cursors leave Plan rows unchanged.
  >
  > P2 — The archival criterion is deliberately non-exact. `T-014P:36-41` says an already-open occurrence is handled “exactly as [the accepted archival] policy specifies,” but does not state that policy, so it fails the task-template requirement that acceptance be checkable without judgment. Current accepted behavior archives a rule by marking every open occurrence `skipped` (`app/plan.py:180-204,399-417`), which makes it absent from this feed. Freeze that result (or name a different controlling contract) and test it; do not leave a future implementer to reinterpret retained open rows.
  >
  > P2 — Linked-transaction Delete has an important two-row outcome that the task asks to test but never defines. Current Delete keeps the persisted transaction as `deleted` and reopens its linked occurrence as `planned|overdue` (`app/transactions.py:890-929`). Under the proposed union, a fresh `filter=all` should therefore contain both the deleted transaction history row and the reopened planned projection. `T-014P:36-38,77-80` only says Delete produces the “exact” next content without specifying that result. State and test the two-row outcome, including deterministic ordering/pagination if both share a financial date.
  >
  > P3: none.
  >
  > The L→M/M split itself is bounded, ordered correctly (`T-014P` blocked by `T-014F`, downstream T-015/T-021 rewired), and consistent with BUILD_PLAN Phase 14 block 5. After the findings above are corrected, both task definitions need a fresh read-only readiness re-review before owner promotion.
- Resolution: removed the impossible captured-rate promise from T-014F; named
  required `mobile_status`; moved validation before materialization; froze
  archival-to-skipped absence and linked-Delete's deleted+reopened two-row
  outcome with mutation/order coverage.
- Verdict: not ready; all three P1 and both P2 findings corrected for fresh
  re-review.

### Split-contract review Pass 2

- Reviewer task name/vendor: `/root/t014_split_rereview`, fresh Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed manifest: integration HEAD `36f3366` plus modified BACKLOG and both
  untracked corrected task files.
- Findings (verbatim, P0–P3):

  > Read-only T-014 split re-review verdict: **NOT READY**; all previous findings are closed, but one new P1 contract contradiction remains.
  >
  > P0: none.
  >
  > P1 — T-014F simultaneously requires the existing full `TransactionOut` and forbids the Plan query/value that this accepted response already contains. `docs/tasks/T-014F-financial-date-transaction-feed.md:30-35,43-48` requires the full existing nested response and exact reuse of accepted transaction list/detail behavior, but also says owner-private Plan state is “neither queried nor exposed.” `TransactionOut` includes `plan_occurrence_id` (`app/schemas.py:368-386`), and its accepted serializer queries `PlanOccurrence` for owner-visible transactions and returns that ID (`app/ledger.py:422-449`). T-014P cannot resolve this later because it explicitly places alteration of the T-014F transaction mapping out of scope (`docs/tasks/T-014P-planned-feed-projection.md:117-118`). Freeze one executable result. The compatibility-preserving option is to retain the existing owner-visible `plan_occurrence_id`, keep it `null` for shared/redacted projections, and narrow the isolation clause to prohibit Plan materialization and new Plan projection/detail fields in T-014F. Alternatively, require `plan_occurrence_id=null` and no Plan query explicitly, acknowledge that this is narrower than existing owner detail behavior, and allow T-014P to define the later mapping.
  >
  > P2: none.
  >
  > P3: none.
  >
  > Confirmed closed from Pass 1:
  >
  > - Exchange mapping now promises the audit-required exact signed legs, not captured rates.
  > - `mobile_status` is explicitly named, required, and enum-bounded.
  > - Complete query/cursor validation precedes materialization and any write.
  > - Rule archival explicitly skips and removes every open occurrence from feed/detail.
  > - Deleting a linked transaction explicitly produces both the retained deleted transaction and reopened planned projection.
  >
  > The remaining cursor total order, financial-date correction/Delete behavior, permission/redaction boundaries, write neutrality, OpenAPI requirements, Touches, dependencies, and the M/M split are otherwise readiness-complete. `git diff --check` passed for the tracked BACKLOG change; both untracked task files were inspected directly. No files were edited.
- Resolution: T-014F now preserves the accepted owner-visible
  `plan_occurrence_id` and shared `null`, while prohibiting only new Plan
  materialization/projection/detail behavior before T-014P.
- Verdict: not ready; the sole P1 is corrected for fresh re-review.

### Split-contract review Pass 3

- Reviewer task name/vendor: `/root/t014_split_final_review`, fresh Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed manifest: integration HEAD `36f3366` plus modified BACKLOG and both
  untracked fully corrected task files.
- Findings (verbatim, P0–P3):

  > Read-only final re-review verdict: APPROVED / readiness-complete for both T-014F and T-014P. P0: none. P1: none. P2: none. P3: none. The sole Pass2 P1 is closed: T-014F now explicitly preserves the accepted owner-visible `plan_occurrence_id` and existing serializer lookup, keeps it `null` for shared/redacted projections, and prohibits only Plan materialization plus new Plan projection/detail fields (T-014F:43-52), matching `TransactionOut`/`transaction_out` behavior in app/schemas.py:368-386 and app/ledger.py:422-449. Reconfirmed closed: exact signed exchange legs rather than unavailable captured rates; required enum-bounded `mobile_status`; complete validation/cursor decoding before materialization/write; archival-to-skipped absence; linked Delete’s retained-deleted + reopened-planned two-row result; Decimal-preserving nested models; T-014F/T-014P dependency and Touches boundaries; stable total cursor/order; privacy/redaction and generic 404s; write neutrality; and exact OpenAPI/test gates. BACKLOG rewiring is coherent, `git diff --check` passes, and both untracked task files were inspected directly. T-014F is ready for owner promotion; T-014P is readiness-approved but remains blocked from promotion/claim until T-014F is accepted. No files edited.
- Resolution: none required; every Pass 1/2 finding is closed.
- Verdict: readiness-complete with no open P0–P3; T-014P remains blocked by
  accepted T-014F implementation.

## Review

Append-only implementation review passes. The implementer records each fresh
read-only reviewer response verbatim following `REVIEW_PROTOCOL-v2.md`.

## Session log

- 2026-08-11 Codex: split the L-sized T-014 into bounded persisted-feed and
  Planned-projection tasks and drafted this dependent contract. Readiness
  review, owner promotion after T-014F, branch claim, implementation, and review
  remain; no application or database file changed.
- 2026-08-11 Codex: split-contract Pass 1 found three P1 and two P2 executable
  contract gaps. Exchange detail, named planned status, pre-write validation,
  archival absence, and linked-Delete two-row behavior are now exact. Fresh
  read-only re-review remains; no application or database file changed.
- 2026-08-11 Codex: Pass 2 confirmed all prior findings closed and found one
  P1 compatibility contradiction around nested `plan_occurrence_id`. The
  accepted owner/shared redaction behavior is now explicit; fresh re-review
  remains and no application or database file changed.
- 2026-08-11 Codex: Pass 3 approved both bounded contracts with no open P0–P3.
  Exact committed-task confirmation remains before readiness metadata and owner
  promotion; no application or database file changed.
