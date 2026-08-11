---
id: T-013Q
title: Persist exact one-amount same/cross-asset Transfer quotes
status: backlog
size: M
spec: design/MOBILE-BACKEND-GAP-AUDIT.md cross-asset Transfer
blocked-by: [T-012]
branch: task/T-013Q-transfer-quote
base-commit:
implementer:
readiness-reviewed-by:
readiness-reviewed-commit:
readiness-verdict:
---

## Goal

The public API can quote one exact source amount into a same-asset or
cross-asset destination amount using the accepted manual Asset-to-Main rates,
and persist an immutable, short-lived quote that T-013E can execute without
re-reading or reinterpreting a changed rate.

## Acceptance

- [ ] `POST /api/v1/operations/transfer/quotes` accepts exactly
      `from_account_id`, `to_account_id`, `from_amount`, and `rate_source`.
      `from_amount` is a positive plain Decimal JSON string; JSON numbers,
      exponent/sign syntax, booleans, null, non-finite values, unsupported
      scale/precision, and unknown members return input-derived `422` before
      a quote row is written. `rate_source` is exactly `manual`; Auto/external
      sources remain unavailable.
- [ ] The source and destination are distinct, active accounts in one
      workspace. The caller must have the accepted transaction-create/edit
      permission on both accounts. Hidden/foreign accounts and owner-private
      workspace/rate data retain existing `404`/`403` privacy semantics, and a
      failed quote writes nothing.
- [ ] A same-asset quote uses exact identity conversion: destination amount
      equals source amount after the one shared asset-precision validation,
      rate is `1`, and no manual-rate row is required.
- [ ] A cross-asset quote uses only the workspace's current manual
      Asset-to-Main values accepted by T-012. For Main `M`, source `S`, target
      `D`, it computes `S → D` as `rate(S → M) / rate(D → M)`, treating a
      Main-side component as exact `1`. Canonical and tagged legacy rows use
      the shared direction-aware helper; no latest transaction exchange,
      multi-hop non-Main pair, foreign-workspace rate, external provider, or
      binary `float` participates.
- [ ] Missing manual components return deterministic `422` naming each
      unvalued Asset-to-Main pair. The failure does not create a quote or alter
      accounts, rates, ledger rows, periods, or Undo candidates.
- [ ] Intermediate multiplication/division uses the repository's explicit
      high-precision Decimal helpers and never ambient 28-digit context.
      Destination money is rounded once to the destination asset precision
      with `ROUND_HALF_UP`; the source amount is validated at source precision.
      The public effective rate is the supported 18-place exact quotient of
      persisted destination/source amounts.
- [ ] A quote is accepted only when the outgoing and incoming values, each
      independently converted by the selected manual rates and rounded at the
      Main asset presentation boundary, are equal. An amount that cannot be
      represented in the destination precision without changing displayed
      Total capital returns deterministic `422` and writes nothing.
- [ ] The `201` response contains exact keys `id`, `workspace_id`,
      `created_by_user_id`, `from_account`, `to_account`, `from_amount`,
      `to_amount`, `rate`, `rate_source`, `main_asset`, `created_at`, and
      `expires_at`. Accounts and Main use the exact public account/asset shapes
      selected during readiness; every money/rate value is a normalized Decimal
      JSON string and OpenAPI freezes the request, response, required-property,
      type, and pattern contract.
- [ ] Quotes expire exactly five minutes after server creation time, use UTC
      timestamps, and are immutable. Expired rows are retained for audit and
      lazy rejection; no queue, worker, scheduled cleanup, Redis, or external
      dependency is added.
- [ ] A new additive Alembic revision after
      `0003_manual_rate_direction` creates a `transfer_quote` table with exact
      Decimal storage for both amounts and the effective rate; workspace,
      creator, source/destination account and asset, quoted Main asset,
      creation/expiry, single-use status, and executed transaction linkage are
      explicit. Named checks constrain status/rate source/positive values;
      indexes support creator/workspace/status/expiry lookup and the executed
      transaction link is unique when present.
- [ ] Quote persistence snapshots every execution-relevant value, including
      account/asset/Main identities and both exact amounts, so later manual-rate
      update/delete cannot mutate the quote. T-013E may bind execution to these
      fields but may not recalculate the destination amount.
- [ ] Migration verification covers clean upgrade from `0003`, SQLite
      constraints/indexes/FKs, PostgreSQL-compatible Numeric/check/index DDL,
      downgrade back to `0003`, and one Alembic head. The migration is additive
      and does not read, rewrite, or require `finapp.db` or legacy v1 rows.
- [ ] ADR-0009 records persisted five-minute single-use quotes, manual
      Asset-to-Main cross-rate derivation, destination quantization, displayed
      Total-capital neutrality, immutable rate binding, and the decision not to
      add background cleanup; `docs/DECISIONS.md` indexes it.
- [ ] Focused quote/domain/OpenAPI/permission/migration tests, full pytest,
      Node syntax, and diff/status checks pass using isolated fixtures or an
      explicit scratch `DATABASE_URL` only.

## Touches

- `app/models.py`
- `app/schemas.py`
- `app/ledger.py` only for a shared exact manual-rate/cross-rate helper
- `app/transfer_quotes.py` and router registration
- `alembic/versions/0004_transfer_quotes.py`
- `tests/test_transfer_quotes_v21.py`
- `tests/test_migrations_v2.py`
- `docs/decisions/ADR-0009-bound-transfer-quotes.md`
- `docs/DECISIONS.md`
- `docs/tasks/T-013Q-transfer-quote.md`
- `docs/BACKLOG.md` and `docs/PROGRESS.md` for task lifecycle only

## Out of scope

- Executing, consuming, refreshing, cancelling, or listing a quote; T-013E
  owns execution and replay/expiry error behavior.
- Changing the existing same-asset `/operations/transfer` or explicit
  two-amount `/operations/exchange` routes, fee behavior, captured transaction
  exchange rates, Undo, transaction feed/detail mapping, or desktop UI.
- Automatic/external rates, network calls, multi-hop rate graphs, quote cleanup
  jobs, account-period changes, mobile UI, Phase 15, or `finapp.db` mutation.

## Verification

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_transfer_quotes_v21.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_valuation_rate_direction_v21.py tests/test_valuation_v2.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_migrations_v2.py -q
.\.venv\Scripts\python.exe -m pytest -q
node --check app/static/app.js
git diff --check
git status --short
```

All database-backed commands use isolated fixtures or an explicit absolute
scratch `DATABASE_URL`. They never fall back to, open, replace, or delete
`finapp.db`.

## Readiness review

Append-only readiness passes against the accepted transfer audit, T-012 and
ADR-0008 rate direction, shipped ledger/permissions/period/Undo invariants,
AGENTS, BACKLOG, BUILD_PLAN, and REVIEW_PROTOCOL.

## Review

Append-only implementation review passes. A different read-only agent returns
the review; the implementer records it verbatim following
[`../REVIEW_PROTOCOL-v2.md`](../REVIEW_PROTOCOL-v2.md).

## Session log

- 2026-08-11 Codex: split the ordered L-sized T-013 into bounded quote and
  execution tasks and drafted the exact quote contract. Readiness review,
  owner promotion, branch claim, implementation, and implementation review
  remain; no application code or database was changed.
