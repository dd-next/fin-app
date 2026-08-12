---
id: T-028
title: Implement mobile Plan flows and Analytics placeholder
status: backlog
size: M
spec: specs/FinnApp-v2.md §8; design/Finnapp mobile specification/spec/03-screens.md §3.4–§3.5; spec/04-sheets.md
blocked-by: [T-019, T-024B]
branch: task/T-028-mobile-plan-analytics
base-commit:
implementer:
readiness-reviewed-by: /root/phase15_readiness_review, Codex GPT-5 same-vendor fallback
readiness-reviewed-commit: deb8a5a
readiness-verdict: ready
---

## Goal

Implement accepted mobile Plan rule/occurrence workflows and the exact Analytics
placeholder without creating ledger effects or inventing analytics.

## Acceptance

- [ ] Plan follows active `FinnApp-v2.md` §8: one card per rule, not the older
      global Upcoming layout. A card shows at most nearest overdue and nearest
      future; multiple overdue shows total count; remaining history is details.
- [ ] Open/Completed/Show stay compact; empty copy matches spec.
- [ ] Add/Edit uses `mobile_kind`, exact Decimal amount, asset, recurrence,
      first due, supported category, and one `account_id` adapter.
- [ ] Expected income labels `To account`; expense/transfer kinds label
      `From account`.
- [ ] An unresolved item shows Edit rule, Skip, Link transaction in one row and
      that order. Skip affects only one occurrence.
- [ ] Link offers eligible posted transactions by semantic type, does not
      enforce account/asset equality, and creates no fake transaction.
- [ ] Branded Delete archives the rule; linked transactions remain, future/open
      items disappear as accepted. Pay/Receive and category merge/delete stay
      absent.
- [ ] Plan never changes balances, Total capital, Available, periods, or Undo.
- [ ] Analytics renders exact header/avatar and Coming soon copy with no charts,
      filters, ranges, data fetches or invented values; avatar opens Profile.
- [ ] Desktop full rule/occurrence history and supported behavior remain
      functional.
- [ ] No backend/schema, automatic payment, full analytics, or
      T-015/T-016/T-017 work is added.

## Touches

`app/static/index.html`, `app/static/app.js`, `app/static/style.css`,
`tests/test_mobile_plan_analytics_ui_v21.py`, `tests/test_frontend_v2.py`, design
notes, and task lifecycle evidence.

## Out of scope

Backend/schema, transaction creation, automatic payment, category merge/delete,
other feature screens, full analytics.

## Verification

```bash
.venv/bin/python -m pytest -q tests/test_mobile_plan_analytics_ui_v21.py tests/test_frontend_v2.py tests/test_mobile_plan_contract_v21.py tests/test_plan_v2.py tests/test_planned_transaction_feed_v21.py tests/test_phase12_privacy_v2.py
node --check app/static/app.js
git diff --check
```

Use `verify` for populated/empty Plan, nearest occurrences/count, all three item
actions, Add/Edit/Delete with dynamic labels, eligible cross-account/asset Link,
Analytics/Profile at 390×844, and desktop Plan regression.

## Review

Append the bounded independent implementation review following the protocol.

## Session log

- 2026-08-12 Codex GPT-5: task specified for batch readiness; not claimed.
- 2026-08-12 Codex GPT-5: independent batch readiness verdict `ready`; remains
  blocked by T-024B.
