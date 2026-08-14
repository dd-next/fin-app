---
id: T-030A
title: Pass the core iPhone 15 mobile acceptance matrix
status: in-progress
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

## Round 2 — owner iPhone Safari findings, 2026-08-14

Reported by the repository owner from actual iPhone Safari with annotated
screenshots, together with a replaced design specification (see the conflict
note below). Numbering follows the owner's list; screenshot names are the
owner's originals in reporting order.

| # | Screen / surface | Expected | Observed | Authority |
|---|---|---|---|---|
| 1 | Accounts → Profile sheet | The sheet and scrim cover the whole frame | Bottom tab bar stays visible below the sheet | `spec/02` bottom sheet `bottom:0`, scrim "covers the whole frame" |
| 2 | Categories → Edit category sheet | Secondary `Cancel` outlined, no fill; tab bar covered | `Cancel` is accent-filled; tab bar visible | `spec/02` Buttons; `spec/02` bottom sheet |
| 3 | Transactions → swiped row | Both swipe actions fully revealed | `Plan` action is clipped and reads narrower than `Delete` | `spec/05` swipe |
| 4 | Operations → account card | Undo sits in the **period** card top line, 26×26 `↺`, left of `›` | Undo sits in the account card, top-right | `spec/02` period card; `spec/05` Undo |
| 5 | Active period sheet | Secondary `View history` outlined | Accent-filled | `spec/02` Buttons |
| 6 | Period history sheet | Secondary `Edit` outlined | Accent-filled | `spec/02` Buttons |
| 7 | Transaction details sheet | Secondary `Delete` outlined | Accent-filled | `spec/02` Buttons |
| 8 | Active period sheet | Secondary `View history` outlined | Accent-filled (duplicate of 5) | `spec/02` Buttons |
| 9 | Operations → segmented control | 44px control, four equal 38px segments, single-line labels | Segments overflow the control and `Add funds` wraps, so the active pill sits crooked | `spec/03` §3.3 segmented control 44px |
| 10 | Operations → segmented control | Active segment pill aligned inside the track | Same defect isolated on the active `Add funds` segment | `spec/03` §3.3 |
| 11 | Operations → Transfer | `Choose destination` occupies the Category slot beside Date; no extra row and no category field | Destination is a full-width row above Amount | updated `spec/03` §3.3 |
| 12 | Operations → account card | Duplicate of 4 | Duplicate of 4 | `spec/05` Undo |
| 13 | Edit period sheet | Secondary `Cancel` outlined | Accent-filled | `spec/02` Buttons |
| 14 | Any field, iPhone Safari | Focus never rescales the page, on any field | Safari auto-zooms on focus; only core-overlay textareas were previously raised to 16px | `spec/03` "never resizes or scrolls the screen" |
| 15 | Account details sheet | Secondary `Share` outlined | Accent-filled | `spec/02` Buttons |
| 16 | Accounts / Analytics header | Avatar tile carries a 10px accent dot | Empty tile, no dot | `spec/02` screen header |

Findings 2, 5, 6, 7, 8, 13 and 15 share one root cause: the base `button` rule
fills with the accent colour and `.mobile-button-secondary` never declares a
`background`, so every sheet secondary inherits the primary fill.

### Design specification replacement — conflict note

The owner replaced `docs/design/Finnapp mobile specification/` in the working
tree and kept the previously accepted copy as
`docs/design/Finnapp mobile specification old version/`. That backup folder is
byte-identical to `HEAD` for all eight `spec/*.md` files, so the working tree
holds the new authority.

The replacement carries the two corrections the owner reported (findings 4/12
period-card `↺`, and finding 11 Destination in the Category slot). It also
reverts settled Phase 14 decisions that no reported finding depends on:

- `spec/05` and `spec/08` reintroduce a hard block on amounts above
  `Available today`. The accepted backend contract makes Available today
  informational and keeps such an expense valid.
- `spec/04` drops the `Redistribute remaining days` checkbox that T-005/T-006
  implemented and the owner accepted.
- `spec/07` reopens the allowance formula as an `OPEN — confirm before
  implementing` question that Phase 14 already closed.
- `spec/04`/`06` drop the Plan `Skip` action, the dynamic `To account` /
  `From account` label, and the disabled `Owner` / `Auto · Coming soon`
  options that ADR-0010 requires.
- `AGENTS.md` demotes `Finapp Screen.dc.html` from final visual source back to
  `Finapp Mobile Redesign.dc.html`, contradicting `design/DESIGN-NOTES.md`.

None of the sixteen findings depends on any of those five points, so all
sixteen are fixed under this task and the reverted areas are left untouched at
their accepted behaviour. The owner has to decide whether the reverts are
intended before anything acts on them.

### Round 2 fixes

