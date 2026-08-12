---
id: T-024A
title: Build reusable mobile visual primitives
status: in-progress
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

- [ ] Shared production primitives cover screen/list/group headers, list/ghost
      rows, Accounts/Plan metric strips, active/absent 96px Operations cards,
      segmented controls, chip lanes/chips, form/sheet/amount/error fields, and
      primary/secondary/inline/destructive buttons.
- [ ] Heights, radii, spacing, type, colors, two-surface limit, and hairlines
      match specs 01–02; metric strips are one surface, never nested cards.
- [ ] Both Operations-card states remain exactly 96px; switching segment does
      not move anything above it.
- [ ] Interactive wrappers are semantic and ≥44px; chips are 36px inside a
      44px lane.
- [ ] Existing asset-precision string formatting is preserved; money uses
      tabular non-wrapping numerals and a separate muted currency suffix. No new
      `Number`/`parseFloat` financial calculation is introduced.
- [ ] Long names truncate without wrapping or widening the viewport.
- [ ] Primitive styles are mobile-scoped; representative real Accounts,
      Operations, and Plan DOM exercises them without a hidden demo gallery.
- [ ] Existing API calls, submit handlers, permissions, and desktop behavior at
      1280×900 remain intact.
- [ ] `DESIGN-NOTES.md` records the primitive/tokens actually introduced.

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
