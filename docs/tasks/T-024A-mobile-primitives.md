---
id: T-024A
title: Build reusable mobile visual primitives
status: done
size: M
spec: design/Finnapp mobile specification/spec/01-foundations.md; spec/02-components.md
blocked-by: [T-023]
branch: task/T-024A-mobile-primitives
base-commit: 818f864
implementer: Codex GPT-5
readiness-reviewed-by: /root/phase15_readiness_review, Codex GPT-5 same-vendor fallback
readiness-reviewed-commit: deb8a5a
readiness-verdict: ready
---

## Goal

Provide one token-backed primitive contract for mobile headers, rows, metrics,
Operations controls, fields, money presentation, and buttons without changing
business workflows.

## Acceptance

- [x] Shared production primitives cover screen/list/group headers, list/ghost
      rows, Accounts/Plan metric strips, active/absent 96px Operations cards,
      segmented controls, chip lanes/chips, form/sheet/amount/error fields, and
      primary/secondary/inline/destructive buttons.
- [x] Heights, radii, spacing, type, colors, two-surface limit, and hairlines
      match specs 01–02; metric strips are one surface, never nested cards.
- [x] Both Operations-card states remain exactly 96px; switching segment does
      not move anything above it.
- [x] Interactive wrappers are semantic and ≥44px; chips are 36px inside a
      44px lane.
- [x] Existing asset-precision string formatting is preserved; money uses
      tabular non-wrapping numerals and a separate muted currency suffix. No new
      `Number`/`parseFloat` financial calculation is introduced.
- [x] Long names truncate without wrapping or widening the viewport.
- [x] Primitive styles are mobile-scoped; representative real Accounts,
      Operations, and Plan DOM exercises them without a hidden demo gallery.
- [x] Existing API calls, submit handlers, permissions, and desktop behavior at
      1280×900 remain intact.
- [x] `DESIGN-NOTES.md` records the primitive/tokens actually introduced.

## Touches

`app/static/index.html`, `app/static/style.css`, only bounded rendering helpers
in `app/static/app.js`, `tests/test_frontend_v2.py`,
`tests/test_phase15_primitives.py`, `docs/design/DESIGN-NOTES.md`, and task
lifecycle evidence.

## Out of scope

Overlay state; sheets/pickers/confirmations/focus trapping; complete feature
screens; swipe/software-keyboard behavior; backend/API/schema changes.

## Verification

```bash
.venv/bin/python -m pytest -q tests/test_frontend_v2.py tests/test_phase15_primitives.py
node --check app/static/app.js
git diff --check
```

Use `verify` on a scratch DB at 390×844 for representative primitives and both
period-card states, then a functional 1280×900 desktop smoke.

## Review

Append the bounded independent implementation review following the repository
protocol.

### Atomic claim review

- Reviewer: `/root/t024a_claim_review`, Codex GPT-5 same-vendor fallback;
  cross-vendor reviewer was unavailable.
- Reviewed scope: branch/base invariants and the complete lifecycle diff in
  this task, `docs/BACKLOG.md`, and `docs/PROGRESS.md`.
- Verbatim result:

  > Read-only review of T-024A atomic claim: **No findings (P0–P3).**
  >
  > Verified:
  >
  > - Branch `task/T-024A-mobile-primitives` is at `818f864`; reflog confirms
  >   it was created from that commit.
  > - Accepted integration `finapp-v2-develop` is also at `818f864`.
  > - At the accepted base, T-023 is `done` and T-024A was readiness-ready
  >   `todo`.
  > - Current lifecycle diff contains only the three expected documentation
  >   files.
  > - Task, backlog, and progress consistently record `in-progress`.
  > - `base-commit: 818f864`, `implementer: Codex GPT-5`, exact branch,
  >   dependency, and session log are correct.
  > - No implementation or acceptance overclaim.
  > - `git diff --check` passes.
  >
  > This reviewed lifecycle diff should be committed unchanged as the first
  > T-024A task commit before implementation begins. Reviewer:
  > `/root/t024a_claim_review`, Codex GPT-5 same-vendor fallback.

### Test-contract finding history

