---
id: T-024B
title: Establish mobile sheets, pickers, and confirmations
status: review
size: M
spec: design/Finnapp mobile specification/spec/02-components.md; spec/04-sheets.md; spec/05-interactions.md
blocked-by: [T-024A]
branch: task/T-024B-mobile-overlays
base-commit: bf50e75
implementer: Codex GPT-5
readiness-reviewed-by: /root/phase15_readiness_review, Codex GPT-5 same-vendor fallback
readiness-reviewed-commit: deb8a5a
readiness-verdict: ready
---

## Goal

Provide one accessible overlay controller for stacked bottom sheets, reusable
Choose sheets, and branded confirmations without changing business actions or
authorization boundaries.

## Acceptance

- [x] One overlay root/controller owns sheet, confirmation, opener, and return
      stack state; feature tasks do not create competing mechanisms.
- [x] Bottom-sheet grabber/header/body/footer/safe band, top radius/border,
      `max-height:88%`, scrim, and ≤180ms motion follow specs 02/04.
- [x] Scrim, close, Escape, and Cancel dismiss without calling a primary or
      destructive callback; confirmed callbacks run at most once.
- [x] Opening records focus, background content is non-interactive, focus stays
      inside the active overlay, and closing restores focus to its opener.
- [x] Tab switching closes the full stack. A Choose sheet returns selection to
      its immediate sheet/form, marks the current option, and cannot select a
      disabled option.
- [x] Confirmation supports cancel+accent, cancel+destructive, and one-button
      Saved variants with accessible modal labels.
- [x] Reduced motion removes transforms without hiding content.
- [x] Callers remain responsible for passing only authorized accounts,
      periods, Plan items and transactions; no permissions are broadened.
- [x] A real production integration point exercises the infrastructure; no
      inaccessible component gallery is added.
- [x] Existing desktop dialogs remain functional until feature owners migrate
      them; concrete feature catalogues and final removal of native controls
      belong to T-025A–T-029.
- [x] No API, ledger mutation, financial formatter, backend, schema, or
      migration change is introduced.
- [x] `DESIGN-NOTES.md` records the overlay contract.

## Touches

Overlay root/templates in `app/static/index.html`, overlay CSS in
`app/static/style.css`, bounded controller/helpers in `app/static/app.js`,
`tests/test_frontend_v2.py`, `tests/test_phase15_overlays.py`, design notes, and
task lifecycle evidence.

## Out of scope

Concrete Accounts/Transactions/Operations/Plan/Profile workflows; changing API
payloads; migrating every legacy native control; T-015/T-016/T-017; custom
software keyboard.

## Verification

```bash
.venv/bin/python -m pytest -q tests/test_frontend_v2.py tests/test_phase15_overlays.py
node --check app/static/app.js
git diff --check
```

Use `verify` at 390×844 for scrim/X/Escape/Cancel/action, nested Choose return,
disabled option, tab closure, focus containment/restoration, reduced motion,
overflow and console; smoke existing desktop dialogs at 1280×900.

## Review

Append the bounded independent implementation review following the repository
protocol.

### Atomic claim review

- Reviewer: `/root/t024a_final_docs_review`, Codex GPT-5 same-vendor fallback;
  cross-vendor reviewer was unavailable.
- Reviewed scope: branch/base invariants and the complete lifecycle diff in
  this task, `docs/BACKLOG.md`, and `docs/PROGRESS.md`.
