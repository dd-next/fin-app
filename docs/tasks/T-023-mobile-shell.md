---
id: T-023
title: Import approved tokens and responsive mobile shell
status: done
size: M
spec: design/Finnapp mobile specification/spec/01-foundations.md; spec/02-components.md Tab bar; spec/05-interactions.md
blocked-by: [T-022]
branch: task/T-023-mobile-shell
base-commit: 874422c
implementer: Codex GPT-5
readiness-reviewed-by: /root/phase15_readiness_review, Codex GPT-5 same-vendor fallback
readiness-reviewed-commit: deb8a5a
readiness-verdict: ready
---

## Goal

Establish the token-backed, safe-area-aware 390×844 mobile frame and five-tab
navigation while preserving the authenticated desktop shell and all existing
backend behavior.

## Acceptance

- [x] Runtime CSS copies only tokens actually used from the frozen token
      sources; runtime does not load `docs/`, webfonts, icon packs, component
      libraries, or a frontend build tool.
- [x] Viewport metadata includes `viewport-fit=cover`; production safe-area
      variables use `env()`, the shell uses `100dvh` with a safe fallback, and
      reference test variables can inject 54px top/34px bottom bands.
- [x] At 390×844 the injected reference bands leave exactly 700px of content
      above the 56px tab bar; content is not covered and no horizontal overflow
      exists.
- [x] The five tabs are exactly Accounts `▤`, Transactions `⇄`, Operations `◎`,
      Plan `◇`, Analytics `ϟ`, in that order, with ≥44px targets, approved
      active/idle colors, and accessible current/selected state.
- [x] Switching tabs preserves the existing view behavior and does not mutate
      or refetch financial data solely because the shell changed.
- [x] At 1280×900 the current top bar, navigation, five views, dialogs, auth and
      invitation flow remain reachable and functional.
- [x] No backend, route, schema, migration, permission, ledger, or money
      formatting behavior changes.
- [x] `DESIGN-NOTES.md` records the exact runtime tokens and shell rules landed.

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

### Implementation review

- Reviewer: `/root/t023_block_review`, Codex GPT-5 same-vendor fallback;
  cross-vendor reviewer was unavailable.
- Reviewed range: `a3916e4` plus the full uncommitted manifest
  `app/static/app.js`, `app/static/index.html`, `app/static/style.css`,
  `docs/design/DESIGN-NOTES.md`, `tests/test_frontend_v2.py`, and untracked
  `tests/test_phase15_shell.py`.
- Tests supplied to reviewer: targeted pytest `10 passed`; JS syntax and diff
  checks passed; authenticated scratch browser measurements at 390×844 and
  1280×900.
- Verbatim findings:

  > P2 — Mobile shell still uses the unapproved Inter-first font stack.
  > `app/static/style.css:3` declares `Inter, ui-sans-serif, system-ui,
  > -apple-system, ...`, so devices with Inter installed render the new mobile
  > tab bar/shell with Inter instead of the exact system stack required by
  > `spec/01-foundations.md` (`-apple-system, BlinkMacSystemFont, "Segoe UI",
  > system-ui, sans-serif`). This also makes
  > `docs/design/DESIGN-NOTES.md:133-150` incomplete because it says it records
  > the exact runtime tokens/shell rules landed but omits the typography
  > divergence. Scope the approved stack to the mobile runtime (or
  > intentionally update the root if desktop preservation is verified) and add
  > a regression assertion.

  > P2 — Keyboard focus indication on the fixed mobile tab bar is clipped by
  > the new geometry. `app/static/style.css:44-47` draws the only focus indicator
  > as an outside `outline` with a 2px positive offset, while
  > `app/static/style.css:272-288` sets `.primary-nav { overflow: hidden; }` and
  > `app/static/style.css:289-307` makes each button fill the bar’s full 55px
  > inner height. The top/bottom focus ring is therefore clipped (and the outer
  > side is clipped for the first/last tab), leaving an incomplete or nearly
  > absent indicator on key navigation targets. This is a basic-accessibility
  > regression not covered by `tests/test_phase15_shell.py:101-112`, which checks
  > target geometry/colors only. Add a mobile-specific inset focus-visible
  > treatment (or allow non-horizontal focus paint without reintroducing
  > overflow) and verify keyboard traversal/current-state visibility at
  > 390×844.

  > No P0, P1, or P3 findings. Other reviewed requirements were clean: exact
  > 54/34→700 shell geometry, 56px/5×equal tab geometry,
  > order/icons/current state, no tab-only financial refetch, scroll
  > containment/reachability, desktop selector isolation, and bounded scope.

- Resolution: scoped the exact approved system stack to mobile; replaced the
  clipped external tab outline with an inset accent focus ring; added focused
  regression assertions and updated `DESIGN-NOTES.md`.

### Limited fix re-review

- Reviewer: `/root/t023_fix_rereview`, Codex GPT-5 same-vendor fallback;
  cross-vendor reviewer was unavailable.
- Reviewed range: `a3916e4` plus the full current manifest, focused on the
  font/focus fixes, assertions, and design note.
- Verbatim result:

  > P0: none.
  > P1: none.
  > P2: none.
  > P3: none.
  >
  > Explicit result: **no findings**.
  >
  > The earlier P2 findings are closed:
  >
  > - Mobile now uses the approved system font stack.
  > - Tab keyboard focus uses an inset accent ring and remains visible within
  >   the clipped tab bar.
  > - Both fixes have focused regression assertions.
  > - `DESIGN-NOTES.md` accurately records the landed font and focus rules.
  > - No desktop regression or unrelated contract change was found in the
  >   bounded diff.
  >
  > Independently rerun gates:
  > targeted pytest: 10 passed
  > node --check app/static/app.js: passed
  > git diff --check: passed