All test-contract reviewers were Codex GPT-5 same-vendor fallbacks because a
cross-vendor reviewer was unavailable. They remained read-only throughout.

#### `/root/t024a_tests_review` — initial findings, verbatim

> P0: None.
>
> P1: None.
>
> P2 findings:
>
> 1. **[P2] Geometry coverage is neither exact nor sufficiently complete.**
>    `tests/test_phase15_primitives.py:31-88` checks a small subset of the required geometry and frequently asserts `min-height` where specs require exact heights. A 100px list row, 80px field, or oversized button would pass. The tests omit the 56px ghost row, 72px Accounts/64px Plan strip distinction, metric divider/no-nested-surface structure, Operations active/absent states and equal-height transition, row/icon geometry, field-sheet and error variants, key radii/padding/type rules, and several button variants. This leaves substantial T-024A acceptance at `docs/tasks/T-024A-mobile-primitives.md:24-31` unprotected.
>
> 2. **[P2] The money test does not verify precision behavior or separate currency presentation.**
>    `tests/test_phase15_primitives.py:77-91` only searches for two pre-existing implementation fragments. Those fragments already exist in the red baseline, while current `formatMoney()` still returns one combined string (`app/static/app.js:87-90`). The test would pass without proving 0/2/high-precision outputs, preservation of input strings, a distinct muted currency-suffix DOM node, or absence of newly introduced `Number`/`parseFloat` financial conversion. Add behavioral formatting cases and inspect the rendered value/suffix structure.
>
> 3. **[P2] “Real DOM” and semantic-target assertions are raw substring checks that are not associated with the actual controls.**
>    `tests/test_phase15_primitives.py:94-128` can pass if the expected class strings appear in comments, dead templates, or unrelated nodes. `.mobile-interactive` is never required on any real element, while `role="tab"` and `aria-selected="true"` already occur in the pre-change Operations markup and do not prove primitive wrappers are semantic or ≥44px. Parse the static DOM, associate classes/roles with the intended elements, and cover dynamically rendered Accounts/Plan structures in a way that cannot be satisfied by an unused gallery or dead string.
>
> 4. **[P2] Mobile scoping and desktop isolation have no regression contract.**
>    No assertion verifies that the primitive rules are confined to the mobile media scope, and no test protects the existing 1280×900 selectors/DOM from being replaced or globally restyled. An implementation could add every asserted rule globally, break desktop, and pass all four tests. The later browser smoke remains necessary, but this regression block should at least prove primitive declarations are mobile-scoped and preserve the desktop contract named at `docs/tasks/T-024A-mobile-primitives.md:38-41`.
>
> 5. **[P2] The CSS helper overfits spelling while still allowing cascade loopholes.**
>    `tests/test_phase15_primitives.py:8-11` requires a standalone selector and literal declaration text. Equivalent token-backed declarations, grouped selectors, or harmless whitespace differences fail, while a compliant-looking first rule followed by a noncompliant override passes. Token checks at lines 17–29 can likewise be satisfied in comments or unused scopes. Use a CSS-aware representation or narrowly normalize declarations and inspect the effective mobile rule/cascade.
>
> P3: None.

Resolution: replaced raw substring checks with balanced CSS parsing and a DOM
ancestry parser; added exact geometry/state/type/color assertions, executable
fiat/crypto formatting cases and forbidden-conversion checks, dynamic complete
`.mobile-*` scope enforcement, and preserved desktop declaration/cascade gates.

#### `/root/t024a_tests_rereview` — findings, verbatim

