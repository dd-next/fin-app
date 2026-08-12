---
id: T-027A
title: Implement the mobile Operations action surface
status: backlog
size: M
spec: design/Finnapp mobile specification/spec/03-screens.md §3.3; spec/05-interactions.md; spec/06-content.md
blocked-by: [T-024B]
branch: task/T-027A-mobile-operations
base-commit:
implementer:
readiness-reviewed-by:
readiness-reviewed-commit:
readiness-verdict:
---

## Goal

Implement compact mobile Spend, Add funds, Transfer, and Scan with exact
financial commands and Saved handling, leaving period lifecycle to T-027B.

## Acceptance

- [ ] Operations has no header, uses `padding:8px 16px 0`, two 96px card slots,
      exact 44px selector and §3.3 vertical budgets.
- [ ] First visit is Spend; selected mode/account persist per user and stale or
      inaccessible saved accounts fall back safely.
- [ ] Account card opens Switch account; changing it refreshes every dependent
      value and currency without stale responses winning.
- [ ] Spend/Add funds use accepted endpoints. Category defaults to accessible
      Groceries/Salary when present, otherwise Uncategorized.
- [ ] Transfer accepts one source amount and destination, executes a Phase 14
      quote, never requests target amount, and performs no client float/rate
      calculation.
- [ ] Amount/Category/Date/Destination/Note use T-024A/T-024B controls. Invalid/zero
      amount blocks Save; exceeding Available today does not.
- [ ] Submit and Scan copy match spec exactly; Scan performs no OCR.
- [ ] Successful saves show exact branded dynamic Saved copy. Done clears
      amount/note/destination, retains mode/account, and refreshes account,
      allowance and Undo state.
- [ ] When the server returns an Undo candidate, a compact 44×44 mobile Undo
      affordance appears in the account card top row without changing either
      96px card. It uses branded confirmation and the accepted server command,
      soft-voids the candidate, refreshes affected values, disappears, survives
      reload, and never falls back to an older transaction after consumption.
- [ ] Account switching remains a separate semantic control from Undo. There is
      never more than one visible candidate for the selected account.
- [ ] Spend/Add funds controls and targets reflect existing account roles;
      denied mutations remain unavailable or show the server-derived error.
      Quote-based mobile Transfer is owner-only and neither offers inaccessible
      targets nor calls quote/execute for a non-owner. Viewer, contributor,
      editor, and owner states do not leak hidden accounts or owner-private
      rate/quote data.
- [ ] Operations works without a period. T-027A supplies a stable 96px
      period-card host/loading/error interface but no lifecycle forms.
- [ ] Desktop explicit exchange, optional fee, persistent Undo and richer forms
      remain functional.
- [ ] No period mutation, backend/schema, fake rate, OCR, history list, or
      desktop redesign is added.

## Touches

`app/static/index.html`, `app/static/app.js`, `app/static/style.css`,
`tests/test_mobile_operations_ui_v21.py`, `tests/test_frontend_v2.py`, design
notes, and task lifecycle evidence.

## Out of scope

Period lifecycle/details/history, backend/API/schema, custom keyboard, other
screens, removal of desktop Undo/exchange/fee behavior.

## Verification

```bash
.venv/bin/python -m pytest -q tests/test_mobile_operations_ui_v21.py tests/test_frontend_v2.py tests/test_operations_v2.py tests/test_operations_undo_v2.py tests/test_transfer_quotes_v21.py tests/test_transfer_quote_execution_v21.py tests/test_valuation_rate_direction_v21.py
node --check app/static/app.js
git diff --check
```

Use `verify` for all modes, same/cross-asset transfer, invalid/zero/overspend,
Saved reset, no-period, Scan, persistent Undo before/after reload, and
viewer/contributor/editor/owner role states at 390×844; preserve desktop at
1280×900.

## Review

Append the bounded independent implementation review following the protocol.

## Session log

- 2026-08-12 Codex GPT-5: task split from former L-sized T-027; not claimed.