| # | Fix | Where |
|---|---|---|
| 1, 2 | The `coverTabBar` opt-out and its `core-overlay` CSS variant are removed; the overlay root is `bottom: 0` for every sheet and confirmation, and the tab-bar `z-index` lifts and safe-band/confirm offsets that compensated for it are deleted | `app.js`, `style.css` |
| 2, 5–8, 13, 15 | `.mobile-button-secondary` declares `background: transparent`, so it stops inheriting the base `button` accent fill | `style.css` |
| 3 | Each row publishes `--mobile-swipe-offset` from its actual action count, and the swiped body translates by that instead of a fixed `-112px` | `app.js`, `style.css` |
| 4, 12 | New `#operations-undo-mobile` in the period card top line: 26×26, `#1B2129`, 8px radius, `z-index: 2` above the card trigger, `::after` restoring a 44px target, `stopPropagation`, hidden with no candidate. `#operations-undo` is hidden on mobile and keeps the desktop control | `index.html`, `app.js`, `style.css` |
| 9, 10 | Segments get an explicit 38px height and `white-space: nowrap`, so the base 44px `min-height` and the wrapped `Add funds` label no longer skew the active pill; `::after` keeps the 44px target | `style.css` |
| 11 | Transfer reorders to Amount → Destination + Date → Note, with Destination in the Category slot and its label visually hidden like its siblings | `index.html`, `style.css` |
| 14 | A single low-specificity `input, textarea, select { font-size: 16px }` inside the mobile block replaces the three view-scoped rules; the 28px amount field keeps its size | `style.css` |
| 16 | The avatar tile paints a measured 10px accent dot through `::before`, immune to the `color: transparent` on `.view-heading > button` | `style.css` |

Asset cache-bust moved `phase15-t030a-1` → `phase15-t030a-3` so the owner's
device reloads both files.

### Round 2b — two further owner corrections, 2026-08-14

| # | Screen | Expected | Observed | Authority |
|---|---|---|---|---|
| 17 | Operations, all save modes | Save writes silently; the form clears, the mode stays and the cards recalculate in place | A **Saved** confirmation with a `Done` button interrupted every save | `spec/03` §3.3, `spec/05` Success, `spec/08` |
| 18 | Operations → Transfer | 10px between the segmented control and the amount field, as in every other mode | Transfer had no gap; the amount field touched the control | `spec/03` §3.3 clearance budget |

`finishMobileOperation` now clears the draft, refreshes and leaves the mode
untouched with no dialog, and its `Saved` copy is deleted; the period card's
`↺` remains the only escape hatch, which is what the updated spec intends.
`#operation-panel-transfer .operations-form` joins the 10px `margin-top` rule.
The repository owner also confirmed on 2026-08-14 that desktop behaviour is
not a priority for this task and must simply keep working.

### Round 2c — the device could not receive any fix

| # | Surface | Expected | Observed | Cause |
|---|---|---|---|---|
| 19 | SPA entry document | A reload after a deploy loads the current `style.css`/`app.js` | The owner's iPhone kept rendering the pre-fix build over a tunnel to a local `uvicorn --reload`, while the same build was correct in the desktop preview | `StaticFiles(html=True)` sends `index.html` with no `Cache-Control`, so iOS Safari caches it heuristically. The asset version tokens live **inside** that document, so bumping them could never reach a device that never re-fetched it. |

`app/main.py` now serves `/` and `/index.html` through an explicit route with
`Cache-Control: no-cache`, so the entry document is always revalidated while
the versioned assets stay cacheable. This is the one change in this task
outside the `Touches` list — it edits a backend file — and it is a static
response header only: no API, schema, contract or behaviour change. Without
it the task's own acceptance criterion of actual iPhone 15 Safari evidence is
unreachable, so it needs owner sign-off as a bounded exception.
`test_spa_entry_document_is_always_revalidated` covers it.

## Round 2 verification evidence — 2026-08-14

Disposable scratch database, fresh Alembic upgrade to `0004_transfer_quotes`,
seeded through the public API. Repository `finapp.db` was never opened.

```text
targeted frontend target (10 files)        72 passed
full pytest                                425 passed in 44.71s
node --check app/static/app.js             passed
git diff --check (app, tests, task docs)   passed
scratch /health                            200 {"status":"ok"}
scratch SPA /                              200 text/html
```

Browser matrix at `393×852`, plus a `390×844` compatibility smoke, measured
from the live DOM:

