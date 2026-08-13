---
id: T-025B
title: Implement mobile Profile, settings, access, and logout
status: review
size: M
spec: design/Finnapp mobile specification/spec/04-sheets.md Profile/Categories/Rate/Share; spec/05-interactions.md; spec/06-content.md
blocked-by: [T-025A]
branch: task/T-025B-mobile-profile-access
base-commit: 7443d2772ce7bcc13b369a092aa7943eb72f0ab0
implementer: /root, Codex GPT-5
readiness-reviewed-by: /root/phase15_readiness_review, Codex GPT-5 same-vendor fallback
readiness-reviewed-commit: deb8a5a
readiness-verdict: ready
---

## Goal

Make Profile, supported category settings, manual rates, sharing/invitations,
and logout usable through accepted APIs without broadening permissions.

## Acceptance

- [x] Avatar opens Profile with Manage categories, Exchange rates, Workspace
      information, and Log out; identity/password editing is absent.
- [x] Supported category create/rename/archive remains usable. Merge/Delete
      controls and reassignment promises are absent under T-016.
- [x] Set a rate uses Asset→Main pair, `Manual value`, disabled
      `Auto · Coming soon`, exact Decimal-string input, and accepted workspace
      rate endpoint; save/delete refresh Accounts totals and warning state.
- [x] Share lists only authorized people/roles, supports invitation links and
      existing Viewer/Contributor/Editor changes, and displays disabled
      `Owner · Coming soon`; inaccessible account/people data is not inferred.
- [x] Logout uses branded confirmation, exact device/workspace copy, and the
      existing server logout endpoint; cancel does not revoke the session.
- [x] Permission-driven controls are absent or disabled truthfully; direct API
      denial remains server authoritative.
- [x] Desktop Profile, category management, rates, sharing and logout remain
      functional through the same non-native primitives.
- [x] No backend/schema, category merge/delete, owner transfer, automatic rate,
      account restoration, or other feature-screen work is added.

## Touches

`app/static/index.html`, `app/static/app.js`, `app/static/style.css`,
`tests/test_mobile_profile_access_ui_v21.py`, `tests/test_frontend_v2.py`, design
notes, and task lifecycle evidence.

## Out of scope

Account list/lifecycle (T-025A), backend/schema, T-015/T-016/T-017, automatic
rates, ownership transfer, other screens.

## Verification

```bash
.venv/bin/python -m pytest -q tests/test_mobile_profile_access_ui_v21.py tests/test_frontend_v2.py tests/test_foundation_v2.py tests/test_sharing_v2.py tests/test_valuation_rate_direction_v21.py tests/test_valuation_v2.py tests/test_phase12_privacy_v2.py
node --check app/static/app.js
git diff --check
```

Use `verify` for Profile → categories/rate/share/logout, role and invitation
states, exact Decimal rate refresh, cancel/confirm logout at 390×844, plus
preserved 1280×900 settings/access behavior.

## Review

### Bounded implementation review

- Reviewer: `/root/t025b_profile_review`, Codex GPT-5 same-vendor fallback;
  cross-vendor review was unavailable. Read-only; no files or Git state were
  changed.
- Reviewed range: current uncommitted implementation against claim HEAD
  `d2265dc23c05b92e1457515191dbc74b867fe36c`; tracked
  `app/static/index.html`, `app/static/app.js`, `app/static/style.css`, plus
  direct inspection of untracked `tests/test_mobile_profile_access_ui_v21.py`.
- Verbatim findings and verdict:

  > Findings
  >
  > - P2 — [app/static/app.js](C:\Users\Ксюша\Documents\Codex\fin-app\app\static\app.js:2204): `loadMobileAccess()` uses mutable `state.sharingAccount` and applies the eventual rows/error without checking account identity. If Share for account A is closed while its initial request is in flight and Share for account B is opened, A’s late response can overwrite B’s PEOPLE list. Capture the requested account ID and discard stale completion unless it still matches. Add focused regression coverage.
  >
  > Resolved during review
  >
  > - The superseded inline Share action violated the Account details footer catalogue and clipped the 390px action row. The current manifest correctly uses an owner-only `secondaryLabel: "Share"` footer action at `app/static/app.js:1385-1392`, with focused source coverage and browser recheck.
  >
  > Verdict: changes required — one P2 remains open; no P0, P1, or P3 findings.
  >
  > Cross-vendor review was unavailable; this was a fresh independent same-vendor Codex fallback.

- Resolution: `loadMobileAccess(accountId)` now captures the account identity and
  discards both late success and failure completions before changing visible
  rows or errors. Sharing mutation handlers capture their account too. Focused
  coverage guards the identity checks.

### Limited re-reviews

- The first limited re-review found one residual P2, verbatim:

  > Findings
  >
  > - P2 — [app/static/app.js](C:\Users\Ксюша\Documents\Codex\fin-app\app\static\app.js:2182): The role-change failure handler still writes `state.sharingError` unconditionally. Because Choose does not await `onSelect`, a user can leave Share A and open Share B while PATCH A is pending; a late A failure then appears in B. Guard the catch with the captured `sharingAccount.id` and add focused coverage.
  >
  > The original stale access-list response path is otherwise correctly fixed: both success and failure in `loadMobileAccess()` validate account identity before committing.
  >
  > Verdict: changes required — one residual P2 remains; no P0, P1, or P3 findings.
  >
  > Cross-vendor review was unavailable; this was a fresh independent same-vendor Codex fallback.

- Resolution: the role-PATCH failure handler now also verifies the captured
  account remains active before publishing an error; the focused test covers
  this guard.