### Verification evidence

- Targeted gates: `.venv/bin/python -m pytest -q tests/test_frontend_v2.py
  tests/test_phase15_shell.py` → `10 passed`; `node --check
  app/static/app.js` and `git diff --check` passed.
- `verify` skill scratch DB:
  `/private/tmp/finapp-verify.T023.oI36Et/finapp.db`, freshly upgraded
  `0001` → `0002` → `0003` → `0004`; Uvicorn always used its explicit
  scratch `DATABASE_URL`.
- Authenticated 390×844: actual zero-inset shell `788px` plus exact 56px tab
  bar; reference injection arithmetic `844 - 54 - 56 - 34 = 700`; five tab
  targets `78×55`; one visible view/current tab through all five sections;
  horizontal overflow `0`; inset keyboard focus ring observed; console clean.
- The access log was drained after initial load; a complete five-tab cycle
  emitted no `/api/v1/*` request, proving tab-only switching does not refetch
  financial data.
- Authenticated 1280×900: shell/nav remained `position: static`, horizontal
  overflow `0`; top bar and all five views were reachable. Account creation,
  account details, Share, and the invitation form were exercised through the
  visible UI; dialog/form controls remained enabled and console was clean.
- Screenshots retained in the scratch directory as
  `mobile-authenticated.png` and `desktop-authenticated.png`.

### Lifecycle evidence review

- Reviewer: `/root/t023_evidence_review`, Codex GPT-5 same-vendor fallback;
  cross-vendor reviewer was unavailable.
- Reviewed scope: T-023 task/backlog/progress lifecycle documentation against
  the full implementation manifest and recorded review/browser evidence.
- Verbatim finding:

  > P1 — `docs/PROGRESS.md:24-25` is stale. It says T-023 is `todo`,
  > unclaimed, and should be atomically claimed, while the task and backlog
  > both show `review`, branch HEAD is claim commit `a3916e4`, and
  > implementation/review evidence is recorded. Update the current-state
  > summary without claiming owner acceptance.
  >
  > P0: none. P2: none. P3: none.

- Resolution: updated only the current `Active work` and `Next` rows to show
  T-023 in `review` and local acceptance as the next action.
- Verbatim limited re-review:

  > P0: none. P1: none. P2: none. P3: none.
  >
  > Explicit result: no findings.
  >
  > The updated status matches the task, backlog, and current git state. Local
  > acceptance is clearly described as the next action, not as already
  > completed.

### Final documentation review

- Reviewer: `/root/t023_final_docs_review`, Codex GPT-5 same-vendor fallback;
  cross-vendor reviewer was unavailable.
- Reviewed scope: final lifecycle evidence and every T-023 reference in
  `docs/PROGRESS.md`.
- Verbatim finding and resolution:

  > P1 — `docs/PROGRESS.md:30-34` remains stale. The handoff says T-023 “is now
  > `todo`,” contradicting the task file, backlog, and current status table,
  > which all correctly show `review`.

  The handoff now states `review` and awaiting local acceptance.
- Verbatim limited re-review:

  > P0: none. P1: none. P2: none. P3: none.
  >
  > Explicit result: **no findings**.
  >
  > All `docs/PROGRESS.md` T-023 references now consistently describe
  > implementation and bounded reviews as complete, status `review`, and local
  > acceptance as the next action. No stale `todo` or unclaimed wording
  > remains. `git diff --check` passes.

## Session log

- 2026-08-12 Codex GPT-5: task specified in the Phase 15 fast-track preparation;
  implementation has not been claimed.
- 2026-08-12 Codex GPT-5: independent batch readiness review and limited
  re-review closed all P0–P2; owner promotion to `todo` recorded.
- 2026-08-12 Codex GPT-5: atomically claimed `task/T-023-mobile-shell` from
  accepted local integration `874422c`; lifecycle metadata now records the
  active implementer and matching backlog state. Implementation remains
  bounded to T-023; no open questions.
- 2026-08-12 Codex GPT-5: implemented the responsive safe-area shell and exact
  five-tab navigation, removed the tab-only Operations refetch, added focused
  regression coverage, closed both review P2 findings, and passed targeted
  static/browser gates. Task is ready for locally authorised acceptance; no
  open questions.
- 2026-08-12 repository owner authorisation executed by Codex GPT-5: locally
  fast-forward accepted verified task commits `a3916e4..f8fa0ef` into
  `finapp-v2-develop`; all P0–P2 were closed before acceptance. No push,
  deploy, task archival, or Phase 15 commit was performed.

### Local acceptance lifecycle review

- Reviewer: `/root/t023_accept_review`, Codex GPT-5 same-vendor fallback;
  cross-vendor reviewer was unavailable.
- Reviewed scope: `finapp-v2-develop` at `f8fa0ef` plus the complete lifecycle
  manifest in `docs/BACKLOG.md`, `docs/PROGRESS.md`, this task, and T-024A.
- Verbatim result:

  > P0: none. P1: none. P2: none. P3: none.
  >
  > Explicit result: **no findings**.
  >
  > Lifecycle state is consistent: T-023 is `done` in the task, backlog, and
  > progress summary; T-024A is readiness-reviewed `ready`, dependency T-023
  > is accepted, and it is `todo` in the task, backlog, and progress summary.
  > `task/T-024A-mobile-primitives` does not yet exist, so the next
  > atomic-claim wording is accurate.
  >
  > The acceptance record accurately describes delegated owner authorization
  > executed locally by Codex and does not claim a Phase 15 acceptance or
  > permanent-data readiness. No task archival, push, deploy, or final Phase
  > 15 commit is recorded or present. `git diff --check` passes.
