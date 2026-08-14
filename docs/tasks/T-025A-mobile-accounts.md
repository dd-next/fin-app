---
id: T-025A
title: Implement mobile Accounts and account lifecycle
status: done
size: M
spec: design/Finnapp mobile specification/spec/03-screens.md §3.1; spec/04-sheets.md account catalogue
blocked-by: [T-024B]
branch: task/T-025A-mobile-accounts
base-commit: 27a80e97e71ea110197950025be5b06a67f8f51b
implementer: /root, Codex GPT-5
readiness-reviewed-by: /root/phase15_readiness_review, Codex GPT-5 same-vendor fallback
readiness-reviewed-commit: deb8a5a
readiness-verdict: ready
---

## Goal

Make Accounts and its account detail/create/edit/reconcile/archive/history flows
usable at 390×844 through accepted APIs while preserving desktop.

## Acceptance

- [x] Mobile Accounts implements the exact 44px header, 72px single-surface
      capital strip, optional 44px rate warning, storage groups, 64px rows,
      56px New account row, permitted long-list scroll, and exact empty state.
- [x] Every visible account appears once: cash storage → `CASH`; crypto
      asset/storage → `CRYPTO`; everything else → `BANK`.
- [x] Total capital, Available, balances, valued amounts, `Not valued`, and
      `protected` derive only from `/api/v1/accounts/summary` and use separate
      non-wrapping value/currency elements.
- [x] The warning is hidden only with no unvalued assets and opens the shared
      Set-a-rate entry point owned by T-025B.
- [x] Account details, Add/Edit, Reconcile, Archive, recent history, and
      `Full history` → account-filtered Transactions are API-backed.
- [x] Archive uses branded confirmation ending `History is kept.` and does not
      promise restoration. Permission-driven actions are absent when denied.
- [x] Mobile has no restoration, ownership transfer, category management or
      automatic-rate implementation in this task.
- [x] Desktop account fields/cards, account-filtered history, permissions and
      existing Account behavior remain functional.
- [x] No backend/schema or other feature-screen work is added.

## Touches

`app/static/index.html`, `app/static/app.js`, `app/static/style.css`,
`tests/test_mobile_accounts_ui_v21.py`, `tests/test_frontend_v2.py`, design notes,
and task lifecycle evidence.

## Out of scope

Profile, categories, rate form, sharing/invitations and logout (T-025B);
Transactions composition, Operations/periods, Plan/Analytics, backend/schema,
T-015/T-016/T-017.

## Verification

```bash
.venv/bin/python -m pytest -q tests/test_mobile_accounts_ui_v21.py tests/test_frontend_v2.py tests/test_foundation_v2.py tests/test_valuation_v2.py tests/test_phase12_privacy_v2.py
node --check app/static/app.js
git diff --check
```

Use `verify` for normal/many/empty Accounts and all named lifecycle flows at
390×844, plus preserved Accounts behavior at 1280×900.

## Review

### Bounded implementation review

- Reviewer: `/root/t025a_accounts_review`, Codex GPT-5 same-vendor fallback;
  cross-vendor review was unavailable. Read-only; no files or Git state were
  changed.
- Reviewed range: uncommitted implementation from claim HEAD
  `e8929e942fc742948b23639502f677e314041cee`; tracked
  `app/static/app.js`, `app/static/index.html`, `app/static/style.css` and
  direct inspection of untracked `tests/test_mobile_accounts_ui_v21.py`.
- Verbatim findings:

  > [P1] Required Saved confirmation is skipped for all mobile account Save flows. `app/static/app.js:1518-1520` (Add/Edit) and `1565-1567` (Reconcile) close the entire overlay stack and show a toast immediately after success. The mobile acceptance contract says every Save ends in the branded `Saved` confirmation with one `Done` action, and spec/04-sheets includes that confirmation primitive. Browser happy-path evidence therefore exercised behavior that is itself off-contract. Add runtime/static coverage asserting Saved remains the top overlay after each successful Save and Done closes it.
  >
  > [P1] Frozen Account copy is replaced with invented copy in three reviewed paths. `app/static/index.html:81` says “Keep cash, bank accounts, cards, and crypto in one place.” instead of the exact empty-state line “Cash, cards, wallets, reserves, and crypto all live here.” (`spec/06-content.md:22`); `app/static/app.js:1175` renders “Set a rate for <codes>” instead of the specified count form (`spec/06-content.md:18`); and `app/static/app.js:1542` replaces the exact Reconcile hint (`spec/06-content.md:62`). T-025A explicitly requires the exact empty state and frozen design copy. The new test locks in the wrong empty copy at `tests/test_mobile_accounts_ui_v21.py:22` and does not assert the other two.
  >
  > [P1] Account-detail valued money violates T-025A’s separate, non-wrapping value/currency invariant. `app/static/app.js:1299-1306` builds the valued amount with `formatMoney()` and HTML-escapes it into one text node; unlike Balance/rows/metrics it does not use `moneyMarkup()`. Thus the base currency is not a separate element and `.mobile-money` cannot guarantee non-wrapping. No test inspects detail markup; `tests/test_mobile_accounts_ui_v21.py:43-49` only finds source substrings elsewhere.
  >
  > [P2] Lifecycle failure paths can silently leave stale UI. Archive’s `onAction` at `app/static/app.js:1582-1586` has no catch or inline/toast error path, so a rejected API call produces an unhandled promise and an unchanged confirmation without feedback. Full history at `1591-1596` switches views even though `loadTransactions()` swallows errors (`2343-2351`), so a failed account-filter request can show the previous transaction list under the new account filter. The test file is source-substring-only and covers neither failure. Add rejected-API behavior coverage (confirmation remains with an announced error; history does not navigate/show stale rows).

