---
id: T-029
title: Integrate navigation, keyboard, motion, and accessibility
status: backlog
size: M
spec: design/Finnapp mobile specification/spec/05-interactions.md; spec/08-acceptance.md
blocked-by: [T-025B, T-026, T-027B, T-028]
branch: task/T-029-navigation-accessibility
base-commit:
implementer:
readiness-reviewed-by:
readiness-reviewed-commit:
readiness-verdict:
---

## Goal

Connect the implemented screens into one accessible mobile interaction graph
without changing backend contracts or feature geometry.

## Acceptance

- [ ] Every permitted tap-map and sheet-graph transition works; deferred Type
      conversion/category merge-delete/restoration controls remain absent.
- [ ] Tab switch closes overlays; scrim/close/Escape dismiss; nested Choose
      returns to its parent; focus is contained and restored to opener.
- [ ] Sheets/dialogs expose correct accessible names/modal semantics, visible
      focus and keyboard operation; all actions work without a pointer.
- [ ] Device/browser software keyboard opens for native amount/note fields,
      clears on Done/segment switch, does not create forbidden screen scroll,
      and Transfer Save has ≥80px visible clearance in the 250px reference
      visual-viewport state. No custom keyboard is built.
- [ ] Sheet motion is ≤180ms and reduced-motion removes transforms without
      hiding content.
- [ ] Targets are ≥44px; chips sit in 44px lanes; console is clean.
- [ ] The entire runtime contains no native `<select>` and no calls to
      `alert`, `confirm`, or `prompt`; supported desktop actions use the shared
      accessible primitives rather than disappearing.
- [ ] Regression tests cover graph/state/focus and forbidden APIs.
- [ ] After acceptance, progress may say `preview-ready` but must still say
      Phase 15 is active/unaccepted under ADR-0011.

## Touches

`app/static/index.html`, `app/static/app.js`, `app/static/style.css`,
`tests/test_frontend_v2.py`, `tests/test_phase15_interactions.py`, design notes,
and task lifecycle/progress evidence.

## Out of scope

Full pixel matrix, desktop redesign, backend/schema/API changes,
T-015/T-016/T-017, Analytics/Scan implementation, custom keyboard.

## Verification

```bash
.venv/bin/python -m pytest -q tests/test_frontend_v2.py tests/test_phase15_interactions.py
node --check app/static/app.js
! rg -n '<select|window\.(alert|confirm|prompt)\(' app/static
git diff --check
```

Use `verify` on a fresh DB for the full navigation graph, native software
keyboard/focus/reduced-motion/console at 390×844 and desktop action reachability.

## Review

Append the bounded independent implementation review following the protocol.

## Session log

- 2026-08-12 Codex GPT-5: integration task specified for batch readiness; not
  claimed.
