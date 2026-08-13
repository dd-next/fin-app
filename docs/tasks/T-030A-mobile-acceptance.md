---
id: T-030A
title: Pass the core iPhone 15 mobile acceptance matrix
status: review
size: M
spec: design/Finnapp mobile specification/spec/01-foundations.md through spec/06-content.md; spec/08-acceptance.md scoped to Accounts, Transactions, and Operations
blocked-by: [T-029]
branch: task/T-030A-mobile-acceptance
base-commit: 867f87e3282300c76989ccf25ab23c0cda62966e
implementer: /root, Codex GPT-5
readiness-reviewed-by: /root/t030a_core_readiness, Codex GPT-5 same-vendor fallback
readiness-reviewed-commit: 36fa32a3676cf66ecb8e5c5588cd6bcbfae62756
readiness-verdict: ready
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
- [x] Transactions keeps the bottom tab bar visible while the feed scrolls and
      excludes planned occurrences from All/Income/Expense/Transfer; planned
      rows appear only after explicitly selecting Planned.
- [x] `All` is a lossless frontend drain over the existing
      `/api/v1/transaction-feed?filter=all` financial-date feed and its opaque
      cursor: successive mixed source pages are consumed until 50 persisted
      rows have been collected or the source cursor is exhausted, and planned
      rows are never rendered. Each source request uses the number of visible
      rows still needed, so no persisted overflow buffer is lost. Income/
      Expense/Transfer/Planned keep using their accepted feed filters; no
      backend/API contract changes.
- [x] Core-section sheets span the viewport width, extend through the tab bar
      to the bottom safe edge, and cover the tab bar while open. Option rows and
      hairlines fill the available body width; long bodies scroll without
      clipping the header, footer, or actions. Scrim, close, Escape and
      programmatic tab switching still close the stack; a physical tab tap is
      unavailable while a core sheet covers it. The shared Plan/Profile/
      Settings overlay appearance remains unchanged.
- [ ] Focusing text, numeric, date, or textarea controls in iPhone Safari does
      not trigger automatic page zoom; user-initiated pinch zoom remains
      available.
- [x] In-scope editable `input`/`textarea` controls have computed font size
      `>=16px` as an owner-approved mobile exception to the frozen 15px field
      value. The viewport meta keeps `initial-scale=1` and does not add
      `maximum-scale` or `user-scalable=no`.
- [ ] Every recorded core-mobile preview P2/P3 is enumerated; all core-mobile
      P0–P2 are resolved before this task is accepted.
- [x] Fixes are mobile-bounded and do not change backend or invent desktop UI.

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
- Final limited re-review, transcribed verbatim:

> No P0–P3 findings.
>
> The remaining lossless-All P1 is closed. T-030A now requires `All` to drain successive pages from the accepted financial-date `/api/v1/transaction-feed?filter=all`, retain its opaque source cursor, discard planned projections only after each source page, and continue until 50 persisted rows are collected or the source is exhausted. Shrinking each source request to the remaining visible capacity prevents an untracked persisted overflow buffer. The required plan-heavy and corrected-financial-date multi-page coverage makes the formerly missing ordering/pagination invariant testable without backend changes.
>
> Verdict: **READY**. Exact reviewed task-file commit: `36fa32a3676cf66ecb8e5c5588cd6bcbfae62756`.

### Bounded implementation review — 2026-08-13

- Reviewer: `/root/t030a_core_impl_review`, Codex GPT-5 fresh same-vendor
  fallback; cross-vendor review was unavailable. Read-only; no repository files
  or Git state changed.
- Reviewed range: base `ac95842f` plus the uncommitted implementation manifest
  in `app/static/`, `docs/design/DESIGN-NOTES.md`, and the focused frontend
  tests named by this task.
- Initial verdict: changes requested; no P0/P3 findings. Findings, transcribed
  verbatim from the reviewer handoff:

> (1) P1 desktop/out-of-scope regression: index.html moves `#primary-nav` from inside `#app-shell` before views to a sibling after all views (index.html 220-228), while desktop CSS keeps `.primary-nav` static (style.css 126-130). At >640px nav therefore renders after the page content, materially changing/breaking desktop/Plan/Analytics despite explicit no-desktop/no-Plan/Analytics-change scope. Must preserve desktop DOM/layout while isolating mobile fixed-nav remedy.
>
> (2) P1 cross-domain overlay exclusion: default `coverTabBar` derives from `state.activeView` (app.js 553-570, 646-650). `openMobileRateSettings` has no `coverTabBar:false` (2731ff), and Accounts missing-rate warning opens it directly without Profile parent (1852ff), so this Settings/Rate sheet now inherits core/full-bottom geometry, violating explicit Profile/Settings/Plan prior-geometry requirement.
>
> (3) P2 missing meaningful pagination test: new tests only substring-inspect helper (tests/test_phase15_mobile_acceptance.py 48-67 and test_mobile_transactions...), but task explicitly requires plan-heavy multi-page and corrected-financial-date/cursor coverage. No executable/mock/API-sequence test proves request limits/cursors, 50 persisted collection, source exhaustion, append continuity/order, or explicit Planned unchanged.

