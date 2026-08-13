---
id: T-027A
title: Implement the mobile Operations action surface
status: done
size: M
spec: design/Finnapp mobile specification/spec/03-screens.md §3.3; spec/05-interactions.md; spec/06-content.md
blocked-by: [T-024B]
branch: task/T-027A-mobile-operations
base-commit: 7821bab32d5bc931b977cd02499b2c01c7a124a4
implementer: /root, Codex GPT-5
readiness-reviewed-by: /root/phase15_readiness_review, Codex GPT-5 same-vendor fallback
readiness-reviewed-commit: deb8a5a
readiness-verdict: ready
---

## Goal

Implement compact mobile Spend, Add funds, Transfer, and Scan with exact
financial commands and Saved handling, leaving period lifecycle to T-027B.

## Acceptance

- [x] Operations has no header, uses `padding:8px 16px 0`, two 96px card slots,
      exact 44px selector and §3.3 vertical budgets.
- [x] First visit is Spend; selected mode/account persist per user and stale or
      inaccessible saved accounts fall back safely.
- [x] Account card opens Switch account; changing it refreshes every dependent
      value and currency without stale responses winning.
- [x] Spend/Add funds use accepted endpoints. Category defaults to accessible
      Groceries/Salary when present, otherwise Uncategorized.
- [x] Transfer accepts one source amount and destination, executes a Phase 14
      quote, never requests target amount, and performs no client float/rate
      calculation.
- [x] Amount/Category/Date/Destination/Note use T-024A/T-024B controls. Invalid/zero
      amount blocks Save; exceeding Available today does not.
- [x] Submit and Scan copy match spec exactly; Scan performs no OCR.
- [x] Successful saves show exact branded dynamic Saved copy. Done clears
      amount/note/destination, retains mode/account, and refreshes account,
      allowance and Undo state.
- [x] When the server returns an Undo candidate, a compact 44×44 mobile Undo
      affordance appears in the account card top row without changing either
      96px card. It uses branded confirmation and the accepted server command,
      soft-voids the candidate, refreshes affected values, disappears, survives
      reload, and never falls back to an older transaction after consumption.
- [x] Account switching remains a separate semantic control from Undo. There is
      never more than one visible candidate for the selected account.
- [x] Spend/Add funds controls and targets reflect existing account roles;
      denied mutations remain unavailable or show the server-derived error.
      Quote-based mobile Transfer is owner-only and neither offers inaccessible
      targets nor calls quote/execute for a non-owner. Viewer, contributor,
      editor, and owner states do not leak hidden accounts or owner-private
      rate/quote data.
- [x] Operations works without a period. T-027A supplies a stable 96px
      period-card host/loading/error interface but no lifecycle forms.
- [x] Desktop explicit exchange, optional fee, persistent Undo and richer forms
      remain functional.
- [x] No period mutation, backend/schema, fake rate, OCR, history list, or
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

### Implementation review

- Reviewer: `/root/t027a_implementation_review`, Codex GPT-5.6, fresh
  same-vendor fallback because cross-vendor review was unavailable.
- Reviewed range: integration base
  `7821bab32d5bc931b977cd02499b2c01c7a124a4`, claim HEAD
  `6d92f682761353ae2ef2f4db47799208d274ba14`, and the exact uncommitted
  manifest in `app/static/index.html`, `app/static/app.js`,
  `app/static/style.css`, plus direct inspection of untracked
  `tests/test_mobile_operations_ui_v21.py` (173 lines at initial review).
- Initial findings, transcribed verbatim:

> Read-only implementation review for T-027A, same-vendor Codex fallback because cross-vendor review was unavailable.
>
> Reviewed range/manifest:
>
> - Integration base: `7821bab32d5bc931b977cd02499b2c01c7a124a4`
> - Branch/claim HEAD: `6d92f682761353ae2ef2f4db47799208d274ba14`
> - Tracked working-tree diff:
>   - `M app/static/app.js`
>   - `M app/static/index.html`
>   - `M app/static/style.css`
> - Directly inspected untracked file:
>   - `?? tests/test_mobile_operations_ui_v21.py` — 173 lines
> - No repository files or Git state were modified.
>
> Findings:
>
> - **P1 — The required mobile period loading/error interface is invisible.** `renderOperationsPeriod()` maps every state without a current period—including loading and request failure—to `is-absent` and the visible title `No period` (`app/static/app.js:1104-1118`). During loading/error, the Start control is hidden, while the only loading/error copy and Retry control live in the desktop group (`app/static/app.js:1132-1153`). Mobile CSS unconditionally hides that group, its status, and its cards (`app/static/style.css:535-537`). Thus an owner sees an ordinary no-period card while the request is pending or failed and has no visible retry/error interface, contrary to T-027A’s explicit stable 96px host/loading/error acceptance. `tests/test_mobile_operations_ui_v21.py:139-152` checks only source literals for `No period`, height, and the disabled Start listener; it cannot catch either missing state.
>
> - **P1 — The account-switch control has only a 26px mobile hit target.** The account card’s only switch control is `#operations-account-overlay-trigger` (`app/static/index.html:124`), and the mobile ID rule forces both `height` and `min-height` to `26px` (`app/static/style.css:544`). That higher-specificity rule overrides the generic 44px button and `.mobile-interactive` minimums. The rest of the 96px card is not wired as a button, so this violates the mobile non-negotiable that every interactive target is at least 44px and the account-card interaction contract. The geometry test at `tests/test_mobile_operations_ui_v21.py:11-28` does not assert this target.
>
> - **P1 — Successful financial commands are not acknowledged independently of refresh, and Done does not own the specified reset lifecycle.** `finishMobileOperation()` clears the draft immediately, awaits all of `refreshAll()`, and only then opens Saved (`app/static/app.js:1267-1289`). If the Spend/Add/execute POST has committed but any unrelated refresh read fails, the outer save handler catches that failure as a form error (`app/static/app.js:1354-1357`, `1427-1430`); no Saved confirmation appears and the user can retry an already-recorded operation. Even on the healthy path, amount/note/destination are cleared before Saved opens, whereas acceptance requires Done to clear them and refresh account/allowance/Undo state. The new tests merely assert that the copy and clearing statements exist (`tests/test_mobile_operations_ui_v21.py:65-73`, `139-149`), not their ordering or post-commit refresh-failure behavior.
>
> - **P2 — Period day count is wrong across daylight-saving transitions.** `daysLeft` subtracts local-midnight `Date` objects and floors by a fixed 86,400,000ms day (`app/static/app.js:1115-1117`). Across a 23-hour spring transition, a two-calendar-day inclusive period can render as `Period · 1d`; a fall transition has the inverse boundary risk. Use calendar/UTC date arithmetic and add a boundary test. The current test at `tests/test_mobile_operations_ui_v21.py:143` only checks the template literal.
>
> - **P2 — Desktop denied-transfer copy regressed to a mobile-only explanation.** `renderOperationsForms()` now assigns `Mobile Transfer is available only to the account owner.` whenever transfer is denied, regardless of viewport (`app/static/app.js:1028-1051`). On desktop, viewer/contributor states previously received the general transfer-permission error, and desktop’s accepted direct workflow remains editor-capable. This message incorrectly describes the preserved desktop contract. `tests/test_mobile_operations_ui_v21.py:155-173` checks only that richer desktop controls/source fragments remain, not denied-role behavior.
>
> No P0 or P3 findings.
>
> Verification reproduced:
>
> - Exact targeted pytest command: `76 passed in 34.10s`
> - `git diff --check`: passed
> - Worktree manifest remained unchanged after review.
> - Bare `node` was unavailable on the reviewer PATH, so I did not independently repeat the supplied successful bundled-runtime `node --check`.
>
> Verdict: **changes requested; not ready for implementation commit/acceptance.** All P1/P2 findings require closure and limited re-review.

- Resolution: the fixed 96px mobile period host now exposes explicit Loading
  and failure states plus a 44px Retry action; the account switch control is a
  44px target physically separate from Undo; Saved opens immediately after the
  command commits, while Done owns draft clearing and refresh; inclusive day
  counts use UTC calendar arithmetic; desktop denied-transfer copy is restored.
  Focused source and runtime coverage was added for every finding.
- First limited re-review, transcribed verbatim:

> Limited read-only re-review of the five prior findings against the amended manifest at HEAD `6d92f682761353ae2ef2f4db47799208d274ba14`.
>
> Finding:
>
> - **P2 — Account switch and Undo hit boxes still overlap by 4px.** The account-switch trigger ends at `cardWidth − 44px` because it uses `right: 44px` (`app/static/style.css:547`). Undo begins at `cardWidth − 48px` because it is 44px wide with `right: 4px` (`app/static/style.css:549`). Their top-row hit boxes therefore overlap from `cardWidth − 48px` through `cardWidth − 44px`. Undo is the later-painted sibling and can intercept that account-switch sliver, so the controls are not fully physically separate as required. Use non-overlapping offsets and add a focused geometry assertion; the added test at `tests/test_mobile_operations_ui_v21.py:29-32` currently asserts `right: 44px` without comparing it to Undo’s position.
>
> The other four findings are closed:
>
> - Mobile period loading/error/Retry states are visible within the stable 96px host.
> - Saved opens before refresh; Done owns draft clearing and refresh.
> - Period day count uses UTC calendar-day arithmetic.
> - Desktop denied-transfer copy is restored while mobile retains owner-only wording.
>
> Verification reproduced: exact target **77 passed in 31.68s**. Worktree/Git state was not modified.
>
> Verdict: **one residual P2 remains; limited closure is not yet granted.** No P0, P1, or P3 findings.

- Residual resolution: account switch now ends at the same boundary at which
  Undo begins (`right:48px` versus Undo `right:4px;width:44px`), and focused
  coverage asserts both non-overlapping geometries.
- Final limited re-review, transcribed verbatim:

> Final limited read-only re-review: **no P0–P3 findings**.
>
> `#operations-account-overlay-trigger` now ends at `cardWidth − 48px`; Undo begins at that same boundary with `right: 4px; width: 44px`. The hit boxes meet without overlap, and focused coverage asserts both geometries.
>
> The residual P2 is closed. T-027A implementation review is clean for the reviewed manifest. No files or Git state were modified.