> - **[P2] CSS extraction still does not establish effective declarations or reliable scope boundaries.** `tests/test_phase15_primitives.py:23-36,65-66` merges only rules whose selector text exactly matches the requested selector; it ignores declarations from generic, compound, and more-specific selectors that determine the actual computed result. Additionally, `after_mobile` is sliced by the length of the block body from a string that still includes the opening syntax, so it is not the exact suffix after the media block. A conflicting declaration can therefore escape the claimed “effective/mobile-scoped” check.
>
> - **[P2] The geometry assertions remain materially incomplete and one assertion conflicts with the named component specification.** `tests/test_phase15_primitives.py:102-181` expects `.mobile-screen-header` padding `0`, while `spec/02-components.md` specifies `padding: 0 16px`; the strict dictionary also omits the specified `display:flex` and `justify-content:space-between`. Most other primitives are checked only for height. Operations cards are not checked for the required `padding:10px 14px 12px` or `justify-content:space-between`, and a larger inherited `min-height`—notably the existing mobile `.metric-card` rule—can make a card render above 96px while these tests pass. Button radii/type/colors and several other accepted exact primitive properties are likewise unprotected.
>
> - **[P2] The tests do not prove that representative production DOM actually exercises the primitives.** `tests/test_phase15_primitives.py:201-247` uses a flat element list without ancestry. It does not associate the metric strips with `view-accounts`/`view-plan` or their live value IDs, does not assert a `.mobile-screen-header` production wrapper, and never associates `.mobile-ops-card` or its active/absent states with Operations DOM/rendering. Empty or hidden matching wrappers could satisfy the test while the visible UI remains unchanged. String fragments inside named renderer functions also do not establish the resulting node hierarchy.
>
> - **[P2] The financial-format regression check does not close the forbidden-conversion/precision concern.** `tests/test_phase15_primitives.py:249-267` forbids `Number`, `parseFloat`, and `toFixed` only inside the new `moneyParts` function. Introducing any of them into `formatNumber`, which performs the actual formatting, still passes. The `fraction.padEnd` assertion is global rather than bounded to `formatNumber`, and there are no exact string-output cases covering fiat and high-precision crypto values. This remains a financial-correctness blocking P2.
>
> - **[P2] Mobile scoping and desktop isolation are not sufficiently protected.** `tests/test_phase15_primitives.py:84-99` checks only a subset of the introduced primitive selectors; field/button variants, money parts, truncation, interaction, metric children, and other production classes may be defined outside the mobile media query without detection. `tests/test_phase15_primitives.py:268-271` proves only that four legacy desktop selectors still exist, not that their declarations or 1280×900 behavior remain intact.
>
> No P0, P1, or P3 findings. No out-of-scope backend, sheet/overlay, picker, or workflow requirement was introduced by this test block.

Resolution: corrected the balanced media suffix, exact header/card rules and
min/max geometry; added ancestry-bound production DOM/render checks, bounded
`formatNumber` execution, whole-stylesheet scoping, and desktop declaration plus
runtime gates. Final supplement verdict: all five P2 findings closed.

#### `/root/t024a_tests_rereview2` — findings, verbatim

