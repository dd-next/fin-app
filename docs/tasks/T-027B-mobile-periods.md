---
id: T-027B
title: Implement mobile account-period cards and lifecycle
status: todo
size: M
spec: design/Finnapp mobile specification/spec/03-screens.md §3.3; spec/04-sheets.md; spec/05-interactions.md
blocked-by: [T-027A]
branch: task/T-027B-mobile-periods
base-commit:
implementer:
readiness-reviewed-by: /root/phase15_readiness_review, Codex GPT-5 same-vendor fallback
readiness-reviewed-commit: deb8a5a
readiness-verdict: ready
---

## Goal

Complete the Operations period card and owner-private Start, Active, Edit,
Close, and History flows using only ledger-derived Phase 14 values.

## Acceptance

- [ ] The period-card slot is exactly 96px for active, absent, loading, error,
      and non-owner states.
- [ ] Owner current state renders API `available_today`, `Period · Nd`, and
      currency; absent renders `No period` and `+ Start period`.
- [ ] Shared/non-owner accounts never request owner-private period endpoints and
      render the same non-actionable No period state regardless of owner state.
- [ ] Start shows account/current balance, Start/End date and a checked
      Redistribute checkbox. Checked maps to
      `redistribute_remaining_days`; unchecked maps to `carry_next_day`.
- [ ] Edit exposes only accepted mutable fields and the same policy mapping.
- [ ] Active detail shows status, dates, opening/current balance and Available
      today. History lists current/ended/closed without Funding, Remaining,
      period Planned, or fake valuation.
- [ ] Branded Close refreshes to absent; successful Start refreshes active.
      Ended/closed periods are read-only.
- [ ] Available today is informational and may be negative.
- [ ] Account changes refresh balance, allowance, days, opening balance and
      currency without stale request overwrite; errors preserve server
      authority and allow bounded retry.
- [ ] UI formats exact API Decimal strings to asset precision and does not
      recompute ledger values.
- [ ] Desktop period controls remain functional. No backend/schema, owner-state
      inference, funding, Plan reservation, or future scheduling is added.

## Touches

`app/static/index.html`, `app/static/app.js`, `app/static/style.css`,
`tests/test_mobile_periods_ui_v21.py`, `tests/test_frontend_v2.py`, design notes,
and task lifecycle evidence.

## Out of scope

Other Operations commands, backend/schema/API changes, shared period exposure,
future periods, period funding, Plan reservation, other screens.

## Verification

```bash
.venv/bin/python -m pytest -q tests/test_mobile_periods_ui_v21.py tests/test_frontend_v2.py tests/test_period_api_v21.py tests/test_periods_v2.py tests/test_period_lifecycle_v2.py tests/test_period_start_replay_v2.py tests/test_period_permissions_v21.py tests/test_period_contract_removal_v21.py tests/test_budget_carry_v2.py tests/test_budget_redistribute_v2.py
node --check app/static/app.js
git diff --check
```

Use `verify` for absent/current/ended/closed, Start/Edit policies, close/restart,
negative allowance, account switching and a shared account at 390×844, plus
desktop period regression.

## Review

Append the bounded independent implementation review following the protocol.

## Session log

- 2026-08-12 Codex GPT-5: task split from former L-sized T-027; not claimed.
- 2026-08-12 Codex GPT-5: independent batch readiness verdict `ready`; remains
  blocked by T-027A.
- 2026-08-13 repository owner authorisation executed by `/root`, Codex GPT-5:
  confirmed T-027A locally accepted, accepted T-027B readiness evidence, and
  promoted T-027B from `backlog` to `todo` on accepted integration `1b2e89a`;
  no task branch was claimed in this checkpoint.
