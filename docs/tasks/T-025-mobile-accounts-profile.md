---
id: T-025
title: Implement mobile Accounts and Profile flows
status: backlog
size: M
spec: design/Finnapp mobile specification/spec/03-screens.md §3.1; spec/04-sheets.md; spec/05-interactions.md; spec/06-content.md
blocked-by: [T-024B]
branch: task/T-025-mobile-accounts-profile
base-commit:
implementer:
readiness-reviewed-by:
readiness-reviewed-commit:
readiness-verdict:
---

## Goal

Make Accounts and its account, Profile, category, manual-rate, logout, and
sharing flows usable at 390×844 through accepted APIs while preserving desktop.

## Acceptance

- [ ] Mobile Accounts implements the exact 44px header, 72px single-surface
      capital strip, optional 44px rate warning, storage groups, 64px rows,
      56px New account row, permitted long-list scroll, and exact empty state.
- [ ] Every visible account appears once: cash storage → `CASH`; crypto
      asset/storage → `CRYPTO`; everything else → `BANK`.
- [ ] Total capital, Available, balances, valued amounts, `Not valued`, and
      `protected` derive only from `/api/v1/accounts/summary` and use separate
      non-wrapping value/currency elements.
- [ ] The warning is hidden only with no unvalued assets and otherwise opens
      Set a rate.
- [ ] Account details, Add/Edit, Reconcile, Share, Archive, recent history, and
      `Full history` → account-filtered Transactions are API-backed.
- [ ] Archive uses branded confirmation ending `History is kept.` and does not
      promise restoration.
- [ ] Profile exposes categories, exchange rates, workspace information, and
      branded logout; identity/password editing is absent.
- [ ] Supported category create/rename/archive remains usable; merge/delete is
      absent under T-016.
- [ ] Set a rate uses Asset→Main pair, `Manual value`, disabled
      `Auto · Coming soon`, exact Decimal-string input, accepted rate endpoint,
      then refreshes totals/warning.
- [ ] Share preserves Viewer/Contributor/Editor behavior, invitation links,
      visible disabled `Owner · Coming soon`, and permission-driven controls.
- [ ] Logout uses the existing server endpoint and exact corrected copy.
- [ ] Desktop account fields/cards, sharing, categories, rates, history and
      permissions remain functional.
- [ ] No backend/schema, restoration, owner transfer, automatic rates,
      category merge/delete, or other feature-screen work is added.

## Touches

`app/static/index.html`, `app/static/app.js`, `app/static/style.css`,
`tests/test_mobile_accounts_ui_v21.py`, `tests/test_frontend_v2.py`, design notes,
and task lifecycle evidence.

## Out of scope

Transactions composition, Operations/periods, Plan/Analytics, backend/schema,
T-015/T-016/T-017, automatic rate sources, ownership transfer.

## Verification

```bash
.venv/bin/python -m pytest -q tests/test_mobile_accounts_ui_v21.py tests/test_frontend_v2.py tests/test_foundation_v2.py tests/test_sharing_v2.py tests/test_valuation_rate_direction_v21.py tests/test_valuation_v2.py
node --check app/static/app.js
git diff --check
```

Use `verify` for normal/many/empty Accounts and all named flows at 390×844,
plus preserved Accounts/Profile behavior at 1280×900.

## Review

Append the bounded independent implementation review following the protocol.

## Session log

- 2026-08-12 Codex GPT-5: task specified for batch readiness; not claimed.
