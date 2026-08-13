---
id: T-027B
title: Implement mobile account-period cards and lifecycle
status: review
size: M
spec: design/Finnapp mobile specification/spec/03-screens.md §3.3; spec/04-sheets.md; spec/05-interactions.md
blocked-by: [T-027A]
branch: task/T-027B-mobile-periods
base-commit: 6313852045c08b14d5c73c0b19a94b7991382d0d
implementer: /root, Codex GPT-5
readiness-reviewed-by: /root/phase15_readiness_review, Codex GPT-5 same-vendor fallback
readiness-reviewed-commit: deb8a5a
readiness-verdict: ready
---

## Goal

Complete the Operations period card and owner-private Start, Active, Edit,
Close, and History flows using only ledger-derived Phase 14 values.

## Acceptance

- [x] The period-card slot is exactly 96px for active, absent, loading, error,
      and non-owner states.
- [x] Owner current state renders API `available_today`, `Period · Nd`, and
      currency; absent renders `No period` and `+ Start period`.
- [x] Shared/non-owner accounts never request owner-private period endpoints and
      render the same non-actionable No period state regardless of owner state.
- [x] Start shows account/current balance, Start/End date and a checked
      Redistribute checkbox. Checked maps to
      `redistribute_remaining_days`; unchecked maps to `carry_next_day`.
- [x] Edit exposes only accepted mutable fields and the same policy mapping.
- [x] Active detail shows status, dates, opening/current balance and Available
      today. History lists current/ended/closed without Funding, Remaining,
      period Planned, or fake valuation.
- [x] Branded Close refreshes to absent; successful Start refreshes active.
      Ended/closed periods are read-only.
- [x] Available today is informational and may be negative.
- [x] Account changes refresh balance, allowance, days, opening balance and
      currency without stale request overwrite; errors preserve server
      authority and allow bounded retry.
- [x] UI formats exact API Decimal strings to asset precision and does not
      recompute ledger values.
- [x] Desktop period controls remain functional. No backend/schema, owner-state
      inference, funding, Plan reservation, or future scheduling is added.

## Touches

`app/static/index.html`, `app/static/app.js`, `app/static/style.css`,
`tests/test_mobile_periods_ui_v21.py`, `tests/test_frontend_v2.py`, design notes,
and task lifecycle evidence.

## Out of scope

Other Operations commands, backend/schema/API changes, shared period exposure,
future periods, period funding, Plan reservation, other screens.

## Verification

```bash
.venv/bin/python -m pytest -q tests/test_mobile_periods_ui_v21.py tests/test_frontend_v2.py tests/test_period_api_v21.py tests/test_periods_v2.py tests/test_period_lifecycle_v2.py tests/test_period_start_replay_v2.py tests/test_period_permissions_v21.py tests/test_period_contract_removal_v21.py tests/test_budget_carry_v2.py tests/test_budget_redistribute_v2.py
node --check app/static/app.js
git diff --check
```

Use `verify` for absent/current/ended/closed, Start/Edit policies, close/restart,
negative allowance, account switching and a shared account at 390×844, plus
desktop period regression.

## Review

### Implementation review

- Reviewer: `/root/t027b_implementation_review`, Codex GPT-5, fresh
  same-vendor fallback because cross-vendor review was unavailable.
- Reviewed range: accepted base
  `6313852045c08b14d5c73c0b19a94b7991382d0d`, claim HEAD
  `f6a3b54e7b8202a6e2333eb3a5870e4740a760d8`, and the complete uncommitted
  manifest in `app/static/index.html`, `app/static/app.js`,
  `app/static/style.css`, plus direct inspection of untracked
  `tests/test_mobile_periods_ui_v21.py`.
- Initial findings, transcribed verbatim:

> Review findings on the final current manifest (read-only; exact target independently rerun: 142 passed in 45.30s):
>
> P0: None.
>
> P1 — Ended history is rendered with a fabricated trailing balance. `app/static/app.js:1389-1394` chooses `period.closing_balance ?? period.opening_balance`, so an `ended` API shape (which contractually has `closing_balance=null` and no live `current_balance`) displays its opening snapshot as though it were the period’s ending/current value. This conflicts with T-027B’s explicit “without … fake valuation” criterion and can materially mislead financial history. Render an ended row without an inferred balance, or explicitly label the canonical opening snapshot rather than placing it in the unlabeled balance column. Update `tests/test_mobile_periods_ui_v21.py:58-68`, which currently enshrines the fallback.
>
> P1 — Ended periods remain actionable in the retained desktop history. `app/static/app.js:1092-1105` adds Edit and Close whenever status is not `closed`; therefore `ended` rows expose both commands even though the accepted contract and T-027B require ended/closed periods to be read-only. The API rejects them, but the UI presents invalid lifecycle actions. Restrict desktop actions to `period.status === "current"` and add focused coverage for an ended row, not just presence of desktop functions.
>
> P2 — Period “today” still uses the browser timezone instead of the workspace-local calendar. `todayValue()` at `app/static/app.js:124-127` is browser-local; the new mobile days-left calculation at `:1124-1126` and Start defaults at `:1269-1270` consume it. The accepted period contract defines status/default Start by workspace-local date (`state.context.workspace.timezone` is available), so a user browsing from another timezone can see `Period · Nd` off by one or submit a future default Start that the server rejects around midnight. Add a workspace-timezone date helper/coverage and use it for mobile period days/defaults (and preserve desktop behavior deliberately).
>
> P3 — The active detail exposes raw API status `current` at `app/static/app.js:1326-1333`, while the final visual source defines the user-facing value as `Active` (`Finapp Screen.dc.html:655-656`). Map the canonical current state to the specified English display label without changing server state.
>
> P3 — `.mobile-period-history-row` is `min-height:56px` at `app/static/style.css:743`, while the named sheet primitive requires 48px rows. This is a small exact-geometry mismatch in the new period sheet.
>
> Verdict: NOT APPROVED pending P1/P2 closure and fresh limited re-review. P3 items should be fixed when reasonable or explicitly recorded.