> - **[P2] Two assertions encode the wrong or incomplete button/ghost-row visual contract.** At `tests/test_phase15_primitives.py:163-165`, the test requires `border-style: dashed` on `.mobile-ghost-row`, but `spec/02-components.md:21` requires the **28×28 leading tile** to be dashed while the 56px row has no divider. At `tests/test_phase15_primitives.py:215,229-230`, `.mobile-button-destructive` is required to use the solid destructive-confirm fill/label, while T-024A excludes confirmations and `spec/02-components.md:74-76` separately defines the in-scope destructive inline action as the 44px inline primitive with translucent negative fill, negative border, and negative text. The test needs distinct assertions/classes for destructive inline versus the later confirmation action, rather than forcing one ambiguous class into the confirm treatment.
>
> - **[P2] Exact geometry/type/color coverage remains materially incomplete despite the added min/max checks.** `tests/test_phase15_primitives.py:146-242` still permits non-compliant primitives: list rows need not be `display:flex`/centered; the ghost tile itself is not checked; group-header tracking/color and optional-count type are absent; metric strips lack exact min/max/radius and per-column padding/type/accent checks; Operations cards omit surface/border colors, 26px top lines, active/absent dot/text/value styles, transparent absent fill, and the 36px Start control; segmented children, chip padding/type/colors, field background/border/padding/focus, error border/value/disabled-submit state, and secondary/inline button padding/border/type/colors are not protected. This falls short of T-024A’s explicit “heights, radii, spacing, type, colors” requirement at task lines 28–29 and specs 01–02.
>
> - **[P2] Production-DOM checks still do not establish semantic interactive Operations cards/header affordances or exclude nested metric surfaces.** At `tests/test_phase15_primitives.py:250-285`, titles and metric values now have useful view ancestry, and Operations cards now have row ancestry. However, the account and period cards are checked only for classes, not a semantic button/role, accessible name, or `.mobile-interactive`; a non-interactive `<div>` would pass even though both cards open controls and T-024A requires semantic wrappers. The header check does not require exactly one 44×44 affordance or Plan’s accent `+`. Metric values merely need some `.mobile-metric` ancestor, so an extra nested `.metric-card` surface can still satisfy the test despite the one-surface prohibition. The renderer checks at lines 306–307 do now cover both period state toggles correctly.
>
> - **[P2] Mobile scoping remains bypassable and omits primitive classes the same test requires.** `tests/test_phase15_primitives.py:10-41,141-143` correctly uses the balanced media endpoint now, but its outside-media regex detects only selector clauses beginning exactly with a listed selector. Global `.app-view .mobile-field`, `.mobile-field:focus`, or other compound primitive rules escape detection. The list also omits `.mobile-row-title`, `.mobile-surface`, and `.mobile-money-value`, although lines 300, 304, and 311 require production code to introduce those primitive classes. Consequently, not all introduced primitive styling is guaranteed mobile-scoped.
>
> No P0, P1, or P3 findings.
>
> The earlier formatter P2 is closed by the bounded forbidden-conversion checks plus executable 0/2/8-decimal cases. The earlier desktop declaration concern is adequately improved at the unit-contract level by the legacy snapshots and mobile resets; the required 1280×900 browser smoke remains the runtime gate.

Resolution: moved the dashed border to the 28px tile, split inline and confirm
destructive contracts, completed exact visual assertions, required semantic
group/label/header ownership and a single surface, and dynamically rejected all
`.mobile-*` CSS outside the balanced mobile block. All four P2 findings closed.

#### `/root/t024a_tests_rereview3` — findings, verbatim

> - P2 — The exact visual contract remains incomplete. Assertions omit several required values: screen/row typography, ghost-label color, Operations top-line typography, segmented equal-flex and idle state, chip-lane spacing and idle border, sheet-field and error-line typography, amount suffix, button text colors/full width, and destructive-confirm styling. See `tests/test_phase15_primitives.py:174-321`.
> - P2 — DOM checks do not fully prove semantics or the no-nested-surface rule. `aria-labelledby` is only checked as non-empty, header controls need no accessible name, and nested `mobile-surface`/`metric-card` wrappers can pass because only `mobile-metric-strip` ancestors are counted. See `tests/test_phase15_primitives.py:356-382`.
> - P2 — Mobile scoping covers only classes manually listed in `PRIMITIVE_SELECTORS`; a newly introduced `mobile-*` implementation class omitted from that set could be globally or compound-scoped outside the mobile media block undetected. See `tests/test_phase15_primitives.py:166-171`.
>
> Closed from the prior review:
>
> - Ghost row requires a dashed tile and no divider.
> - Destructive inline action is a distinct 44px primitive with exact destructive colors.
>
> Verification:
>
> - Baseline: `6 failed, 1 passed`, appropriately red.
> - `git diff --check`: passed.
> - P0/P1/P3: none.

Resolution: added every omitted exact declaration; resolved labels to real
descendants and required real header accessible names; asserted one strip,
surface, and metric ancestor; replaced the allowlist-only scope check with
dynamic complete CSS discovery. All three P2 findings closed.

#### `/root/t024a_tests_rereview4` — findings, verbatim

