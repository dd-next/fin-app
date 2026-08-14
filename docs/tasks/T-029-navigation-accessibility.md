---
id: T-029
title: Integrate navigation, keyboard, motion, and accessibility
status: done
size: M
spec: design/Finnapp mobile specification/spec/05-interactions.md; spec/08-acceptance.md
blocked-by: [T-025B, T-026, T-027B, T-028]
branch: task/T-029-navigation-accessibility
base-commit: 844ea6c779f863c9f6274998f3e9efee4f3782b1
implementer: /root, Codex GPT-5
readiness-reviewed-by: /root/phase15_readiness_review, Codex GPT-5 same-vendor fallback
readiness-reviewed-commit: deb8a5a
readiness-verdict: ready
---

## Goal

Connect the implemented screens into one accessible mobile interaction graph
without changing backend contracts or feature geometry.

## Acceptance

- [x] Every permitted tap-map and sheet-graph transition works; deferred Type
      conversion/category merge-delete/restoration controls remain absent.
- [x] Tab switch closes overlays; scrim/close/Escape dismiss; nested Choose
      returns to its parent; focus is contained and restored to opener.
- [x] Sheets/dialogs expose correct accessible names/modal semantics, visible
      focus and keyboard operation; all actions work without a pointer.
- [x] Device/browser software keyboard opens for native amount/note fields,
      clears on Done/segment switch, does not create forbidden screen scroll,
      and Transfer Save has ≥80px visible clearance in the 250px reference
      visual-viewport state. No custom keyboard is built.
- [x] Sheet motion is ≤180ms and reduced-motion removes transforms without
      hiding content.
- [x] Targets are ≥44px; chips sit in 44px lanes; console is clean.
- [x] The entire runtime contains no native `<select>` and no calls to
      `alert`, `confirm`, or `prompt`; supported desktop actions use the shared
      accessible primitives rather than disappearing.
- [x] Regression tests cover graph/state/focus and forbidden APIs.
- [x] After acceptance, progress may say `preview-ready` but must still say
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

Implementation reviewer: `/root/t028_review_retry`, Codex GPT-5 fresh
same-vendor fallback; cross-vendor review was unavailable.

Reviewed range: claim commit
`ade15414c06eb106180ea701769d419de823b2d1` plus the complete uncommitted
manifest: modified `app/static/index.html`, `app/static/app.js`,
`app/static/style.css`, `tests/test_frontend_v2.py`,
`docs/design/DESIGN-NOTES.md`, and direct inspection of untracked
`tests/test_phase15_interactions.py`. The reviewer remained read-only and did
not alter files or Git state.

Initial bounded finding, verbatim:

> - **[P2] Desktop logout still bypasses the required shared confirmation.** [app/static/app.js](C:/Users/Ксюша/Documents/Codex/fin-app/app/static/app.js:5192) calls `openLogoutConfirmation` only when `isMobileViewport()` is true; lines 5197–5199 immediately POST logout and show Auth on desktop. This violates T-029’s requirement that supported desktop actions use shared accessible primitives rather than disappearing/bypassing them. Route the desktop click through `openLogoutConfirmation` too and add a regression test proving cancel makes no logout request on both viewport classes.
>
> No other bounded P0–P2 finding. Verdict: changes requested; T-029 is not review-clean until desktop logout confirmation is unified.

Resolution: the logout handler now routes every viewport through
`openLogoutConfirmation`; the POST remains exclusively inside the confirmed
action, and focused coverage freezes the unified handler. No desktop bypass
remains.

Limited re-review, verbatim:

> No findings. The sole P2 is closed: desktop and mobile logout now share `openLogoutConfirmation`, and the focused regression test guards the unified handler. The resolution is review-clean.

Final verdict: approved with no open P0–P2 finding; no P3 was reported.

Verification evidence:

- Exact task target: `11 passed in 0.55s`.
- Bundled Node `--check app/static/app.js`: passed.
- Forbidden runtime search for native `<select>` and
  `window.alert/confirm/prompt`: clean.
- `git diff --check`: passed; LF→CRLF notices only.
- Isolated scratch `/health` and SPA: HTTP 200; repository `finapp.db` was not
  touched.
- Mobile 390×844: Add account → nested Storage Choose → parent return and
  focus restoration; Saved/Done; Profile tab-close; Escape and scrim dismissal;
  native amount focus clearing on operation segment change; exact 180ms sheet
  motion; zero native select nodes, zero horizontal overflow and empty console
  passed.
- Desktop 1280×900: Account detail → Edit → shared Storage Choose temporarily
  closed the nested native dialogs, selected Cash, and restored both dialogs in
  order; zero horizontal overflow and empty console passed.
- Scratch server used the isolated database at
  `finapp-t029-79cc9e5adc5842fb9449ace283989e6a/finapp.db`; it was stopped after
  verification.

Local acceptance: performed directly by the repository owner, without a
separate acceptance-lifecycle reviewer sub-agent. The owner re-ran the task
verification gates on the reviewed manifest before accepting:

- `pytest -q tests/test_frontend_v2.py tests/test_phase15_interactions.py`:
  `11 passed`.
- `git diff --check`: passed; LF→CRLF notices only.
- Forbidden runtime search over `app/static` for native `<select>` and
  `window.alert/confirm/prompt`: clean.
- `node --check app/static/app.js` was **not** re-run at acceptance: no Node
  runtime is available in the owner's acceptance environment. The gate stands on
  the implementation session's bundled-Node result recorded above.
- Ancestry verified: `9d40b9f` → `844ea6c` → `ade1541` → `0ac4693`;
  `finapp-v2-develop` fast-forwarded to reviewed implementation `0ac4693` with
  no merge commit.

## Session log

- 2026-08-12 Codex GPT-5: integration task specified for batch readiness; not
  claimed.
- 2026-08-12 Codex GPT-5: dependency references updated after T-025 split;
  limited independent re-review verdict `ready`.
- 2026-08-13 repository owner authorisation executed by `/root`, Codex GPT-5:
  confirmed T-025B, T-026, T-027B, and T-028 locally accepted, accepted the
  recorded readiness verdict, and promoted T-029 from `backlog` to `todo` on
  accepted integration `9d40b9f`; no task branch was claimed here.
- 2026-08-13 repository owner authorisation executed by `/root`, Codex GPT-5:
  atomically claimed `task/T-029-navigation-accessibility` from promoted
  integration `844ea6c`, recorded `/root` as implementer, and started only
  T-029.
- 2026-08-13 `/root`, Codex GPT-5: unified all mobile and supported desktop
  selectors and destructive actions behind accessible shared Choose and
  confirmation primitives; completed focus containment/restoration, tab-close,
  keyboard blur, 180ms/reduced-motion, 44px-target and forbidden-native-API
  guards. Exact 11-test, syntax/diff/search gates and isolated 390×844 plus
  preserved 1280×900 browser smokes passed. Independent same-vendor fallback
  review closed its sole P2 desktop-logout finding; T-029 is ready for local
  owner acceptance. T-030A was not started.
- 2026-08-13 repository owner, assisted by Claude Opus 5: committed the reviewed
  T-029 manifest as `0ac4693`, fast-forwarded `finapp-v2-develop` onto it, and
  accepted T-029; task and backlog moved `review` → `done`. On owner
  instruction, `finapp-v2-develop` was then pushed to `origin`, so origin is no
  longer behind local accepted integration. No phase close, no deploy to
  `finapp-v2`, and no T-030A claim were performed.