- Resolution: Add/Edit and Reconcile now refresh then open the branded
  single-`Done` Saved confirmation; frozen empty/rate/Reconcile copy is exact;
  detail valuation uses `moneyMarkup`; confirmation failures remain visible in
  a `role=alert` error; Full history navigates only after a successful load and
  restores both filters on failure. Static coverage and focused scratch-browser
  failure checks cover each behavior.

### Limited re-review

- Reviewer: `/root/t025a_accounts_rereview`, fresh Codex GPT-5 same-vendor
  fallback; cross-vendor review was unavailable. Read-only; no files changed.
- Reviewed scope: only the five resolved behavior/coverage findings in the
  current manifest against claim HEAD `e8929e9`, including the untracked test.
- Verbatim verdict:

  > T-025A limited re-review (fresh same-vendor fallback; cross-vendor unavailable): No P0–P3 findings. Reviewed current manifest against HEAD e8929e942fc742948b23639502f677e314041cee, including direct inspection of untracked tests/test_mobile_accounts_ui_v21.py, limited to the five prior findings. Verified: Add/Edit and Reconcile open Saved confirmation with single default Done action; frozen empty/rate-warning/Reconcile copy matches spec/06-content.md; detail valued amount uses moneyMarkup with separate .mobile-money-value/.mobile-money-code spans; archive rejection is caught in-place, announced via role=alert, and action is re-enabled; failed Full history leaves account sheet/view/URL and transaction rows intact and restores account/period filters. Supplied 390x844 browser evidence corroborates each behavior. Independent targeted rerun: 31 passed in 7.34s. git diff --check for tracked manifest passed. Read-only: no files edited.

### Verification evidence

- Targeted gate:
  `.venv\\Scripts\\python.exe -m pytest -q tests/test_mobile_accounts_ui_v21.py tests/test_frontend_v2.py tests/test_foundation_v2.py tests/test_valuation_v2.py tests/test_phase12_privacy_v2.py`
  → `31 passed in 11.34s`; independent reviewer rerun → `31 passed in 7.34s`.
  Bundled Node `--check app/static/app.js` and `git diff --check` passed.
- `verify` used only fresh migrated scratch database
  `C:\\Users\\A90B~1\\AppData\\Local\\Temp\\finapp-t025a-54e5ae06eeba473c88fe6be7941cde4f\\finapp.db`;
  repository `finapp.db` was never used. Data was created through the visible UI.
- At 390×844, measured geometry was header 44px, metric strip 72px, warning
  44px, group header 24px, rows 64px and New account 56px. Empty, normal and
  seven-row/three-group long-list states rendered with zero horizontal overflow.
- Add/Edit, Reconcile, branded Archive, recent transaction detail, filtered
  Full history and Set-a-rate handoff were exercised. Add and Reconcile ended
  in Saved/Done. Forced network failure left Archive open with announced error;
  failed Full history stayed on Accounts with the detail sheet and filters intact.
  Console was clean and no JavaScript dialog was present.
- At 1280×900, six account cards, existing desktop account detail dialog and
  actions remained functional with zero horizontal overflow. Screenshots:
  `accounts-empty-390x844.png`, `accounts-many-390x844.png`, and
  `accounts-desktop-1280x900.png` in the named scratch directory.

### Final documentation and lifecycle review

- Reviewer: `/root/t025a_final_docs_review`, Codex GPT-5 same-vendor fallback;
  cross-vendor review was unavailable. Read-only; no files or Git state changed.
- Reviewed branch/range: `task/T-025A-mobile-accounts`, base
  `27a80e97e71ea110197950025be5b06a67f8f51b`, claim HEAD
  `e8929e942fc742948b23639502f677e314041cee`, and the complete nine-file
  implementation/test/design/lifecycle manifest including the untracked test.