> Fourth review complete: 2 P2 remain, no P0/P1. P2-A11y at test line 415: `aria-label or id` accepts id as accessible name; parser captures no text, so icon-only unnamed header control passes. Require real name via aria-label/aria-labelledby target or parsed visible text. P2-contract at lines 251-280/283-354: exact CSS checks still permit materially broken primitives—ops card asserts `justify-content` but not `display:flex`/column; segmented parent omits required display and surface fill; sheet/amount fields omit required fill/border/layout; and there is no 48px sheet-primary primitive/check at all (only 50px submit primary). These are explicit spec/02 component requirements, so dead/inert CSS can pass. Dynamic whole-CSS auto-scope check is sound; card aria-labelledby-descendant checks are sound; metric single-surface check is present (though stronger same-node assertion would help). Evidence: baseline `tests/test_frontend_v2.py` 7 passed; red suite 6 failed, 1 passed for expected absent implementation; `node --check` passed; `git diff --check` and untracked `git diff --no-index --check` passed. Same-vendor fallback, read-only, no edits.

Resolution: required a nonempty `aria-label`; added functional flex/column,
segment surface, field layout/fill/border, and distinct 48px sheet-primary
contracts. Limited fifth re-review, verbatim:

> Limited fifth read-only re-review: no findings (P0–P3). Both prior P2s are closed. Header controls now require a truthy aria-label; ops contract requires flex/column; segmented requires flex/surface; sheet and amount fields require display/alignment/surface/border; distinct 48px `.mobile-button-sheet-primary` is present in selector inventory and exact geometry/type/color assertions. Baseline 7 passed; red suite remains 6 failed/1 passed solely on absent production primitives; node check passed; tracked plus untracked diff checks passed. Same-vendor fallback; no edits.

### Implementation review

- Reviewer: `/root/t024a_impl_review`, Codex GPT-5 same-vendor fallback;
  cross-vendor reviewer was unavailable.
- Reviewed scope: complete uncommitted T-024A manifest in
  `app/static/index.html`, `app/static/style.css`, `app/static/app.js`,
  `docs/design/DESIGN-NOTES.md`, `tests/test_frontend_v2.py`, and
  `tests/test_phase15_primitives.py`.
- Initial findings, verbatim:

  > - **P1 — The Operations account balance is hidden on mobile and newly exposed on desktop, the inverse of the required behavior.** `index.html:114` adds the ledger-derived balance and `app.js:359-362` populates it, but `style.css:494` hides `.mobile-ops-balance` only inside the mobile media query. Therefore the 96px mobile account card shows the account selector but omits the required bottom “Balance” label/value, while desktop gains an extra unspecific grid child that can displace the existing Undo control into another row. This violates both spec 02’s account-card contract and T-024A’s preserved-desktop criterion. Add coverage for computed visibility/layout at 390×844 and 1280×900.
  >
  > - **P1 — The money primitive is not insulated from existing descendant selectors, so required production typography/layout is not what the tests assert.** `app.js:96-99` inserts nested spans into Accounts metrics (`app.js:858-859`) and Plan rule metadata (`app.js:1292`). Existing `.metric-card span` at `style.css:129` has greater specificity than `.mobile-money-value`/`.mobile-money-code` at `style.css:528-529`, reducing the Accounts metric value from the required 20/600 to `.85rem`/700 and overriding the suffix contract. Likewise existing `.rule-card span` makes every nested Plan money span block-level, so value and currency no longer form one inline, non-wrapping amount. The saved Accounts screenshot visibly shows the undersized metric values; no populated Plan rule was browser-checked. The tests at `tests/test_phase15_primitives.py:242-246` and `443-467` inspect isolated declarations/source fragments rather than the effective cascade, so they pass despite the regression.
  >
  > - **P2 — The Start period control’s effective height is 44px, not the specified 36px visual inside its 96px card.** `.mobile-start-period` declares `height/min-height: 36px` at `style.css:485`, but the same button also has `.mobile-interactive`, whose later `min-height:44px` at `style.css:531` wins in the cascade. The test at `tests/test_phase15_primitives.py:281-282` checks only the isolated selector and misses the combined element. Preserve a semantic ≥44px hit wrapper while keeping the visible control at 36px, and test the effective element geometry.
  >
  > - **P2 — The supplied browser evidence does not cover the final reviewed CSS manifest.** Both saved mobile screenshots predate the final `style.css` modification (`18:44:52`/`18:45:53` versus `18:46:22`). The Operations screenshot still shows the header that final CSS now hides, confirming it is stale relative to this diff. Repeat the scratch-database 390×844 and 1280×900 checks after fixes against the exact reviewed manifest.
  >
  > No P0 or P3 findings. No backend/API/schema/handler changes were present. Decimal-string formatting and escaping remain intact, and the existing owner-only period guard continues to prevent shared-account period disclosure.