### Verification evidence

- Exact targeted command: `77 passed in 31.98s` after behavioral fixes;
  reviewer independently reproduced `77 passed in 31.68s` before the final
  geometry-only closure, and the post-geometry focused gate was `18 passed`.
- Bundled Node `--check app/static/app.js`: passed.
- `git diff --check`: passed; Windows LF→CRLF notices only.
- Scratch FastAPI used only temporary databases under
  `C:\Users\Ксюша\AppData\Local\Temp`; each scratch directory was removed
  after verification and repository `finapp.db` was not touched.
- 390×844 browser: Spend/Add funds, same/cross-asset quote Transfer, Scan,
  category/date/destination Choose sheets, invalid/zero/overspend, exact Saved,
  Done reset/refresh, persistent branded Undo, no-period, account switch, and
  viewer/contributor/editor/owner privacy passed. Loading and error hosts stayed
  96px; Retry and account switch measured 44px; Saved retained amount/note and
  old balance until Done, then Done cleared the draft, retained mode and
  refreshed `1,000.00` to `1,025.00`. Transfer ended at the exact 440px running
  budget; page width was 390/390 with no visible native select.
- 1280×900 browser retained direct exchange, To amount, optional fee, full
  persistent Undo, richer forms, and no horizontal overflow.

### Local owner acceptance

- Accepted implementation commit:
  `bf7c3a814ab6691b66b4fa3bbb0c5254792df76d`.
- Repository-owner authorisation fast-forwarded the exact task branch to local
  `finapp-v2-develop`; no push or deploy was performed.
- Acceptance scope is T-027A only. T-027B remains unclaimed and its period
  lifecycle forms are not part of this checkpoint.

#### Acceptance lifecycle review

- Reviewer: `/root/t027a_acceptance_review`, Codex GPT-5.6, fresh same-vendor
  fallback because cross-vendor review was unavailable.
- Response, transcribed verbatim:

> Read-only local owner-acceptance review for T-027A, fresh same-vendor Codex fallback because cross-vendor review was unavailable.
>
> No P0–P3 findings.
>
> Reviewed:
>
> - Exact linear ancestry: accepted T-026 `e2e7d74` → promotion `7821bab` → claim `6d92f68` → implementation `bf7c3a8`.
> - `finapp-v2-develop` and `task/T-027A-mobile-operations` both point to `bf7c3a8`, confirming the local fast-forward.
> - Current manifest contains only the intended acceptance edits to:
>   - `docs/tasks/T-027A-mobile-operations.md`
>   - `docs/BACKLOG.md`
>   - `docs/PROGRESS.md`
> - Task and backlog consistently mark T-027A `done`.
> - T-027B remains `backlog`, unclaimed, and has no task branch.
> - Phase 15 remains explicitly incomplete.
> - The session log is append-only and records promotion, claim, implementation, and local acceptance.
> - Implementation review findings are transcribed verbatim with resolutions, limited re-reviews, exact test evidence, browser evidence, syntax and diff checks.
> - PROGRESS accurately identifies implementation `bf7c3a8`, the 77-test gate, local acceptance, and T-027B as next.
> - Local branch is ahead of origin; no push is represented. No deploy is claimed.
> - `git diff --check` passed; only informational LF→CRLF notices appeared.
>
> Verdict: suitable for the local T-027A acceptance commit.

## Session log

- 2026-08-12 Codex GPT-5: task split from former L-sized T-027; not claimed.
- 2026-08-12 Codex GPT-5: readiness findings added mobile Undo and shared-role
  quote checks; limited re-review verdict `ready`; remains blocked by T-024B.
- 2026-08-13 repository owner authorisation executed by `/root`, Codex GPT-5:
  accepted readiness evidence and promoted T-027A from `backlog` to `todo` on
  accepted integration after T-026 local acceptance; no task branch was claimed
  in this checkpoint.
- 2026-08-13 repository owner authorisation executed by `/root`, Codex GPT-5:
  atomically claimed `task/T-027A-mobile-operations` from accepted integration
  `7821bab`, recorded `/root` as implementer, and started only T-027A.
- 2026-08-13 `/root`, Codex GPT-5: implemented compact mobile Spend, Add funds,
  quote-based Transfer and Scan with exact Saved/Done, persistent Undo,
  role/privacy and fixed-height period host behavior while retaining desktop
  exchange/fee forms. Closed all P1/P2 review findings and the residual hit-box
  geometry finding after two limited re-reviews; targeted, syntax/diff,
  isolated 390×844 browser and retained 1280×900 checks pass. Task is ready for
  its implementation commit and local owner acceptance; nothing remains open.
- 2026-08-13 repository owner authorisation executed by `/root`, Codex GPT-5:
  fast-forwarded reviewed implementation `bf7c3a8` onto local
  `finapp-v2-develop`, accepted T-027A as `done`, and left T-027B unclaimed for
  its separate promotion/claim lifecycle. No push or deploy was performed.
