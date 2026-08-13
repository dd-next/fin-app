---
id: T-028
title: Implement mobile Plan flows and Analytics placeholder
status: review
size: M
spec: specs/FinnApp-v2.md §8; design/Finnapp mobile specification/spec/03-screens.md §3.4–§3.5; spec/04-sheets.md
blocked-by: [T-019, T-024B]
branch: task/T-028-mobile-plan-analytics
base-commit: 39e3cf673887d2571ae658d5bb5f6fdef005f9d6
implementer: /root, Codex GPT-5
readiness-reviewed-by: /root/phase15_readiness_review, Codex GPT-5 same-vendor fallback
readiness-reviewed-commit: deb8a5a
readiness-verdict: ready
---

## Goal

Implement accepted mobile Plan rule/occurrence workflows and the exact Analytics
placeholder without creating ledger effects or inventing analytics.

## Acceptance

- [ ] Plan follows active `FinnApp-v2.md` §8: one card per rule, not the older
      global Upcoming layout. A card shows at most nearest overdue and nearest
      future; multiple overdue shows total count; remaining history is details.
- [ ] Open/Completed/Show stay compact; empty copy matches spec.
- [ ] Add/Edit uses `mobile_kind`, exact Decimal amount, asset, recurrence,
      first due, supported category, and one `account_id` adapter.
- [ ] Expected income labels `To account`; expense/transfer kinds label
      `From account`.
- [ ] An unresolved item shows Edit rule, Skip, Link transaction in one row and
      that order. Skip affects only one occurrence.
- [ ] Link offers eligible posted transactions by semantic type, does not
      enforce account/asset equality, and creates no fake transaction.
- [ ] Branded Delete archives the rule; linked transactions remain, future/open
      items disappear as accepted. Pay/Receive and category merge/delete stay
      absent.
- [ ] Plan never changes balances, Total capital, Available, periods, or Undo.
- [ ] Analytics renders exact header/avatar and Coming soon copy with no charts,
      filters, ranges, data fetches or invented values; avatar opens Profile.
- [ ] Desktop full rule/occurrence history and supported behavior remain
      functional.
- [ ] No backend/schema, automatic payment, full analytics, or
      T-015/T-016/T-017 work is added.

## Touches

`app/static/index.html`, `app/static/app.js`, `app/static/style.css`,
`tests/test_mobile_plan_analytics_ui_v21.py`, `tests/test_frontend_v2.py`, design
notes, and task lifecycle evidence.

## Out of scope

Backend/schema, transaction creation, automatic payment, category merge/delete,
other feature screens, full analytics.

## Verification

```bash
.venv/bin/python -m pytest -q tests/test_mobile_plan_analytics_ui_v21.py tests/test_frontend_v2.py tests/test_mobile_plan_contract_v21.py tests/test_plan_v2.py tests/test_planned_transaction_feed_v21.py tests/test_phase12_privacy_v2.py
node --check app/static/app.js
git diff --check
```

Use `verify` for populated/empty Plan, nearest occurrences/count, all three item
actions, Add/Edit/Delete with dynamic labels, eligible cross-account/asset Link,
Analytics/Profile at 390×844, and desktop Plan regression.

## Review

Implementation reviewer: `/root/t028_review_retry`, Codex GPT-5 fresh
same-vendor fallback; cross-vendor review was unavailable.

Reviewed range: claim commit
`f6641c81d67ef97b89f634fd65187d5b27eb8be0` plus the complete uncommitted
manifest: modified `app/static/index.html`, `app/static/app.js`,
`app/static/style.css`, `docs/design/DESIGN-NOTES.md`, and direct inspection of
untracked `tests/test_mobile_plan_analytics_ui_v21.py`. The reviewer remained
read-only and did not alter files or Git state.

Initial review findings, verbatim:

> - **[P2] Link can silently attach the first candidate without explicit user selection.** In [app/static/app.js](C:/Users/Ксюша/Documents/Codex/fin-app/app/static/app.js:4144), `draft.occurrenceId` and `draft.transactionId` default to `occurrences[0]` / `transactions[0]`; the primary action at lines 4190–4200 immediately submits those IDs. Thus opening Link from a Plan item and pressing “Link transaction” without choosing a transaction links the first eligible row, while opening from a transaction can similarly link the first occurrence. This is unsafe for a financial association and contradicts the Choose-driven form semantics. Initialize whichever side was not explicitly supplied to `null`, show “Choose …”, and require an explicit choice before enabling/submitting. The source-only test at [tests/test_mobile_plan_analytics_ui_v21.py](C:/Users/Ксюша/Documents/Codex/fin-app/tests/test_mobile_plan_analytics_ui_v21.py:121) does not cover this; add an interaction test proving no POST occurs until the missing side is explicitly selected.
>
> - **[P2] The async Link candidate load can reopen a stale sheet after navigation.** [app/static/app.js](C:/Users/Ксюша/Documents/Codex/fin-app/app/static/app.js:4128) awaits the posted-transaction request before calling `openMobileSheet` at line 4184, but records no overlay/view/workspace request context and performs no stale-response check. `switchView` closes overlays at lines 635–640, so a user can tap “Link transaction,” switch tabs while the request is pending, and have the resolved request open the Plan Link sheet over the new tab with a detached opener. Capture a request/context token and verify the initiating Plan item/view/workspace is still active before mutating state or opening the sheet. Add a deferred-request UI test covering tab switch or sheet dismissal before resolution; the current new tests contain no async race coverage.
>
> No P0, P1, or P3 findings. Review was read-only against `f6641c81d67ef97b89f634fd65187d5b27eb8be0` and the stated uncommitted manifest.

Resolution: the unspecified Link side now starts `null`, its field reads
`Choose …`, and the sheet primary remains disabled until both explicit IDs
exist. Candidate loading captures workspace, active view, and connected opener,
and discards stale success or failure before state mutation, error display, or
sheet opening. Focused source guards freeze both behaviors; the isolated
browser confirmed disabled Link before selection and enabled Link only after
choosing an eligible posted VND expense for the USD Plan item.

Limited re-review, verbatim:

> No findings. Both prior P2 findings are closed:
>
> - Link now requires explicit selection of the unspecified side and keeps the primary action disabled until both IDs exist.
> - Async candidate loading now discards stale success and error responses before state mutation or sheet opening when workspace, view, or opener context changes.
>
> The limited resolution diff introduces no P0–P3 regression. Focused tests cover both guards, and the reported 35-test, Node syntax, diff, and scratch-browser evidence is sufficient for this re-review.

Final verdict: approved with no open P0–P3 finding.

Verification evidence:

- Exact task target: `35 passed in 11.82s`.
- Bundled Node `--check app/static/app.js`: passed.
- `git diff --check`: passed; LF→CRLF notices only.
- Isolated scratch `/health` and SPA: HTTP 200; repository `finapp.db` was not
  touched.
- Mobile 390×844: populated and empty Plan, exact Open/Completed and empty
  copy, one card per rule, nearest future/overdue plus total overdue badge,
  compact Show and full occurrence history, Add/Edit/Saved, exact ordered
  Edit rule/Skip/Link transaction row, one-occurrence Skip, explicit Link
  selection, branded Delete, and exact Analytics/Profile passed. A USD 9.99
  planned occurrence linked to a posted VND 149000 transaction; actual asset
  remained VND and USD/VND balances stayed `2500.00`/`4851000`.
- Mobile document/body width both equalled the 390px viewport; no horizontal
  overflow was present.
- Desktop 1280×900 retained cards, Add/Edit, compact Show, full occurrence
  history/filter, Link, Skip, and archive actions.
- The isolated server, database, and screenshots were removed after the run.

## Session log

- 2026-08-12 Codex GPT-5: task specified for batch readiness; not claimed.
- 2026-08-12 Codex GPT-5: independent batch readiness verdict `ready`; remains
  blocked by T-024B.
- 2026-08-13 repository owner authorisation executed by `/root`, Codex GPT-5:
  confirmed T-019 and T-024B accepted, accepted T-028 readiness evidence, and
  promoted T-028 from `backlog` to `todo` on accepted integration `0630535`;
  no task branch was claimed in this checkpoint.
- 2026-08-13 repository owner authorisation executed by `/root`, Codex GPT-5:
  atomically claimed `task/T-028-mobile-plan-analytics` from promoted
  integration `39e3cf6`, recorded `/root` as implementer, and started only
  T-028.
- 2026-08-13 `/root`, Codex GPT-5: implemented the bounded mobile Plan rule and
  occurrence surfaces plus the exact data-free Analytics placeholder; retained
  desktop Plan. The exact 35-test target, syntax/diff checks, isolated mobile
  and desktop browser matrix passed. Independent same-vendor fallback review
  closed both Link-safety P2 findings and its limited re-review returned no
  P0–P3 findings. T-028 is ready for local owner acceptance.