- Verbatim result:

  > Read-only atomic claim review for T-024B: **No findings (P0–P3).**
  >
  > Verified:
  >
  > - Exact branch `task/T-024B-mobile-overlays` was newly created from accepted local integration commit `bf50e75`; reflog confirms the creation point.
  > - At base `bf50e75`, T-024B was readiness-ready `todo` and dependency T-024A was accepted `done`.
  > - Current uncommitted manifest contains only the three expected claim documentation files:
  >   - `docs/tasks/T-024B-mobile-overlays.md`
  >   - `docs/BACKLOG.md`
  >   - `docs/PROGRESS.md`
  > - Task and backlog consistently record `in-progress`; progress identifies the exact active branch and bounded next work.
  > - `base-commit: bf50e75`, `implementer: Codex GPT-5`, branch, dependency, readiness evidence, and append-only session log are correct.
  > - No implementation, acceptance, push, deploy, archive, or phase-commit overclaim exists.
  > - `git diff --check` passes.
  >
  > This lifecycle diff is suitable for the first T-024B task commit unchanged. Reviewer: `/root/t024a_final_docs_review`, Codex GPT-5 same-vendor fallback; cross-vendor reviewer unavailable. Read-only; no files or Git state modified.

### Red-test block review

- Reviewer: `/root/t024b_tests_review2`, Codex GPT-5 same-vendor fallback;
  cross-vendor reviewer was unavailable. Read-only; no files or Git state were
  changed.
- Initial reviewed range: pre-implementation untracked
  `tests/test_phase15_overlays.py`; manifest contained only that untracked file.
- Original findings, verbatim:

  > - **P1 — DOM test does not verify one live overlay structure.** Lines 57–77 collect flat IDs without tracking ancestry. The required nodes may be scattered outside `#mobile-overlay-root`, duplicated as inactive templates, or placed inside `#app-shell`—which the controller then marks `aria-hidden`, hiding the dialog itself—and the test still passes. Assert exact descendant relationships and that the live overlay root is outside the inert background.
  >
  > - **P1 — Core controller behavior is only checked through source substrings.** Lines 105–127 do not execute any events. Dead or incorrectly ordered code can satisfy every assertion while scrim/X/Escape/Cancel invoke callbacks, double-click invokes confirmation twice, tab switching leaves nested entries, or closing fails to clear `inert`/`aria-hidden`. Add a DOM runtime test covering all dismissal paths, double action, and full-stack tab closure.
  >
  > - **P1 — Focus accessibility is not meaningfully tested.** Lines 114–123 only require `.focus()`, `restoreFocus`, and key-name strings. They do not prove focus enters the active top overlay, Tab and Shift+Tab wrap, background becomes interactive again, nested Choose returns focus to its immediate parent, or final close restores the original opener. These are explicit acceptance criteria and need runtime assertions.
  >
  > - **P2 — Choose-sheet disabled/current/nested behavior can pass with broken control flow.** Lines 130–138 separately search for `option.disabled`, `onSelect`, `pop`, and `render`; an implementation may still call `onSelect` for disabled options, pop the wrong entry, or close the parent. Execute enabled and disabled option clicks and assert callback counts, current marker semantics, stack depth, and immediate-parent return.
  >
  > - **P2 — CSS checks are not media-aware and omit desktop preservation.** Lines 18–27 merge exact selectors regardless of media scope; lines 101–102 accept unrelated/commented reduced-motion text. Mobile overlay styles could leak into 1280×900, or reduced motion could still hide translated content. Assert mobile scoping, default desktop hiding/non-interference, and the actual reduced-motion rule’s effective transform/transition state.
  >
  > - **P2 — Confirmation variants and native-confirm boundary are under-tested.** Lines 124–126 only look for `destructive` and `saved`; they do not validate cancel+accent, cancel+destructive, or one-button Saved DOM/action semantics. Line 151 omits `confirm` from the native-dialog regex. Add structural/action assertions for all three variants and prohibit new `confirm()`/`window.confirm()` use in the bounded controller/integration.
  >
  > Diff status: only `?? tests/test_phase15_overlays.py`; no tracked diff. Reproduced baseline: `7 passed, 6 failed`; `node --check app/static/app.js` passed; `git diff --check` passed. No P0 or P3 findings. No files or Git state modified.

