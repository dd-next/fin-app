---
id: T-026
title: Implement the mobile Transactions feed and management flows
status: review
size: M
spec: design/Finnapp mobile specification/spec/03-screens.md §3.2; spec/04-sheets.md; spec/05-interactions.md; spec/06-content.md
blocked-by: [T-024B]
branch: task/T-026-mobile-transactions
base-commit: f3f747bfcc9e1e731f7200770c2b963da1753a19
implementer: /root, Codex GPT-5
readiness-reviewed-by: /root/phase15_readiness_review, Codex GPT-5 same-vendor fallback
readiness-reviewed-commit: deb8a5a
readiness-verdict: ready
---

## Goal

Make Transactions a stable mobile financial-date feed with working chips,
details, correction, assignment, Plan linking, swipe and branded Delete while
preserving richer desktop filters and the Phase 14 contracts.

## Acceptance

- [x] Mobile has the exact header/filter badge, chip lane, date-grouped scrolling
      list, row/status/empty copy, and no transaction creation control.
- [x] All/Income/Expense/Transfer/Planned use `/api/v1/transaction-feed` with
      exact opaque cursor behavior; switching chip resets pagination and removes
      empty groups.
- [x] Exchange maps visibly to Transfer, adjustment appears only in All,
      Deleted stays at financial-date position, and planned rows never affect
      ledger-derived values.
- [x] Persisted/planned rows use their discriminated detail endpoints; hidden
      legs remain redacted and inaccessible IDs retain generic not-found.
- [x] Planned details open the Plan-item flow rather than changing tabs.
- [x] Swipe exposes keyboard-accessible Plan/Delete actions, with the specified
      visual shift and ≥44px targets.
- [x] Branded Delete soft-voids through the accepted endpoint, supports required
      ended/shared confirmation without native dialogs, and refreshes the feed.
- [x] Mobile correction omits transaction Type conversion. Accepted assignment
      remains available where applicable.
- [x] Advanced Filters uses the persisted `/transactions` API for Account,
      Period, Type, Category, From and To. While active it shows persisted rows
      only; choosing a top chip clears it and returns to the unified feed.
- [x] Empty-state Open Operations switches tab and closes overlays.
- [x] Desktop retains richer status/adjustment/exchange filters, assignment and
      existing behavior.
- [x] No backend/query extension, fake paged client filter, hard delete,
      transaction creation, or T-015 conversion is added.

## Touches

`app/static/index.html`, `app/static/app.js`, `app/static/style.css`,
`tests/test_mobile_transactions_ui_v21.py`, `tests/test_frontend_v2.py`, design
notes, and task lifecycle evidence.

## Out of scope

Backend/feed contract changes, type conversion, category merge/delete, Plan
screen redesign, Operations, Accounts/Profile, periods, desktop redesign.

## Verification

```bash
.venv/bin/python -m pytest -q tests/test_mobile_transactions_ui_v21.py tests/test_frontend_v2.py tests/test_transaction_feed_v21.py tests/test_planned_transaction_feed_v21.py tests/test_transactions_phase12_v2.py tests/test_phase12_privacy_v2.py
node --check app/static/app.js
git diff --check
```

Use `verify` for chips/pagination/groups, all item kinds, swipe, filters,
details/correction/delete/empty state at 390×844 and retained filters at
1280×900.

## Review

### Independent implementation review — 2026-08-13

- Reviewer: `/root/t025b_final_review`, Codex GPT-5 fresh independent
  same-vendor fallback because the other vendor was unavailable.
- Reviewed range: claim commit `51fe3fc` plus the bounded uncommitted T-026
  manifest in `app/static/index.html`, `app/static/app.js`,
  `app/static/style.css`, and `tests/test_mobile_transactions_ui_v21.py`.
- Initial findings, transcribed verbatim:

> Findings
>
> - P1 — [app/static/app.js](C:\Users\Ксюша\Documents\Codex\fin-app\app\static\app.js:3113): Mobile assignment always sends `confirm_ended_period: true` immediately after an account is selected. An assignment that affects an ended period therefore bypasses the backend’s required 409 confirmation round trip without showing any consequence confirmation—the Choose row silently supplies the explicit-confirmation flag. Submit the initial assignment without the flag, then use a branded confirmation and confirmed retry when required. Add focused coverage for both ordinary and ended-period assignments.
>
> - P1 — [app/static/app.js](C:\Users\Ксюша\Documents\Codex\fin-app\app\static\app.js:270): `refreshAll()` always replaces `state.transactions` with an unfiltered `/transactions?limit=50` page while leaving `transactionAdvancedActive` and its badge/filter controls unchanged. Delete, correction, assignment, and Plan-link flows all call `refreshAll()`, so after any such mutation under Advanced Filters, `renderMobileTransactions()` at line 2975 shows unfiltered persisted rows as though the advanced filters were still active. Reload the active persisted query after mutations or clear advanced mode truthfully; add a regression covering mutation while a filter is active.
>
> - P2 — [app/static/app.js](C:\Users\Ксюша\Documents\Codex\fin-app\app\static\app.js:3318): Mobile correction’s Financial date and Advanced Filters’ From/To fields at lines 3458–3459 are plain text inputs. The named sheet specification requires every Financial date, From, and To choice to use the Choose-sheet primitive. Add the date-choice flow and focused coverage.
>
> No P0 or P3 findings.
>
> Read-only verification passed: the exact targeted suite completed with `32 passed in 10.60s`; bundled Node syntax checking and `git diff --check` also passed. Those source-contract tests do not exercise the three runtime paths above.
>
> Verdict: changes required; T-026 is not yet suitable to commit. Cross-vendor review was unavailable, so this was a fresh independent same-vendor Codex fallback.