- Resolution: made the compact balance desktop-hidden/mobile-visible and
  refreshed it synchronously on account changes; narrowed global metric label
  styling and introduced dedicated Plan metadata styling; separated the 44px
  semantic Start target from its 36px visual; repeated final scratch runtime
  measurements after the last CSS/JS fixes. Dedicated regressions cover each
  issue.
- Verbatim final result:

  > Final limited read-only re-review of T-024A production primitives: **No findings (P0–P3).**
  >
  > Reviewer: `/root/t024a_impl_review`, Codex GPT-5 same-vendor fallback; cross-vendor reviewer unavailable.
  >
  > Reviewed current complete uncommitted manifest:
  >
  > - `app/static/index.html`
  > - `app/static/style.css`
  > - `app/static/app.js`
  > - `docs/design/DESIGN-NOTES.md`
  > - `tests/test_frontend_v2.py`
  > - untracked `tests/test_phase15_primitives.py`
  >
  > Verified the prior findings are closed:
  >
  > - Mobile Operations exposes the selected account’s exact API-provided ledger balance; desktop hides the compact balance and preserves the legacy toolbar.
  > - Account switching updates the balance synchronously from the newly selected account without `Number`, `parseFloat`, `float`, rounding, API, ledger, permission, or period-contract changes.
  > - Money values preserve exact asset-precision string formatting, escaping, tabular non-wrapping layout, and a separate muted suffix on mobile.
  > - Direct-child desktop selectors prevent nested money spans from inheriting metric-label styling.
  > - Dedicated `.plan-rule-meta` preserves the legacy desktop metadata line while nested money remains inline; mobile explicitly preserves metadata block layout and inline-flex money.
  > - Start period has a semantic 44px button target around the specified 36px visual control.
  > - Active and absent Operations cards remain 96px and segment changes do not alter geometry above the workspace.
  > - Existing owner-only period loading and generic non-owner `No period` behavior remain unchanged; no shared-account private-period disclosure was introduced.
  > - No backend, schema, API, submit-handler, destructive-action, or unrelated workflow changes are present.
  > - Design notes accurately record the introduced production primitives and invariants.
  >
  > Fresh runtime evidence supplied for the explicit scratch database confirms the final 390×844 and 1280×900 geometry, balances, precision, overflow, mobile/desktop visibility, and Plan money behavior. The reviewer could not independently attach to the in-app browser because no browser binding was available in this reviewer session; this limitation does not contradict the supplied exact-runtime evidence.
  >
  > Reviewer reran:
  >
  > - `.venv/bin/python -m pytest -q tests/test_frontend_v2.py tests/test_phase15_primitives.py` — `14 passed`
  > - `node --check app/static/app.js` — passed
  > - `git diff --check` — passed
  > - untracked-file whitespace check via `git diff --no-index --check /dev/null tests/test_phase15_primitives.py` — passed
  >
  > No files or git state were modified.

### Test-contract review

- Reviewer: `/root/t024a_tests_rereview4`, Codex GPT-5 same-vendor fallback;
  cross-vendor reviewer was unavailable.
- Reviewed scope: complete `tests/test_phase15_primitives.py`, bounded
  `tests/test_frontend_v2.py` diff, and read-only correlation with the current
  production manifest.
- Verbatim final result:

  > Read-only review of FinApp Phase 15 T-024A, final test block — **No findings (P0–P3).**
  >
  > Reviewed the complete current `tests/test_phase15_primitives.py` and bounded `tests/test_frontend_v2.py` change. The contract covers mobile scoping, exact primitives, DOM semantics, precision-safe formatting, account-change balance refresh, and desktop metric/Plan cascade preservation. All prior test-review findings are closed.
  >
  > Verification:
  >
  > - Targeted suite: **14 passed in 0.13s**
  > - JavaScript syntax: passed
  > - Tracked diff check: passed
  > - Untracked test whitespace check: passed; exit 1 was the expected no-index “files differ” result
  > - No files edited or Git state mutated
  >
  > Reviewer: `/root/t024a_tests_rereview4`, Codex GPT-5 same-vendor fallback.