- Resolution: restored the original desktop nav DOM position and introduced
  mobile-only runtime reparenting; added explicit non-covering geometry to the
  Profile, Categories, Rate and Plan root/confirmation paths; and added an
  executable Node test of the real feed helper covering plan-heavy `50 -> 48 ->
  1` requests, opaque cursors, 50-row stable order, append continuity, source
  exhaustion and explicit Planned pass-through.
- Final limited re-review, transcribed verbatim:

> Limited re-review complete: all three prior findings are closed; no residual P0–P3. Desktop P1 closed by restoring nav to original DOM location and mobile-only runtime reparenting, with desktop restoration before page-loading. Settings/Rate P1 closed: Profile, Categories, Rate root sheets and post-close Rate Saved confirmations explicitly retain coverTabBar:false; nested flows inherit it. Pagination P2 closed by executable Node test covering plan-heavy 50→48→1 requests, opaque cursors, 50 persisted/order, append continuity, explicit Planned pass-through, and exhaustion. Re-ran focused gate: 72 passed; node --check and git diff --check pass. Verdict READY for this bounded implementation block; actual iPhone/WebKit acceptance remains separate.

## Verification evidence — 2026-08-13

The automated and scratch-browser implementation gates pass. The browser
evidence below used a disposable migrated SQLite database in
`/private/tmp/finapp-t030a.DWLtA1/finapp.db`; `finapp.db` was not touched.

| Evidence | Expected | Observed | Method / evidence name |
|---|---|---|---|
| Focused gate | all focused suites pass | `72 passed in 0.29s` | exact task pytest command, `focused-72` |
| JavaScript / diff | syntax and whitespace clean | both passed | `node-check`, `diff-check` |
| Accounts shell | fixed tab bar; no horizontal overflow | nav `796..852`; overflow `0` | 393×852 IAB, `accounts-shell-393` |
| Core Purpose sheet | full width and covers tab bar | width `393`; bottom `852`; nav begins `796`; covered | `accounts-purpose-core-sheet-393` |
| Account text focus | 16px; viewport scale remains 1 | `16px`; scale `1 -> 1`; width `393 -> 393` | `account-name-focus-393` |
| Transactions long feed | 50 persisted All rows; no Planned; fixed nav throughout | 50 rows, 0 planned; nav `796..852` at scroll `0`, `1700`, `2598` | 60 persisted spends plus one plan occurrence, `transactions-top-mid-end-393` |
| Explicit Planned | planned occurrence remains accessible only in Planned | one row, one Planned pill, title `Should only be Planned` | `transactions-planned-explicit-393` |
| Operations | both cards are 96px; no horizontal/page overflow | `96`, `96`; shell `796/796`; overflow `0` | `operations-shell-393` |
| Operations textarea focus | 16px; viewport scale remains 1 | `16px`; scale `1 -> 1`; width `393 -> 393` | `operations-note-focus-393` |
| 390×844 compatibility | same bounded shell geometry | cards `96`, `96`; nav `788..844`; shell `788/788`; overflow `0` | `operations-compat-390` |
| Browser console | no unexplained warnings/errors in exercised flows | `0` warnings/errors | `console-final` |

The available in-app browser was used for deterministic layout and behavior
checks, but it is not recorded as WebKit and therefore does not replace the
task's required actual iPhone 15 Safari evidence. Repository-owner device
acceptance remains pending for: visual/layout viewport scale before and after
text, numeric, date and textarea focus; keyboard dismissal; user pinch zoom;
expanded/collapsed Safari toolbar; and tab-bar bounds at the top, middle and end
of the long Transactions feed. Until that evidence exists, the unchecked full
matrix and real-Safari acceptance items above are intentionally not claimed.

## Session log

- 2026-08-12 Codex GPT-5: task split from former L-sized T-030; not claimed.
- 2026-08-12 Codex GPT-5: mobile Undo and shared-role matrix added after review;
  limited independent re-review verdict `ready`.
- 2026-08-13 repository owner: narrowed the fast-track to Accounts,
  Transactions, and Operations on iPhone 15; explicitly deferred Plan,
  Analytics, and desktop verification. Supplied Safari evidence records a
  missing tab bar on the long Transactions feed, planned rows in `All`, clipped
  sheets, and focus-triggered page zoom.
- 2026-08-13 repository owner promoted the readiness-clean task to `todo` on
  accepted integration `867f87e`; `/root`, Codex GPT-5 atomically claimed
  `task/T-030A-mobile-acceptance` from that exact base and started only the
  owner-scoped core iPhone 15 fast-track.
- 2026-08-13 `/root`, Codex GPT-5: implemented and independently re-reviewed
  the bounded core fixes. The focused 72-test, JavaScript and diff gates pass;
  disposable 393×852 and 390×844 browser checks pass for the reported bugs,
  geometry, focus scale and console. T-030A is in review with no P0–P3 code
  finding; actual iPhone 15 Safari/device evidence remains for owner acceptance.