- Resolution: assignment now makes an ordinary unconfirmed request and presents
  a branded consequence confirmation only after the accepted explicit-confirmation
  409 before retrying with `confirm_ended_period: true`; `refreshAll()` preserves
  the active persisted query and pagination during mobile mutations; Financial
  date and From/To use a branded, month-navigable Choose-sheet calendar with
  unbounded previous/next traversal, 42 date buttons, 44px targets, and `Any`
  for range endpoints. Focused source coverage and browser behavior checks were
  added.
- First limited re-review, transcribed verbatim:

> Findings
>
> - P1 — [app/static/app.js](C:\Users\Ксюша\Documents\Codex\fin-app\app\static\app.js:3297): The new Choose-sheet date flow permits only the current value, today, the previous three days, and the first day of the current month. Consequently, Financial date cannot be corrected to an arbitrary valid date, and From/To cannot express most historical or future ranges—for example, no prior-month boundary is selectable. This replaces the original free-form capability with a materially incomplete picker. Supply a non-native Choose/date flow that can represent arbitrary valid dates and add behavioral coverage beyond asserting that `mobileDateChoice()` is called.
>
> The other two findings are closed:
>
> - Assignment now performs an unconfirmed first request, shows the branded ended-period consequence confirmation only on the required 409, retries with the explicit flag, and ends in Saved.
> - `refreshAll()` now reloads the persisted `transactionQuery()` while mobile Advanced Filters are active, preserving filtered rows, pagination, and the badge across mutations.
>
> No P0, P2, or P3 findings. `git diff --check` and bundled Node syntax checking pass; supplied focused/runtime evidence supports the two closed paths.
>
> Verdict: changes required—the date-choice finding remains open. Cross-vendor review was unavailable; this was a fresh independent same-vendor Codex fallback.

- Final limited re-review, transcribed verbatim:

> No P0–P3 findings.
>
> The remaining date-choice P1 is closed:
>
> - Financial date and From/To use the branded CHOOSE-sheet calendar.
> - Previous/next navigation traverses historical and future months without an application-imposed bound.
> - The 42-button grid includes adjacent-month dates, preserves the current selection, and uses 44×44 minimum targets.
> - From/To include Any.
> - Selecting a date returns to and updates the parent sheet.
> - Focused source checks and the supplied July 2026 runtime traversal confirm the formerly missing arbitrary-date behavior.
>
> `git diff --check` and bundled Node syntax checking pass; the supplied focused gate remains `33 passed`.
>
> Verdict: PASS—all three original findings are closed. Cross-vendor review was unavailable; this was a fresh independent same-vendor Codex fallback.

### Verification evidence

- Exact targeted command: `33 passed in 11.38s`.
- Bundled Node `--check app/static/app.js`: passed.
- `git diff --check`: passed; Windows LF→CRLF notices only.
- Scratch FastAPI used only
  `C:\Users\Ксюша\AppData\Local\Temp\finapp-t026-ff9dcf462e9c45cca557c73609e47e14\finapp.db`;
  repository `finapp.db` was not touched.
- 390×844 browser: all five real feed chips, financial-date groups, planned,
  income, expense, adjustment, transfer and exchange presentation, planned and
  persisted discriminated details, correction and Saved, branded soft-delete,
  advanced filters, empty-state navigation, arbitrary-date Choose calendar,
  −112px swipe, 64×64 actions, no page overflow, and no console errors passed.
- Mutation under active Type=Income retained badge `1`, only the filtered Salary
  row, and its group after Saved. Previous month → Jul 15 selected in the From
  calendar and returned to Filters. The calendar day target measured 44px.
- 1280×900 browser: the seven richer filters, persisted rows, Details/actions,
  and no page overflow passed.

## Session log

- 2026-08-12 Codex GPT-5: task specified for batch readiness; not claimed.
- 2026-08-12 Codex GPT-5: independent batch readiness verdict `ready`; remains
  blocked by T-024B.
- 2026-08-13 repository owner authorisation executed by `/root`, Codex GPT-5:
  accepted readiness evidence and promoted T-026 from `backlog` to `todo` on
  accepted integration; no task branch was claimed in this checkpoint.
- 2026-08-13 repository owner authorisation executed by `/root`, Codex GPT-5:
  atomically claimed `task/T-026-mobile-transactions` from accepted integration
  `f3f747b`, recorded `/root` as implementer, and started only T-026.
- 2026-08-13 `/root`, Codex GPT-5: implemented the bounded mobile Transactions
  feed, details, swipe, soft-delete, correction, assignment, Plan link and
  advanced filters while retaining desktop behavior. Closed all independent
  review findings after two limited re-reviews; targeted, syntax/diff, isolated
  390×844 browser and retained 1280×900 checks pass. Task is ready for its
  implementation commit and local owner acceptance; nothing remains open.
