---
id: T-026
title: Implement the mobile Transactions feed and management flows
status: in-progress
size: M
spec: design/Finnapp mobile specification/spec/03-screens.md §3.2; spec/04-sheets.md; spec/05-interactions.md; spec/06-content.md
blocked-by: [T-024B]
branch: task/T-026-mobile-transactions
base-commit: f3f747bfcc9e1e731f7200770c2b963da1753a19
implementer: /root, Codex GPT-5
readiness-reviewed-by: /root/phase15_readiness_review, Codex GPT-5 same-vendor fallback
readiness-reviewed-commit: deb8a5a
readiness-verdict: ready
---

## Goal

Make Transactions a stable mobile financial-date feed with working chips,
details, correction, assignment, Plan linking, swipe and branded Delete while
preserving richer desktop filters and the Phase 14 contracts.

## Acceptance

- [ ] Mobile has the exact header/filter badge, chip lane, date-grouped scrolling
      list, row/status/empty copy, and no transaction creation control.
- [ ] All/Income/Expense/Transfer/Planned use `/api/v1/transaction-feed` with
      exact opaque cursor behavior; switching chip resets pagination and removes
      empty groups.
- [ ] Exchange maps visibly to Transfer, adjustment appears only in All,
      Deleted stays at financial-date position, and planned rows never affect
      ledger-derived values.
- [ ] Persisted/planned rows use their discriminated detail endpoints; hidden
      legs remain redacted and inaccessible IDs retain generic not-found.
- [ ] Planned details open the Plan-item flow rather than changing tabs.
- [ ] Swipe exposes keyboard-accessible Plan/Delete actions, with the specified
      visual shift and ≥44px targets.
- [ ] Branded Delete soft-voids through the accepted endpoint, supports required
      ended/shared confirmation without native dialogs, and refreshes the feed.
- [ ] Mobile correction omits transaction Type conversion. Accepted assignment
      remains available where applicable.
- [ ] Advanced Filters uses the persisted `/transactions` API for Account,
      Period, Type, Category, From and To. While active it shows persisted rows
      only; choosing a top chip clears it and returns to the unified feed.
- [ ] Empty-state Open Operations switches tab and closes overlays.
- [ ] Desktop retains richer status/adjustment/exchange filters, assignment and
      existing behavior.
- [ ] No backend/query extension, fake paged client filter, hard delete,
      transaction creation, or T-015 conversion is added.

## Touches

`app/static/index.html`, `app/static/app.js`, `app/static/style.css`,
`tests/test_mobile_transactions_ui_v21.py`, `tests/test_frontend_v2.py`, design
notes, and task lifecycle evidence.

## Out of scope

Backend/feed contract changes, type conversion, category merge/delete, Plan
screen redesign, Operations, Accounts/Profile, periods, desktop redesign.

## Verification

```bash
.venv/bin/python -m pytest -q tests/test_mobile_transactions_ui_v21.py tests/test_frontend_v2.py tests/test_transaction_feed_v21.py tests/test_planned_transaction_feed_v21.py tests/test_transactions_phase12_v2.py tests/test_phase12_privacy_v2.py
node --check app/static/app.js
git diff --check
```

Use `verify` for chips/pagination/groups, all item kinds, swipe, filters,
details/correction/delete/empty state at 390×844 and retained filters at
1280×900.

## Review

Append the bounded independent implementation review following the protocol.

## Session log

- 2026-08-12 Codex GPT-5: task specified for batch readiness; not claimed.
- 2026-08-12 Codex GPT-5: independent batch readiness verdict `ready`; remains
  blocked by T-024B.
- 2026-08-13 repository owner authorisation executed by `/root`, Codex GPT-5:
  accepted readiness evidence and promoted T-026 from `backlog` to `todo` on
  accepted integration; no task branch was claimed in this checkpoint.
- 2026-08-13 repository owner authorisation executed by `/root`, Codex GPT-5:
  atomically claimed `task/T-026-mobile-transactions` from accepted integration
  `f3f747b`, recorded `/root` as implementer, and started only T-026.