### Scratch browser verification

- Skill: `$verify`; server used only
  `/private/tmp/finapp-verify.T024A.hldk2l/finapp.db`, migrated through
  `0004_transfer_quotes`; `finapp.db` was never opened or replaced.
- 390×844 Accounts: 72px single-surface strip, two 64px whole-button rows,
  20/600 metric value, separately muted 11px suffix, exact `0.12345678 BTC`,
  long-name ellipsis, and zero horizontal overflow.
- 390×844 Operations: active and absent cards both 96px; selector stays 44px
  at y=201; account switching updates `1,234.50 USD` to `0.12345678 BTC`;
  absent Start target is 44px around a 36px visual control; zero overflow.
- 390×844 Plan: 64px single-surface strip; populated long rule retains inline,
  non-wrapping precision-safe money and zero horizontal overflow.
- 1280×900: Operations header/legacy toolbar and forms remain visible, compact
  balance remains hidden, selector remains the legacy 58px surface; Accounts
  metrics remain 152px and rows ≥170px; Plan metadata remains its legacy block
  line with nested money inline; zero horizontal overflow.

### Final documentation review

- Reviewer: `/root/t024a_final_docs_review`, Codex GPT-5 same-vendor fallback;
  cross-vendor reviewer was unavailable.
- Reviewed scope: final task/backlog/progress/design lifecycle evidence and its
  correlation with the complete T-024A manifest.
- Verbatim result:

  > Final limited read-only documentation/lifecycle review for T-024A: **No findings (P0–P3).**
  >
  > Verified:
  >
  > - All initial and repeated P1/P2 findings are recorded verbatim with resolutions and clean closures.
  > - The corrected fifth-review quote exactly matches the reviewer’s original verdict.
  > - Task, backlog, and progress statuses consistently remain `review`, awaiting authorized local acceptance.
  > - Branch `task/T-024A-mobile-primitives`, base `818f864`, implementer, acceptance criteria, manifest, session log, and design notes are consistent.
  > - Scratch evidence explicitly uses `/private/tmp/finapp-verify.T024A.hldk2l/finapp.db`; `finapp.db` was never opened or replaced.
  > - No acceptance, push, deploy, or phase-commit overclaim exists.
  > - Targeted tests: **14 passed in 0.11s**.
  > - JavaScript syntax and tracked diff checks passed.
  > - Untracked test whitespace check passed; exit 1 is the expected no-index “files differ” status.
  >
  > Same-vendor fallback; no files or Git state modified.

## Session log

- 2026-08-12 Codex GPT-5: task split from the former L-sized T-024; not claimed.
- 2026-08-12 Codex GPT-5: independent batch readiness verdict `ready`; remains
  `backlog` until T-023 is accepted.
- 2026-08-12 repository owner authorisation executed by Codex GPT-5: promoted
  readiness-ready T-024A from `backlog` to `todo` after local acceptance of
  dependency T-023; implementation is not yet claimed.
- 2026-08-12 Codex GPT-5: atomically claimed
  `task/T-024A-mobile-primitives` from accepted local integration `818f864`;
  lifecycle metadata and shared state now identify the active implementer.
  Implementation remains bounded to T-024A; no open questions.
- 2026-08-12 Codex GPT-5: implemented the bounded mobile primitive contract,
  exact string money presentation, representative Accounts/Operations/Plan
  bindings, and desktop-preserving cascade rules. Targeted gate is 14 passed;
  JavaScript and diff checks pass. `$verify` scratch mobile/desktop smoke passed.
  Independent implementation re-review closed all P0–P3 findings; task is now
  `review`, awaiting authorised local acceptance. No open questions.
- 2026-08-12 repository owner authorisation executed by Codex GPT-5: locally
  accepted fully verified task commit `c08901f` by fast-forward into
  `finapp-v2-develop`; task is `done`. No push, deploy, archive, or Phase 15
  commit was created.
