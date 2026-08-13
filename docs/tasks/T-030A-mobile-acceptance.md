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
      destructive/success confirmation in this catalogue passes: Add/Edit/
      Account details, Reconcile, Share, Switch account, Filters, persisted
      Transaction details/Edit/Assign/Delete, Start/Active/Edit period, Period
      history, their nested Account/Storage/Purpose/Asset/Category/Date/
      Destination choices, Close/Archive confirmations, and Saved.
      Profile/Categories/Rates and Plan-item/Plan-link entry points are checked
      only to remain present and unchanged; their downstream flows are not
      exercised or modified.
- [ ] Measurements prove 700px content, 96px cards, target/type minima,
      non-wrapping tabular money/separate currency, and only permitted scrolls.
- [ ] Copy matches `spec/06`; `DESIGN-NOTES.md` and ADR-0010/0011 corrections
      override older exported fixtures.
- [ ] Contrast and reduced motion pass; console and network contain no
      unexplained errors.
- [ ] Transactions keeps the bottom tab bar visible while the feed scrolls and
      excludes planned occurrences from All/Income/Expense/Transfer; planned
      rows appear only after explicitly selecting Planned.
- [ ] `All` is a lossless frontend drain over the existing
      `/api/v1/transaction-feed?filter=all` financial-date feed and its opaque
      cursor: successive mixed source pages are consumed until 50 persisted
      rows have been collected or the source cursor is exhausted, and planned
      rows are never rendered. Each source request uses the number of visible
      rows still needed, so no persisted overflow buffer is lost. Income/
      Expense/Transfer/Planned keep using their accepted feed filters; no
      backend/API contract changes.
- [ ] Core-section sheets span the viewport width, extend through the tab bar
      to the bottom safe edge, and cover the tab bar while open. Option rows and
      hairlines fill the available body width; long bodies scroll without
      clipping the header, footer, or actions. Scrim, close, Escape and
      programmatic tab switching still close the stack; a physical tab tap is
      unavailable while a core sheet covers it. The shared Plan/Profile/
      Settings overlay appearance remains unchanged.
- [ ] Focusing text, numeric, date, or textarea controls in iPhone Safari does
      not trigger automatic page zoom; user-initiated pinch zoom remains
      available.
- [ ] In-scope editable `input`/`textarea` controls have computed font size
      `>=16px` as an owner-approved mobile exception to the frozen 15px field
      value. The viewport meta keeps `initial-scale=1` and does not add
      `maximum-scale` or `user-scalable=no`.
- [ ] Every recorded core-mobile preview P2/P3 is enumerated; all core-mobile
      P0–P2 are resolved before this task is accepted.
- [ ] Fixes are mobile-bounded and do not change backend or invent desktop UI.

## Touches

Frontend files only for bounded mobile corrections,
`tests/test_phase15_mobile_acceptance.py`, focused existing frontend tests,
`docs/design/DESIGN-NOTES.md`, this task and relevant progress evidence. Design
notes may record only these owner-approved corrections: core overlays cover the
tab bar, All drains the existing mixed feed without rendering planned rows, and
in-scope editable controls use at least 16px to prevent iPhone Safari auto-zoom.

## Out of scope

Backend/schema/API changes, desktop redesign or regression checks, Plan,
Analytics, deferred product capabilities, phase acceptance or task archival.

## Verification

```bash
.venv/bin/python -m pytest -q tests/test_frontend_v2.py tests/test_phase15_interactions.py tests/test_phase15_mobile_acceptance.py tests/test_mobile_accounts_ui_v21.py tests/test_mobile_transactions_ui_v21.py tests/test_mobile_operations_ui_v21.py tests/test_mobile_periods_ui_v21.py tests/test_phase15_shell.py tests/test_phase15_primitives.py tests/test_phase15_overlays.py
node --check app/static/app.js
git diff --check
```

Use `verify` with one fresh authenticated iPhone 15 `393×852` scratch matrix
plus a bounded `390×844` compatibility smoke; a single happy-path screenshot
is not sufficient evidence. Use WebKit for the automated primary matrix. Final
device evidence must come from actual iPhone 15 Safari and record visual/
layout viewport scale before and after text, numeric, date and textarea focus,
keyboard dismissal, pinch-zoom availability, and tab-bar bounds at the top,
middle and end of a long Transactions feed with the Safari toolbar expanded
and collapsed. Do not run a desktop matrix in this task.

## Review

Append the bounded independent implementation review following the protocol.

### Scope-reduction readiness review — 2026-08-13

- Reviewer: `/root/t030a_core_readiness`, Codex GPT-5 fresh same-vendor
  fallback; cross-vendor review was unavailable. Read-only; no files or Git
  state changed.
- Reviewed task-file commit: `6c9be0a4a9c1de9de293e708417f70dfba18edc5`.
- Verdict: not ready; no P0/P3 findings, three P1 and two P2 findings.
- Resolution: the task now explicitly authorizes and bounds the core-only
  overlay design correction; defines the lossless mixed-feed drain without
  backend/API changes; freezes the 16px editable-control exception and actual
  iPhone Safari evidence; enumerates the in-scope sheet catalogue; and includes
  all focused core mobile regression suites. Full findings are preserved in the
  reviewer response for this session and will be transcribed verbatim into the
  implementation evidence before task completion.
- First limited re-review: four findings closed; one P1 remained because the
  proposed `/transactions` adapter did not preserve the accepted financial-date
  ordering across cursor boundaries. Resolution: `All` now explicitly drains
  the accepted mixed feed using its opaque cursor and a shrinking requested
  limit, discarding planned projections only after each source page while
  retaining every persisted row in stable feed order. Plan-heavy interleaving
  and corrected financial dates across multiple pages are required coverage.

## Session log

- 2026-08-12 Codex GPT-5: task split from former L-sized T-030; not claimed.
- 2026-08-12 Codex GPT-5: mobile Undo and shared-role matrix added after review;
  limited independent re-review verdict `ready`.
- 2026-08-13 repository owner: narrowed the fast-track to Accounts,
  Transactions, and Operations on iPhone 15; explicitly deferred Plan,
  Analytics, and desktop verification. Supplied Safari evidence records a
  missing tab bar on the long Transactions feed, planned rows in `All`, clipped
  sheets, and focus-triggered page zoom.
