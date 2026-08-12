---
id: T-023
title: Import approved tokens and responsive mobile shell
status: todo
size: M
spec: design/Finnapp mobile specification/spec/01-foundations.md; spec/02-components.md Tab bar; spec/05-interactions.md
blocked-by: [T-022]
branch: task/T-023-mobile-shell
base-commit:
implementer:
readiness-reviewed-by: /root/phase15_readiness_review, Codex GPT-5 same-vendor fallback
readiness-reviewed-commit: deb8a5a
readiness-verdict: ready
---

## Goal

Establish the token-backed, safe-area-aware 390×844 mobile frame and five-tab
navigation while preserving the authenticated desktop shell and all existing
backend behavior.

## Acceptance

- [ ] Runtime CSS copies only tokens actually used from the frozen token
      sources; runtime does not load `docs/`, webfonts, icon packs, component
      libraries, or a frontend build tool.
- [ ] Viewport metadata includes `viewport-fit=cover`; production safe-area
      variables use `env()`, the shell uses `100dvh` with a safe fallback, and
      reference test variables can inject 54px top/34px bottom bands.
- [ ] At 390×844 the injected reference bands leave exactly 700px of content
      above the 56px tab bar; content is not covered and no horizontal overflow
      exists.
- [ ] The five tabs are exactly Accounts `▤`, Transactions `⇄`, Operations `◎`,
      Plan `◇`, Analytics `ϟ`, in that order, with ≥44px targets, approved
      active/idle colors, and accessible current/selected state.
- [ ] Switching tabs preserves the existing view behavior and does not mutate
      or refetch financial data solely because the shell changed.
- [ ] At 1280×900 the current top bar, navigation, five views, dialogs, auth and
      invitation flow remain reachable and functional.
- [ ] No backend, route, schema, migration, permission, ledger, or money
      formatting behavior changes.
- [ ] `DESIGN-NOTES.md` records the exact runtime tokens and shell rules landed.

## Touches

`app/static/index.html`, `app/static/style.css`, narrowly scoped navigation code
in `app/static/app.js`, `tests/test_frontend_v2.py`,
`tests/test_phase15_shell.py`, `docs/design/DESIGN-NOTES.md`, and this task's
lifecycle evidence.

## Out of scope

Screen-specific lists/forms; primitive rows/cards/fields; sheets, pickers,
confirmations, keyboard behavior; removal of existing native controls; auth
redesign; backend/API/schema work.

## Verification

```bash
.venv/bin/python -m pytest -q tests/test_frontend_v2.py tests/test_phase15_shell.py
node --check app/static/app.js
git diff --check
```

Use the updated `verify` skill against a fresh scratch database for authenticated
390×844 and 1280×900 checks: content/safe-area measurements, overflow, tab
order/state/switching, every view, auth/invitation reachability, and console.

## Review

Append the bounded independent implementation review following
[`../REVIEW_PROTOCOL-v2.md`](../REVIEW_PROTOCOL-v2.md).

## Session log

- 2026-08-12 Codex GPT-5: task specified in the Phase 15 fast-track preparation;
  implementation has not been claimed.
- 2026-08-12 Codex GPT-5: independent batch readiness review and limited
  re-review closed all P0–P2; owner promotion to `todo` recorded.