- Resolution: the parser now proves singleton ancestry outside the inert shell;
  balanced-media assertions cover mobile scope, desktop hiding and effective
  reduced motion; controller assertions cover cleanup, full-stack closure,
  guarded action ordering and focus wiring; disabled selection ordering,
  current state, all confirmation variants and the native-dialog boundary are
  explicit. Event behavior was reserved for the mandatory final `$verify` gate.
- Limited closure verdict, verbatim:

  > Limited read-only re-review of revised `tests/test_phase15_overlays.py`: **No findings (P0–P3).**
  >
  > The prior gaps are closed at the intended two-layer boundary:
  >
  > - Automated regression checks now enforce overlay ancestry outside the inert shell, mobile CSS scoping, desktop trigger hiding, effective reduced-motion transform/transition removal, confirmation variants/native-dialog boundary, once-guard ordering, disabled-option ordering, and full-stack closure wiring.
  > - T-024B’s mandatory final `$verify` browser gate remains responsible for event-level proof of scrim/X/Escape/Cancel callback suppression, double-action prevention, nested Choose return, disabled clicks, Tab/Shift+Tab containment, focus restoration, tab closure, reduced-motion visibility, and desktop-dialog preservation. Recording that evidence against the final manifest closes the earlier runtime P1/P2 concerns.
  >
  > Verification reproduced:
  >
  > - `tests/test_frontend_v2.py`: 7 passed.
  > - `tests/test_phase15_overlays.py`: 7 expected red failures.
  > - `node --check app/static/app.js`: passed.
  > - `git diff --check`: passed.
  > - Manifest: only `?? tests/test_phase15_overlays.py`; no tracked diff.
  >
  > No files or Git state modified.

### Implementation review and resolutions

- Reviewer: `/root/t024b_impl_review`, Codex GPT-5 same-vendor fallback;
  cross-vendor reviewer was unavailable. Reviewed the complete implementation
  manifest from claim `c12edd8`; read-only, no files or Git state were changed.
- Initial findings, verbatim:

  > [P1] The controller does not record an opener per stack entry, so nested overlays violate the required opener/focus-return contract. `openMobileSheet` stores only an optional selector and `openMobileConfirmation` ignores its `opener` whenever a parent is already on the stack; confirmation entries have no `returnFocusSelector` at all. On nested confirmation Cancel/X/Escape/success, `closeMobileOverlay()` gets a falsy focus target, rebuilds the parent, and `renderMobileOverlay()` focuses the parent's first control instead of the control that opened the confirmation. Nested Choose has the same failure whenever a caller omits an explicit selector, despite accepting an `opener` argument. Record the actual opener on every entry and prefer it (or a selector resolving in the rebuilt parent) when popping; add execution coverage.
  >
  > [P2] Required scratch-browser behavior is not yet evidenced for confirmation Cancel/action variants and once-async suppression, nested Choose immediate return, disabled-option rejection, or reduced motion. The 390 smoke proves the root production Choose, X/scrim/Escape, root opener restore, tab loop/tab closure, selection, layering and overflow; the overlay pytest is source/DOM substring inspection only and does not execute controller behavior. That is insufficient for the task's explicit `$verify` gate, especially because it missed the nested opener defect above. A test-only browser harness is fine if no gallery is shipped, or expose/invoke the functions through a non-production test mechanism.

- Resolution: every stack entry records its opener and stable ID, pop resolves
  the immediate connected/recreated opener before the root opener, and a
  URL-gated non-financial verification harness exercises nested Choose and all
  confirmation variants without shipping a component gallery or touching an
  API. Scratch-browser checks covered disabled/enabled selection, immediate
  focus return, Cancel/action variants, double-action suppression, focus loop,
  tab closure, overflow, console and desktop preservation.
- Fresh re-review finding after those resolutions, verbatim:

  > [P1] The overlay intercepts physical tab-bar taps: its full-screen root is `z-index:100`, while the fixed tab bar remains `z-index:auto`. Programmatic clicks can mask this. Restore active-overlay tab-bar elevation and verify with a hit-tested tap.

