---
id: T-025A
title: Implement mobile Accounts and account lifecycle
status: backlog
size: M
spec: design/Finnapp mobile specification/spec/03-screens.md §3.1; spec/04-sheets.md account catalogue
blocked-by: [T-024B]
branch: task/T-025A-mobile-accounts
base-commit:
implementer:
readiness-reviewed-by:
readiness-reviewed-commit:
readiness-verdict:
---

## Goal

Make Accounts and its account detail/create/edit/reconcile/archive/history flows
usable at 390×844 through accepted APIs while preserving desktop.

## Acceptance

- [ ] Mobile Accounts implements the exact 44px header, 72px single-surface
      capital strip, optional 44px rate warning, storage groups, 64px rows,
      56px New account row, permitted long-list scroll, and exact empty state.
- [ ] Every visible account appears once: cash storage → `CASH`; crypto
      asset/storage → `CRYPTO`; everything else → `BANK`.
- [ ] Total capital, Available, balances, valued amounts, `Not valued`, and
      `protected` derive only from `/api/v1/accounts/summary` and use separate
      non-wrapping value/currency elements.
- [ ] The warning is hidden only with no unvalued assets and opens the shared
      Set-a-rate entry point owned by T-025B.
- [ ] Account details, Add/Edit, Reconcile, Archive, recent history, and
      `Full history` → account-filtered Transactions are API-backed.
- [ ] Archive uses branded confirmation ending `History is kept.` and does not
      promise restoration. Permission-driven actions are absent when denied.
- [ ] Mobile has no restoration, ownership transfer, category management or
      automatic-rate implementation in this task.
- [ ] Desktop account fields/cards, account-filtered history, permissions and
      existing Account behavior remain functional.
- [ ] No backend/schema or other feature-screen work is added.

## Touches

`app/static/index.html`, `app/static/app.js`, `app/static/style.css`,
`tests/test_mobile_accounts_ui_v21.py`, `tests/test_frontend_v2.py`, design notes,
and task lifecycle evidence.

## Out of scope

Profile, categories, rate form, sharing/invitations and logout (T-025B);
Transactions composition, Operations/periods, Plan/Analytics, backend/schema,
T-015/T-016/T-017.

## Verification

```bash
.venv/bin/python -m pytest -q tests/test_mobile_accounts_ui_v21.py tests/test_frontend_v2.py tests/test_foundation_v2.py tests/test_valuation_v2.py tests/test_phase12_privacy_v2.py
node --check app/static/app.js
git diff --check
```

Use `verify` for normal/many/empty Accounts and all named lifecycle flows at
390×844, plus preserved Accounts behavior at 1280×900.

## Review

Append the bounded independent implementation review following the protocol.

## Session log

- 2026-08-12 Codex GPT-5: split from overloaded T-025 after readiness review;
  not claimed.