| Finding | Observed |
|---|---|
| 1, 2 | Profile and Edit category sheets span y 486–852 and 393 wide; tab bar 796–852 fully covered; `navCovered` true in Account details, Transaction details, Active period, Period history and Edit period as well |
| 2, 5–8, 13, 15 | Every footer secondary computes `rgba(0,0,0,0)` fill, `rgba(255,255,255,.12)` border, `rgb(201,208,217)` label, 48px/10px — verified on `Cancel`, `View history`, `Edit`, `Delete`, `Share`, `Save period`'s `Cancel`; primaries stay `rgb(255,162,75)` |
| 3 | Swiped body right edge 377 → 249; `Plan` 249–313 and `Delete` 313–377 both fully revealed at 64px each |
| 4, 12 | Undo 26×26 at x 321–347 inside the period card (202–377), left of the chevron (354–362), `#1B2129`, 8px radius, `z-index 2`; `elementFromPoint` at its centre returns the undo itself; tapping it opens **Undo this operation?** with the spec body and a `#7A2F35` destructive action, and does not open period details; desktop `#operations-undo` computes `display: none` |
| 9, 10 | Four segments at exactly 87×38, x 19/108/198/287, inside the 44px track at y 124–168; single-line labels |
| 11 | Amount 361 wide full row, then Destination 212 and Date 141 on one row, then Note; submit ends at y 394 (frame y 440); the `To account` label is 1px visually hidden |
| 14 | All 48 editable controls compute ≥16px on every surface, including the Edit category `Name` field that reproduced the zoom; viewport meta keeps no `maximum-scale`/`user-scalable=no`, so pinch zoom stays available |
| 16 | Avatar `::before` computes exactly 10×10 `rgb(255,162,75)` |

`390×844` smoke: both cards 96px, segments 87×38, undo 26×26, no horizontal
overflow, no editable control below 16px, avatar dot 10×10.

Round 2b re-verification at `393×852`, driven through the real controls:

| Finding | Observed |
|---|---|
| 17 | Spend 50,000: no confirmation, no sheet, `overlay-active` false, amount and note cleared, mode stays Spend, balance and Available both 2,749,000 → 2,699,000, undo still offered. Add funds 25,000: silent, cleared, mode stays Add funds, balance → 2,724,000. Transfer 24,000 to a same-asset account through the mobile picker: silent, amount cleared, destination reset to `Choose destination`, mode stays Transfer, balance → 2,700,000, quote and execute both 201 |
| 18 | Gap after the segmented control is 10px in Spend, Add funds **and** Transfer; the amount field starts at y 178 and the submit ends at y 404 in all three, so the modes share one layout |

The two 422s in the console are deliberate bad-input transfer attempts from
the harness (no destination, then a cross-asset amount the exact-Decimal quote
rejects); both surfaced as inline form errors, and the successful transfer is
201 + 201.

Console and network are clean in the authenticated session — every request
200; the single 401 is the pre-login `auth/me` bootstrap probe.

Two limitations stand. The in-app browser is not WebKit, so real iPhone 15
Safari evidence is still required for owner acceptance. Its pane also freezes
CSS transitions while it is not the front tab, so the swipe measurement was
taken with the 160ms transition disabled; the settled transform and both
action boxes were then read directly.

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
- 2026-08-14 repository owner: returned sixteen new iPhone Safari findings with
  annotated screenshots and replaced the mobile design specification in the
  working tree, keeping the accepted copy as `Finnapp mobile specification old
  version/`. The owner instructed this session to record the findings and fix
  them, which reopens the task from `review` to `in-progress`. The findings and
  the specification-replacement conflict note are recorded under **Round 2**.
- 2026-08-14 Claude Opus 5: fixed all sixteen findings. Full pytest (425), the
  72-test targeted target, `node --check` and `git diff --check` pass, and the
  393×852 matrix plus 390×844 smoke verify every finding from the live DOM. The
  five stale frozen-contract assertions were rewritten to the new behaviour, and
  two assertions in `test_mobile_profile_access_ui_v21.py` that had been failing
  since `0621f97` were repaired. Left open for the owner: the design-spec
  replacement conflict above, and whether `openCategories` routing desktop into
  the mobile sheet is intended (a T-030B question). Independent implementation
  review and real iPhone 15 Safari evidence are still outstanding.
- 2026-08-14 Claude Opus 5: owner returned two further corrections after seeing
  the fixes on device — remove the **Saved** confirmation so saving is silent,
  and restore the missing 10px gap in Transfer. Both are fixed and verified
  through the real controls for all three save modes; full pytest stays at 425.
  The owner also stated that desktop is not a priority for this task, so the
  `openCategories` desktop-routing question is left entirely to T-030B.
- 2026-08-14 Claude Opus 5: the owner reported that nothing changed on device
  even after both fix rounds. Root cause was delivery, not the fixes: the SPA
  entry document was served without `Cache-Control`, so iOS Safari kept a
  heuristically cached copy holding the old asset version tokens. `app/main.py`
  now serves it with `no-cache`. Recorded as **Round 2c**; it is the one change
  outside `Touches` and needs owner sign-off. Full pytest 426.