- Resolution: `overlay-active` now raises the tab bar to z-index 110 above the
  z-index 100 root. The active sheet safe band uses non-shrinkable
  `safe-bottom + tabbar-height` clearance, and the confirmation uses the same
  bottom clearance. A physical coordinate tap, not a programmatic click,
  proves the tab receives the pointer and closes the stack.

### Final P1 regression-test review

- Reviewer: `/root/t024b_tab_test_review`, Codex GPT-5 same-vendor fallback;
  reviewed only the final red regression-test delta; read-only, no repository
  or Git mutation.
- Finding, verbatim:

  > [P1] The clearance regression only asserts the active safe band's `height`, not its `min-height` (`tests/test_phase15_overlays.py:132-135`). `.mobile-sheet` is a constrained flex column (`max-height:88%`) and `.mobile-sheet-safe-band` is a shrinkable flex item whose base `min-height` remains only `var(--mobile-safe-bottom)`. An implementation can satisfy this test with `height: calc(safe + tabbar)` yet shrink the band back toward 34px under pressure, allowing the raised 56px nav to cover the last sheet/footer action—the exact remaining P1. Require the active rule and test to set/assert both `height` and `min-height` to `calc(var(--mobile-safe-bottom) + var(--mobile-tabbar-height))` (or otherwise prove non-shrink, e.g. flex:none). Evidence: current new suite is red on implementation as intended: 2 failed, 6 passed; failures are missing active-nav CSS and missing body class toggle. No mutation performed.

- Resolution: the regression and production rule both require exact `height`
  and `min-height` equal to safe area plus tab-bar height.
- Limited closure verdict, verbatim:

  > Limited re-review: prior P1 is closed.
  >
  > The test now requires both active safe-band `height` and `min-height` to equal the exact safe-area plus tab-bar calculation, preventing flex shrink from removing action clearance.
  >
  > Evidence:
  >
  > - `git diff --check` clean.
  > - Selected tests remain intentionally red only for the two missing production changes: active navigation CSS and body-state toggle.
  > - No new P0–P3 findings.
  > - Read-only review; no files changed.

### Final implementation re-review

- Verbatim result from `/root/t024b_impl_review`:

  > Final limited read-only re-review verdict — **No findings (P0–P3). Prior P1 is closed.**
  >
  > Reviewer: `/root/t024b_impl_review`, Codex GPT-5 same-vendor fallback; read-only, no repository or Git mutation.
  >
  > Reviewed range/manifest: current uncommitted T-024B diff from task HEAD `c12edd8` on `task/T-024B-mobile-overlays`: `app/static/app.js`, `app/static/index.html`, `app/static/style.css`, and untracked `tests/test_phase15_overlays.py`, focused on the final tabbar-hit/lower-clearance changes and their regression assertions.
  >
  > Verified source/CSS contract:
  > - `renderMobileOverlay()` now toggles `body.overlay-active` exactly with stack activity.
  > - At mobile width, overlay root is fixed full-frame at z-index 100 and `body.overlay-active .primary-nav` is z-index 110, preserving the deliberate non-inert tabbar and allowing real tab taps to reach `switchView()`, which closes the entire stack.
  > - The active sheet safe band has both exact `height` and `min-height` of `calc(var(--mobile-safe-bottom) + var(--mobile-tabbar-height))`; the active confirmation uses the same exact bottom clearance. This prevents sheet options/actions from being painted or hit underneath the elevated tabbar while retaining the sheet's 88% maximum height.
  > - Strengthened regression tests assert the body-class toggle, z-index ordering, safe-band height/min-height, and confirmation bottom clearance.
  >
  > Correlated `$verify` evidence from explicit scratch DB `/private/tmp/finapp-verify.T024B-final.L2RUAF/finapp.db` closes the behavioral gap: at 390×844 a physical CUA click on the last Reserve option selected account id 2 with option bottom = nav top = 788; a physical CUA click at Plan center hit `button[data-view=plan]`, closed the root, and activated Plan; confirmation bottom = nav top = 788, action bottom = 771, and `elementFromPoint` hit Verify. Horizontal overflow was 0 and console was empty. At 1280×900, native select remained visible at 520×48, the mobile trigger remained hidden, legacy Add account dialog opened, overflow was 0, and console was empty. No `finapp.db` use is present in the supplied evidence.
  >
  > Independent rerun: `.venv/bin/python -m pytest -q tests/test_frontend_v2.py tests/test_phase15_primitives.py tests/test_phase15_overlays.py` → **22 passed**; `node --check app/static/app.js` → pass; `git diff --check` → pass. Worktree manifest is exactly the three modified static files plus the one untracked overlay test file above.
  >
  > The prior P1 physical-tab interception is therefore closed, and this final fix is suitable to retain unchanged.