- Resolution: ended history now leaves the unavailable trailing value blank;
  desktop actions exist only for current rows; mobile days/defaults use the
  workspace timezone with DST-safe calendar arithmetic; Active copy and exact
  48px history rows match the final visual source. A nested Active → History
  Close now dismisses the complete stale sheet stack. Focused coverage freezes
  all behavior. The reviewer also found a test-only empty-slice bug; the exact
  end marker was corrected before final re-review.
- Final limited re-review, transcribed verbatim:

> Final limited re-review — verbatim closure report:
>
> Reviewer: `/root/t027b_implementation_review`, Codex GPT-5 fresh same-vendor fallback; cross-vendor reviewer unavailable.
> Reviewed range: accepted base `6313852045c08b14d5c73c0b19a94b7991382d0d`, claim HEAD `f6a3b54e7b8202a6e2333eb3a5870e4740a760d8`, and the complete current uncommitted manifest: modified `app/static/index.html`, `app/static/app.js`, `app/static/style.css`, plus directly inspected untracked `tests/test_mobile_periods_ui_v21.py`. The limited re-review covered all changes resolving Pass 1 findings, including the bounded nested-close fix and test-slice correction. No files were edited, no branch was switched, and Git state was not altered by the reviewer.
>
> P0: None.
> P1: None.
> P2: None.
> P3: None.
>
> All Pass 1 findings are closed:
> - Ended mobile history no longer substitutes `opening_balance` for an unavailable end/current value; only current `current_balance` and closed `closing_balance` appear in the trailing money column, and ended remains canonical/read-only.
> - Retained desktop history now creates Edit/Close actions only for `status === "current"`; ended and closed rows are read-only.
> - Mobile period days-left and Start defaults use the accepted workspace timezone through `workspaceTodayValue()`, while exact calendar-day subtraction remains DST-safe.
> - Active detail maps the API lifecycle state to the specified user-facing `Active` label.
> - New mobile period history rows use the specified exact 48px sheet-row geometry.
> - Focused coverage freezes each correction, including an exact slice for the desktop history function; the earlier empty-slice test bug is closed.
>
> Reviewer checks: exact 10-module target before Pass 1 fixes was `142 passed in 45.30s`; after the final limited diff, focused `tests/test_mobile_periods_ui_v21.py tests/test_frontend_v2.py` independently passed `18 passed in 0.25s`; `git diff --check` passed. Implementer-supplied final evidence additionally records the exact full target `143 passed`, bundled Node syntax pass, isolated mobile/desktop browser evidence, and scratch cleanup.
>
> Verdict: APPROVED. All P0–P3 findings are closed; no residual finding.

### Verification evidence

- Exact targeted command: `143 passed in 59.52s`; reviewer independently
  reproduced the pre-fix target as `142 passed in 45.30s` and the final focused
  pair as `18 passed in 0.25s`.
- Bundled Node `--check app/static/app.js`: passed.
- `git diff --check`: passed; Windows LF→CRLF notices only.
- Scratch FastAPI used only
  `C:\Users\Ксюша\AppData\Local\Temp\finapp-t027b-verify\finapp.db`;
  the server was stopped, the directory removed, and repository `finapp.db`
  was not touched.
- 390×844 browser: fixed 96px absent/current/loading/error/shared states,
  checked redistribution and unchecked carry policy mappings, arbitrary date
  Choose, exact Active details, Edit, exact branded Close, absent/restart,
  current plus read-only closed History, negative `−1,967 VND` allowance,
  account/currency switch and shared-viewer privacy passed; width was 390/390.
- 1280×900 browser retained Add/Edit/Close/History and exact negative values;
  the mobile active-card trigger remained hidden and no overflow appeared.

## Session log

- 2026-08-12 Codex GPT-5: task split from former L-sized T-027; not claimed.
- 2026-08-12 Codex GPT-5: independent batch readiness verdict `ready`; remains
  blocked by T-027A.
- 2026-08-13 repository owner authorisation executed by `/root`, Codex GPT-5:
  confirmed T-027A locally accepted, accepted T-027B readiness evidence, and
  promoted T-027B from `backlog` to `todo` on accepted integration `1b2e89a`;
  no task branch was claimed in this checkpoint.
- 2026-08-13 repository owner authorisation executed by `/root`, Codex GPT-5:
  atomically claimed `task/T-027B-mobile-periods` from promoted integration
  `6313852`, recorded `/root` as implementer, and started only T-027B.
- 2026-08-13 `/root`, Codex GPT-5: implemented owner-private mobile Start,
  Active, Edit, Close and History flows using only canonical period values,
  kept all card states at 96px and retained desktop controls. Closed all P1–P3
  findings after limited re-review; targeted, syntax/diff, isolated 390×844
  browser and retained 1280×900 checks pass. Task is ready for its
  implementation commit and local owner acceptance; nothing remains open.
