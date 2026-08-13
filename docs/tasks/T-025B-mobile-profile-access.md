---
id: T-025B
title: Implement mobile Profile, settings, access, and logout
status: in-progress
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

- [ ] Avatar opens Profile with Manage categories, Exchange rates, Workspace
      information, and Log out; identity/password editing is absent.
- [ ] Supported category create/rename/archive remains usable. Merge/Delete
      controls and reassignment promises are absent under T-016.
- [ ] Set a rate uses Asset→Main pair, `Manual value`, disabled
      `Auto · Coming soon`, exact Decimal-string input, and accepted workspace
      rate endpoint; save/delete refresh Accounts totals and warning state.
- [ ] Share lists only authorized people/roles, supports invitation links and
      existing Viewer/Contributor/Editor changes, and displays disabled
      `Owner · Coming soon`; inaccessible account/people data is not inferred.
- [ ] Logout uses branded confirmation, exact device/workspace copy, and the
      existing server logout endpoint; cancel does not revoke the session.
- [ ] Permission-driven controls are absent or disabled truthfully; direct API
      denial remains server authoritative.
- [ ] Desktop Profile, category management, rates, sharing and logout remain
      functional through the same non-native primitives.
- [ ] No backend/schema, category merge/delete, owner transfer, automatic rate,
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

Append the bounded independent implementation review following the protocol.

## Session log

- 2026-08-12 Codex GPT-5: split from overloaded T-025 after readiness review;
  not claimed.
- 2026-08-12 Codex GPT-5: limited independent re-review verdict `ready`; remains
  blocked by T-025A.