### Verification evidence

- Targeted automated gate:
  `.venv/bin/python -m pytest -q tests/test_frontend_v2.py tests/test_phase15_primitives.py tests/test_phase15_overlays.py`
  → `22 passed in 0.14s`; `node --check app/static/app.js` and
  `git diff --check` passed. The untracked-file whitespace check was clean
  (`git diff --no-index --check` exit 1 only because the file differs).
- `$verify` used only the fresh migrated scratch database
  `/private/tmp/finapp-verify.T024B-final.L2RUAF/finapp.db`; the repository
  `finapp.db` was never used. Accounts and balances were created through the
  visible UI/public application flow.
- 390×844 production Choose: X, scrim and Escape dismissed without selection;
  enabled selection updated the existing select/change path and exact balance;
  disabled selection was rejected; nested Choose returned focus to its
  immediate opener; Tab/Shift+Tab wrapped; all confirmation variants rendered;
  Cancel was non-mutating and a double destructive action ran its async callback
  once. The final physical option tap selected Reserve (`id=2`, `55.75 USD`).
- 390×844 final hit-test: last option bottom and tab top were both 788px;
  `elementFromPoint` at the Plan tab center resolved to
  `button[data-view=plan]`; a physical CUA tap closed the overlay, removed the
  active body state and activated Plan. Confirmation bottom was 788px, action
  bottom 771px, and its center hit the Verify button. Horizontal overflow was
  zero and browser console was empty.
- Reduced-motion CSS was checked for effective `transform:none` and
  `transition:none`; the browser policy denied motion emulation, so ordinary
  visible content plus the exact effective regression contract is the retained
  evidence.
- 1280×900 desktop: existing Operations select remained visible at 520×48,
  mobile trigger remained hidden, legacy Add account dialog opened and closed,
  horizontal overflow was zero and console was empty.
- Screenshots: `/private/tmp/finapp-verify.T024B-final.L2RUAF/mobile-overlay-final.png`
  and `/private/tmp/finapp-verify.T024B-final.L2RUAF/desktop-final.png`.

### Final documentation and lifecycle review

- Reviewer: `/root/t024b_final_docs_review`, Codex GPT-5 same-vendor fallback;
  read-only, no files or Git state changed.
- Reviewed range: exact branch `task/T-024B-mobile-overlays`, claim HEAD
  `c12edd844c88d826835a0b79f748fa7b18cf53fc`, base
  `bf50e7581d6dd6a9fa8a75f42e837f9d1257e79e`, and the complete eight-file
  implementation, test, design and lifecycle manifest.