- Verbatim result:

  > No P0–P3 findings.
  >
  > T-025A is suitable to commit as the task implementation.
  >
  > Verified:
  >
  > - Exact branch/base/claim invariants match.
  > - Complete nine-file manifest is accounted for, including the untracked test.
  > - Task and backlog consistently say `review`; T-025B and all later tasks remain `backlog`.
  > - Acceptance criteria are checked with corresponding test/browser evidence.
  > - Initial findings are literal verbatim copies of the reviewer’s detailed findings; resolutions and limited re-review are accurate.
  > - Session log only appends entries.
  > - `PROGRESS.md` clearly leaves T-025A pending local acceptance and Phase 15 incomplete.
  > - Design-note addition is bounded to T-025A.
  > - No push, deploy, archive, acceptance commit, or Phase 15 commit occurred.
  > - Scratch evidence names a temporary database and explicitly excludes repository `finapp.db`.
  > - Implementation remains within Accounts/account-lifecycle scope.
  > - Independent targeted rerun: `31 passed in 13.52s`.
  > - `git diff --check` passed; worktree manifest remained unchanged.
  > - Latest supplied bundled Node syntax gate passed. The optional independent bundled-runtime lookup stalled and was terminated without changing state.

- Limited transcription re-review, verbatim:

  > No P0–P3 findings.
  >
  > The appended final review preserves my prior response verbatim. Only [T-025A-mobile-accounts.md](C:/Users/Ксюша/Documents/Codex/fin-app/docs/tasks/T-025A-mobile-accounts.md) changed since the review; all other manifest diff sizes remain unchanged.
  >
  > No status, acceptance, successor promotion, push, deploy, archive, or phase-completion overclaim was introduced. `git diff --check` passes.

## Session log

- 2026-08-12 Codex GPT-5: split from overloaded T-025 after readiness review;
  not claimed.
- 2026-08-12 Codex GPT-5: limited independent re-review verdict `ready`; remains
  blocked by T-024B.
- 2026-08-13 repository owner authorisation executed by Codex GPT-5: promoted
  readiness-ready T-025A to `todo`, atomically claimed
  `task/T-025A-mobile-accounts` from accepted integration `27a80e9`, and
  recorded `/root` as implementer.
- 2026-08-13 `/root`, Codex GPT-5: implemented mobile Accounts and the bounded
  account lifecycle over accepted APIs while preserving desktop. All initial
  P1/P2 findings are resolved; limited re-review has no findings. Targeted
  31-test, JavaScript, diff and scratch-browser gates pass. Task is `review`,
  awaiting authorised local acceptance; no open questions.
- 2026-08-13 repository owner authorisation executed by `/root`, Codex GPT-5:
  locally accepted reviewed implementation commit `2b3af12` by fast-forward
  into `finapp-v2-develop`; T-025A is `done`. No successor task was promoted or
  claimed in this acceptance checkpoint; no push, deploy, archive, or Phase 15
  commit was created.

### Local acceptance lifecycle review

- Reviewer: `/root/t025a_acceptance_review`, Codex GPT-5 same-vendor fallback;
  cross-vendor review was unavailable. Read-only; no files or Git state changed.
- Verbatim result:

  > T-025A final read-only local-acceptance lifecycle review — same-vendor fallback; cross-vendor unavailable.
  >
  > No P0–P3 findings.
  >
  > Suitable to commit as the local acceptance checkpoint.
  >
  > Verified read-only:
  > - `finapp-v2-develop` and `task/T-025A-mobile-accounts` both resolve to implementation commit `2b3af12eb6918a76e19a7d43b6d87cca48b685cd`.
  > - Exact ancestry is integration base `27a80e97e71ea110197950025be5b06a67f8f51b` → claim `e8929e942fc742948b23639502f677e314041cee` → implementation `2b3af12`; `git merge-base --is-ancestor` passes, and the integration reflog records `merge task/T-025A-mobile-accounts: Fast-forward`.
  > - The only uncommitted files are `docs/tasks/T-025A-mobile-accounts.md`, `docs/BACKLOG.md`, and `docs/PROGRESS.md`; no staged changes exist.
  > - Task and backlog consistently transition `review` → `done`; the appended session log accurately states local fast-forward acceptance of `2b3af12` and preserves the prior append-only entries.
  > - `PROGRESS.md` accurately reports no active task, T-025A locally accepted, T-025B next, and Phase 15 incomplete; it does not claim the usable-preview boundary or phase close.
  > - T-025B remains `backlog`, has blank base/implementer, and no local T-025B branch exists; all later Phase 15 tasks remain backlog.
  > - No task archive, phase-completion commit, push, or deploy is claimed. Origin remains at `71e3396`, while local integration is ahead by the expected promotion/claim/implementation chain.
  > - Recorded targeted gate remains `31 passed`; bundled Node syntax and `git diff --check` are recorded passed. Current `git diff --check` also passes (only LF→CRLF informational warnings).
  > - Worktree and Git state were not changed.
  >
  > My bounded review goal completed in 83 seconds with 28,042 tool-reported tokens used.

- Initial transcription re-review found one P3 omission: the final usage
  sentence above. It was appended without changing behavior or coverage.
- Resolved-P3 re-review, verbatim:

  > Resolved-P3 re-review: No P0–P3 findings. The exact omitted usage sentence is now appended, so the detailed response is fully verbatim. Only the expected three acceptance documents remain modified, and `git diff --check` exits 0 (LF→CRLF informational warnings only). Read-only; no state changed.
