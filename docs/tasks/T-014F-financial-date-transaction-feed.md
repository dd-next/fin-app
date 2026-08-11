---
id: T-014F
title: Expose a stable financial-date feed for persisted transactions
status: backlog
size: M
spec: design/MOBILE-BACKEND-GAP-AUDIT.md feed ordering and adjustment/exchange rows
blocked-by: [T-001]
branch: task/T-014F-financial-date-transaction-feed
base-commit:
implementer:
readiness-reviewed-by: /root/t014_split_final_review (Codex same-vendor fallback)
readiness-reviewed-commit: 5b47c9288b0a7dc9d65f270e8b4a8cd36275cc3b
readiness-verdict: ready
---

## Goal

The mobile adapter can page visible persisted ledger transactions in stable
financial-date order and render every domain transaction type without changing
the richer existing desktop transaction API.

## Acceptance

- [ ] Add authenticated `GET /api/v1/transaction-feed` with query parameters
      `filter` (default `all`, exact enum `all|income|expense|transfer`),
      `cursor` (optional opaque versioned string), and `limit` (integer default
      `50`, inclusive `1..100`). Unknown/duplicate parameters, malformed or
      unsupported-version cursors, non-integer limits, and invalid filter
      values are `422` and perform no database write.
- [ ] The response is exactly `{items, next_cursor}` with no extra properties.
      Every item in this task is a closed discriminated transaction projection:
      `kind="transaction"`, stable `key="transaction:<positive id>"`,
      `financial_date`, `mobile_type`, `transaction_type`, and the existing
      full `TransactionOut` under `transaction`. IDs and Decimal values are
      never copied into an alternative lossy representation.
- [ ] Mapping is exact: domain `income|expense|transfer` keeps the same
      `mobile_type`; `exchange` maps to mobile `transfer` while retaining
      `transaction_type="exchange"` and both exact signed amount legs in the nested
      detail; `adjustment` maps to mobile `adjustment`, remains identifiable as
      a non-convertible balance correction, and retains its signed leg.
      Exchange and adjustment appear only under `filter=all`; the three named
      filters select only their matching domain transaction type.
- [ ] Feed visibility and redaction exactly reuse the accepted transaction
      list/detail rules: primary-workspace rows, visible shared-account legs,
      and creator-owned unassigned rows are eligible; inaccessible legs stay
      redacted through `has_hidden_legs`; foreign/hidden detail IDs return the
      generic `404 Feed item not found`. The nested accepted `TransactionOut`
      preserves owner-visible `plan_occurrence_id` and its existing serializer
      lookup, while shared/redacted projections keep that value `null`. This
      task performs no Plan materialization and adds no Plan projection/detail
      field beyond that existing compatibility value; private period/rate state
      is neither queried nor exposed.
- [ ] Persisted items order descending by the stable total key
      `(financial_date, sort_at, kind_rank, item_id)`, where
      `financial_date=Transaction.local_date`, `sort_at=occurred_at`,
      `kind_rank=1`, and `item_id=Transaction.id`. The opaque cursor encodes
      that complete last-item key plus version `1`; continuation applies a
      strict lexicographic `<` predicate. A fixed dataset produces no duplicate
      or omitted items across pages, including equal dates/timestamps.
- [ ] A correction that changes `local_date` or `occurred_at` moves the row to
      its new financial position on a fresh read regardless of ID. Soft Delete
      keeps the row in the same financial position with nested status
      `deleted`; it never removes or re-dates history. Account/period filters on
      the existing `/api/v1/transactions` route retain their accepted snapshot
      and financial-date-independent membership semantics.
- [ ] Add authenticated
      `GET /api/v1/transaction-feed/transaction/{transaction_id}` using the
      same closed transaction projection as the list. This is the common
      Transaction-details data route that T-014P extends with a `planned`
      discriminator; a positive integer ID is required and hidden/foreign IDs
      return `404 Feed item not found`.
- [ ] OpenAPI freezes the list/detail query/path bounds, exact item/page
      property and required sets, `additionalProperties: false`, discriminator
      constant, enum mappings, cursor string/null shapes, existing nested
      `TransactionOut` reference, and documented `404`/`422` errors.
- [ ] Existing `GET /api/v1/transactions` filters, integer ID cursor,
      `TransactionPageOut`, detail/correction/Delete routes, explicit
      adjustment/exchange identity, and desktop behavior remain byte-shape
      compatible and regression protected. No existing route is repurposed.
- [ ] Focused feed ordering/mapping/pagination/privacy/OpenAPI tests, existing
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

## Review

Append-only implementation review passes. The implementer records each fresh
read-only reviewer response verbatim following `REVIEW_PROTOCOL-v2.md`.

## Session log

- 2026-08-11 Codex: split the L-sized T-014 into bounded persisted-feed and
  Planned-projection tasks and drafted this first contract. Readiness review,
  owner promotion, branch claim, implementation, and implementation review
  remain; no application or database file changed.
- 2026-08-11 Codex: three split-contract reviews closed four P1 and two P2
  findings; exact commit `5b47c92` and lifecycle metadata were approved with
  no open P0–P3. T-014F awaits owner promotion; no application or database
  file changed.