- Final limited re-review, verbatim:

  > No P0–P3 findings.
  >
  > Both prior P2 paths are closed:
  >
  > - `loadMobileAccess()` discards stale success and failure responses before changing rows or errors.
  > - Role PATCH uses the captured account and discards late failures after the active sharing account changes.
  > - Focused regression assertions cover both identity guards.
  >
  > Verdict: PASS — both P2 findings are closed.
  >
  > Cross-vendor review was unavailable; this was a fresh independent same-vendor Codex fallback.

### Final implementation and lifecycle review

- Reviewer: `/root/t025b_final_review`, fresh Codex GPT-5 same-vendor
  fallback; cross-vendor review was unavailable. Read-only; no files or Git
  state were changed.
- Reviewed the complete seven-file manifest against claim HEAD `d2265dc`,
  including direct inspection of the untracked test and all implementation,
  task/backlog/progress evidence.
- Verbatim finding and verdict:

  > Findings
  >
  > - P2 — [app/static/app.js](C:\Users\Ксюша\Documents\Codex\fin-app\app\static\app.js:2187): The stale-sharing guards validate only `sharingAccount.id`, not the active Share sheet instance. `state.sharingAccount` is never cleared when Share closes, so a late GET or role-PATCH failure for account A still passes after Share A is closed and either reopened for A or replaced by an unrelated sheet. `loadMobileAccess()` can then overwrite newer same-account rows and unconditionally re-render the unrelated/current overlay at line 2233; the PATCH catch can similarly publish a stale error and re-render at line 2189. Capture a per-open Share generation/entry token and require that exact context to remain active before committing rows/errors or rendering. Add focused regression coverage for close/reopen of the same account and close/open of an unrelated overlay.
  >
  > No P0, P1, or P3 findings.
  >
  > The Account-details Share footer contract, exact Decimal-string rate path, permission-driven controls, task scope, manifest, lifecycle statuses, append-only session log, and prior reviewer transcription otherwise check out. I independently reran bundled Node syntax checking and `git diff --check`; both passed. The supplied targeted result remains `67 passed in 24.08s`.
  >
  > Verdict: changes required—one P2 remains. The implementation is not yet suitable to commit until this residual stale-context race is fixed and re-reviewed.
  >
  > Cross-vendor review was unavailable; this was a fresh independent same-vendor Codex fallback.

- Resolution: each Share opening now owns a unique overlay context object;
  nested Choose/confirmation overlays inherit it, and GET/PATCH completions may
  publish only while that exact context is active. Reopening the same account
  therefore cannot accept work from the prior sheet instance, and unrelated
  overlays cannot be re-rendered by stale sharing work.
- Verbatim limited re-review:

  > No P0–P3 findings.
  >
  > The prior P2 is closed:
  >
  > - Each Share opening creates a unique context object, so reopening the same account cannot accept the previous instance’s completion.
  > - Nested Choose sheets and confirmations inherit that exact context.
  > - GET success/failure and role-PATCH failures commit or render only when the exact context remains active at the top of the overlay stack.
  > - Unrelated overlays have a null or different context.
  > - Focused regression assertions cover context creation, propagation, identity checks, and captured-context use.
  >
  > Bundled Node syntax checking and `git diff --check` passed independently.
  >
  > Verdict: PASS—the residual stale-context race is closed, and the implementation is suitable to commit.
  >
  > Cross-vendor review was unavailable; this was a fresh independent same-vendor Codex fallback.

### Verification evidence

- Targeted gate:
  `.venv\Scripts\python.exe -m pytest -q tests/test_mobile_profile_access_ui_v21.py tests/test_frontend_v2.py tests/test_foundation_v2.py tests/test_sharing_v2.py tests/test_valuation_rate_direction_v21.py tests/test_valuation_v2.py tests/test_phase12_privacy_v2.py`
  → `67 passed in 24.01s`. Bundled Node `--check app/static/app.js` and
  `git diff --check` passed.
- `verify` used only migrated scratch database
  `C:\Users\A90B~1\AppData\Local\Temp\finapp-t025b-f80acb546a104727b92f9b6d5799cdcf\finapp.db`;
  repository `finapp.db` was never used. Data was created through the visible UI.
- At 390×844: read-only Profile, category add/rename/kind/archive, exact
  `50000.123456789012345678` BTC→USD rate save/delete and totals/warning
  refresh, invitation acceptance by a second user, contributor permission
  restrictions, owner role change/removal, and logout cancel/confirm passed.
  The account-detail inline actions measured `357px` client/scroll width after
  Share moved to the specified secondary footer. Zero horizontal overflow,
  zero visible native selects, and an empty browser console were observed.
- At 1280×900, Profile menu, category dialog, exact-rate dialog, sharing and
  account details remained functional with zero horizontal overflow.
  Screenshots `t025b-mobile.png` and `t025b-desktop.png` are retained in the
  named scratch directory.

## Session log

- 2026-08-12 Codex GPT-5: split from overloaded T-025 after readiness review;
  not claimed.
- 2026-08-12 Codex GPT-5: limited independent re-review verdict `ready`; remains
  blocked by T-025A.
- 2026-08-13 repository owner authorisation executed by `/root`, Codex GPT-5:
  promoted readiness-ready T-025B to `todo`, atomically claimed
  `task/T-025B-mobile-profile-access` from accepted integration `7443d27`, and
  recorded `/root` as implementer.
- 2026-08-13 `/root`, Codex GPT-5: implemented the bounded mobile Profile,
  categories, exact manual rates, sharing/invitations and branded logout while
  preserving desktop. Browser-found overlay replacement and account-detail
  footer issues were fixed; all reviewer P2 sharing-race findings are closed. Targeted
  67-test, JavaScript, diff and scratch-browser gates pass. Task is `review`,
  awaiting owner-authorized local acceptance; no open questions.