- Verbatim verdict:

  > Final read-only documentation/lifecycle review for T-024B: **No findings (P0–P3).**
  >
  > Reviewer: `/root/t024b_final_docs_review`, Codex GPT-5 same-vendor fallback; read-only, no files or Git state changed.
  >
  > Reviewed branch/range: `task/T-024B-mobile-overlays`, task HEAD `c12edd844c88d826835a0b79f748fa7b18cf53fc`, base `bf50e7581d6dd6a9fa8a75f42e837f9d1257e79e`, complete uncommitted manifest:
  >
  > - `app/static/app.js`
  > - `app/static/index.html`
  > - `app/static/style.css`
  > - `docs/BACKLOG.md`
  > - `docs/PROGRESS.md`
  > - `docs/design/DESIGN-NOTES.md`
  > - `docs/tasks/T-024B-mobile-overlays.md`
  > - untracked `tests/test_phase15_overlays.py`
  >
  > Verified:
  >
  > - Task and backlog are consistently `review`; branch, base commit, implementer, dependency and readiness metadata are correct.
  > - All acceptance criteria are checked and supported by the implementation, targeted tests and recorded `$verify` evidence.
  > - Every recorded P1/P2 finding is preserved verbatim with reviewer identity, reviewed range/manifest, resolution and closure verdict. The red-test findings and closure text match the originating reviewer evidence exactly.
  > - The session log is append-only and accurately states what landed, remaining acceptance work and no open questions.
  > - `PROGRESS.md` reports verified-but-not-accepted state without claiming task or phase acceptance.
  > - No next task was promoted or claimed; backlog dependencies remain untouched.
  > - `DESIGN-NOTES.md` records the bounded overlay contract and physical tab-close clearance without widening backend, API, ledger, permissions or financial scope.
  > - Scratch-browser evidence names `/private/tmp/finapp-verify.T024B-final.L2RUAF/finapp.db` and explicitly excludes repository `finapp.db`; referenced mobile and desktop screenshots are present.
  > - No push, deploy, archive, phase commit, next-task work, or owner-acceptance overclaim is present.
  >
  > Independent verification:
  >
  > - `.venv/bin/python -m pytest -q tests/test_frontend_v2.py tests/test_phase15_primitives.py tests/test_phase15_overlays.py` → **22 passed in 0.13s**
  > - `node --check app/static/app.js` → passed
  > - `git diff --check` → passed
  > - Untracked `tests/test_phase15_overlays.py` no-index whitespace check → clean
  >
  > Verdict: the complete T-024B manifest is suitable to retain unchanged, commit as the task implementation, and locally accept under the owner’s explicit authorization.

- Limited transcription re-review, verbatim:

  > Limited final re-review: **No findings (P0–P3).**
  >
  > The “Final documentation and lifecycle review” section preserves the prior response verbatim, including reviewer identity, exact branch/base/HEAD, eight-file manifest, verification evidence and acceptance verdict.
  >
  > Confirmed:
  >
  > - Only `docs/tasks/T-024B-mobile-overlays.md` changed since the prior review.
  > - Task remains `review`; no acceptance, next-task promotion, push, deploy, archive or phase-commit overclaim was introduced.
  > - `git diff --check` passes.
  > - Read-only review; no files or Git state changed.

## Session log

- 2026-08-12 Codex GPT-5: task split from the former L-sized T-024; not claimed.
- 2026-08-12 Codex GPT-5: independent batch readiness verdict `ready`; remains
  blocked by T-024A.
- 2026-08-12 repository owner authorisation executed by Codex GPT-5: promoted
  readiness-ready T-024B from `backlog` to `todo` after local acceptance of
  dependency T-024A; implementation is not yet claimed.
- 2026-08-12 Codex GPT-5: atomically claimed
  `task/T-024B-mobile-overlays` from accepted local integration `bf50e75`;
  lifecycle metadata and shared state now identify the active implementer.
  Implementation remains bounded to T-024B; no open questions.
- 2026-08-13 Codex GPT-5: implemented the single mobile overlay stack, bounded
  Operations account Choose integration, confirmation variants, focus/inert/
  dismissal semantics, reduced-motion rules and URL-gated non-financial browser
  harness. Review-driven opener restoration and physical tab-hit defects were
  fixed; all recorded P0–P2 findings are closed. Targeted 22-test, JavaScript,
  diff and scratch `$verify` mobile/desktop gates pass. Task is `review`,
  awaiting authorised local acceptance; no open questions.
