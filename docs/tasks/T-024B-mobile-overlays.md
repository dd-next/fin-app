---
id: T-024B
title: Establish mobile sheets, pickers, and confirmations
status: in-progress
size: M
spec: design/Finnapp mobile specification/spec/02-components.md; spec/04-sheets.md; spec/05-interactions.md
blocked-by: [T-024A]
branch: task/T-024B-mobile-overlays
base-commit: bf50e75
implementer: Codex GPT-5
readiness-reviewed-by: /root/phase15_readiness_review, Codex GPT-5 same-vendor fallback
readiness-reviewed-commit: deb8a5a
readiness-verdict: ready
---

## Goal

Provide one accessible overlay controller for stacked bottom sheets, reusable
Choose sheets, and branded confirmations without changing business actions or
authorization boundaries.

## Acceptance

- [ ] One overlay root/controller owns sheet, confirmation, opener, and return
      stack state; feature tasks do not create competing mechanisms.
- [ ] Bottom-sheet grabber/header/body/footer/safe band, top radius/border,
      `max-height:88%`, scrim, and ≤180ms motion follow specs 02/04.
- [ ] Scrim, close, Escape, and Cancel dismiss without calling a primary or
      destructive callback; confirmed callbacks run at most once.
- [ ] Opening records focus, background content is non-interactive, focus stays
      inside the active overlay, and closing restores focus to its opener.
- [ ] Tab switching closes the full stack. A Choose sheet returns selection to
      its immediate sheet/form, marks the current option, and cannot select a
      disabled option.
- [ ] Confirmation supports cancel+accent, cancel+destructive, and one-button
      Saved variants with accessible modal labels.
- [ ] Reduced motion removes transforms without hiding content.
- [ ] Callers remain responsible for passing only authorized accounts,
      periods, Plan items and transactions; no permissions are broadened.
- [ ] A real production integration point exercises the infrastructure; no
      inaccessible component gallery is added.
- [ ] Existing desktop dialogs remain functional until feature owners migrate
      them; concrete feature catalogues and final removal of native controls
      belong to T-025A–T-029.
- [ ] No API, ledger mutation, financial formatter, backend, schema, or
      migration change is introduced.
- [ ] `DESIGN-NOTES.md` records the overlay contract.

## Touches

Overlay root/templates in `app/static/index.html`, overlay CSS in
`app/static/style.css`, bounded controller/helpers in `app/static/app.js`,
`tests/test_frontend_v2.py`, `tests/test_phase15_overlays.py`, design notes, and
task lifecycle evidence.

## Out of scope

Concrete Accounts/Transactions/Operations/Plan/Profile workflows; changing API
payloads; migrating every legacy native control; T-015/T-016/T-017; custom
software keyboard.

## Verification

```bash
.venv/bin/python -m pytest -q tests/test_frontend_v2.py tests/test_phase15_overlays.py
node --check app/static/app.js
git diff --check
```

Use `verify` at 390×844 for scrim/X/Escape/Cancel/action, nested Choose return,
disabled option, tab closure, focus containment/restoration, reduced motion,
overflow and console; smoke existing desktop dialogs at 1280×900.

## Review

Append the bounded independent implementation review following the repository
protocol.

### Atomic claim review

- Reviewer: `/root/t024a_final_docs_review`, Codex GPT-5 same-vendor fallback;
  cross-vendor reviewer was unavailable.
- Reviewed scope: branch/base invariants and the complete lifecycle diff in
  this task, `docs/BACKLOG.md`, and `docs/PROGRESS.md`.
- Verbatim result:

  > Read-only atomic claim review for T-024B: **No findings (P0–P3).**
  >
  > Verified:
  >
  > - Exact branch `task/T-024B-mobile-overlays` was newly created from accepted local integration commit `bf50e75`; reflog confirms the creation point.
  > - At base `bf50e75`, T-024B was readiness-ready `todo` and dependency T-024A was accepted `done`.
  > - Current uncommitted manifest contains only the three expected claim documentation files:
  >   - `docs/tasks/T-024B-mobile-overlays.md`
  >   - `docs/BACKLOG.md`
  >   - `docs/PROGRESS.md`
  > - Task and backlog consistently record `in-progress`; progress identifies the exact active branch and bounded next work.
  > - `base-commit: bf50e75`, `implementer: Codex GPT-5`, branch, dependency, readiness evidence, and append-only session log are correct.
  > - No implementation, acceptance, push, deploy, archive, or phase-commit overclaim exists.
  > - `git diff --check` passes.
  >
  > This lifecycle diff is suitable for the first T-024B task commit unchanged. Reviewer: `/root/t024a_final_docs_review`, Codex GPT-5 same-vendor fallback; cross-vendor reviewer unavailable. Read-only; no files or Git state modified.

## Session log

- 2026-08-12 Codex GPT-5: task split from the former L-sized T-024; not claimed.
- 2026-08-12 Codex GPT-5: independent batch readiness verdict `ready`; remains
  blocked by T-024A.
- 2026-08-12 repository owner authorisation executed by Codex GPT-5: promoted
  readiness-ready T-024B from `backlog` to `todo` after local acceptance of
  dependency T-024A; implementation is not yet claimed.
- 2026-08-12 Codex GPT-5: atomically claimed
  `task/T-024B-mobile-overlays` from accepted local integration `bf50e75`;
  lifecycle metadata and shared state now identify the active implementer.
  Implementation remains bounded to T-024B; no open questions.
