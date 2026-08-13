---
id: T-030A
title: Pass the core iPhone 15 mobile acceptance matrix
status: backlog
size: M
spec: design/Finnapp mobile specification/spec/01-foundations.md through spec/06-content.md; spec/08-acceptance.md scoped to Accounts, Transactions, and Operations
blocked-by: [T-029]
branch: task/T-030A-mobile-acceptance
base-commit:
implementer:
readiness-reviewed-by:
readiness-reviewed-commit:
readiness-verdict: pending re-review after owner scope reduction
---

## Goal

Fast-track Accounts, Transactions, and Operations to a usable, stable mobile
finish on an iPhone 15 Safari reference viewport. Keep Plan, Analytics, and
desktop verification out of this task without changing their current code.

## Acceptance

- [ ] Every applicable Accounts, Transactions, and Operations item in
      `spec/08-acceptance.md` has pass/fail, expected/observed value,
      verification method, and screenshot/evidence name in this task.
- [ ] The primary browser matrix runs at the iPhone 15 CSS viewport `393×852`;
      a bounded `390×844` compatibility smoke preserves the design reference.
- [ ] Empty, populated and long-list Accounts/Transactions states pass.
- [ ] All Operations modes, active/absent period, invalid/above-Available,
      account switch, real software keyboard Transfer, and Saved pass.
- [ ] Mobile persistent Undo is verified with candidate present, branded
      confirmation, soft-void refresh, disappearance, reload persistence, and
      no fallback to an older transaction; shared roles and owner-only quote
      presentation are included.
- [ ] Every concrete sheet, nested picker return, swipe state and branded
      destructive/success confirmation reachable from these three sections
      passes.
- [ ] Measurements prove 700px content, 96px cards, target/type minima,
      non-wrapping tabular money/separate currency, and only permitted scrolls.
- [ ] Copy matches `spec/06`; `DESIGN-NOTES.md` and ADR-0010/0011 corrections
      override older exported fixtures.
- [ ] Contrast and reduced motion pass; console and network contain no
      unexplained errors.
- [ ] Transactions keeps the bottom tab bar visible while the feed scrolls and
      excludes planned occurrences from All/Income/Expense/Transfer; planned
      rows appear only after explicitly selecting Planned.
- [ ] Core-section sheets use the specified available sheet height, keep all
      rows and actions readable, and do not appear vertically clipped above the
      tab bar.
- [ ] Focusing text, numeric, date, or textarea controls in iPhone Safari does
      not trigger automatic page zoom; user-initiated pinch zoom remains
      available.
- [ ] Every recorded core-mobile preview P2/P3 is enumerated; all core-mobile
      P0–P2 are resolved before this task is accepted.
- [ ] Fixes are mobile-bounded and do not change backend or invent desktop UI.

## Touches

Frontend files only for bounded mobile corrections,
`tests/test_phase15_mobile_acceptance.py`, `tests/test_frontend_v2.py`, this task
and relevant progress evidence.

## Out of scope

Backend/schema/API changes, desktop redesign or regression checks, Plan,
Analytics, deferred product capabilities, phase acceptance or task archival.

## Verification

```bash
.venv/bin/python -m pytest -q tests/test_frontend_v2.py tests/test_phase15_interactions.py tests/test_phase15_mobile_acceptance.py
node --check app/static/app.js
git diff --check
```

Use `verify` with one fresh authenticated iPhone 15 `393×852` scratch matrix
plus a bounded `390×844` compatibility smoke; a single happy-path screenshot
is not sufficient evidence. Do not run a desktop matrix in this task.

## Review

Append the bounded independent implementation review following the protocol.

## Session log

- 2026-08-12 Codex GPT-5: task split from former L-sized T-030; not claimed.
- 2026-08-12 Codex GPT-5: mobile Undo and shared-role matrix added after review;
  limited independent re-review verdict `ready`.
- 2026-08-13 repository owner: narrowed the fast-track to Accounts,
  Transactions, and Operations on iPhone 15; explicitly deferred Plan,
  Analytics, and desktop verification. Supplied Safari evidence records a
  missing tab bar on the long Transactions feed, planned rows in `All`, clipped
  sheets, and focus-triggered page zoom.
