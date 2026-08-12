---
id: T-030A
title: Pass the 390x844 mobile acceptance matrix
status: backlog
size: M
spec: design/Finnapp mobile specification/spec/01-foundations.md through spec/08-acceptance.md
blocked-by: [T-029]
branch: task/T-030A-mobile-acceptance
base-commit:
implementer:
readiness-reviewed-by:
readiness-reviewed-commit:
readiness-verdict:
---

## Goal

Close and document the complete mobile checklist at 390×844 on a fresh scratch
database.

## Acceptance

- [ ] Every item in `spec/08-acceptance.md` has pass/fail, expected/observed
      value, verification method, and screenshot/evidence name in this task.
- [ ] Empty, populated and long-list Accounts/Transactions/Plan states pass.
- [ ] All Operations modes, active/absent period, invalid/above-Available,
      account switch, real software keyboard Transfer, and Saved pass.
- [ ] Every concrete sheet, nested picker return, swipe state and branded
      destructive/success confirmation passes.
- [ ] Measurements prove 700px content, 96px cards, target/type minima,
      non-wrapping tabular money/separate currency, and only permitted scrolls.
- [ ] Copy matches `spec/06`; `DESIGN-NOTES.md` and ADR-0010/0011 corrections
      override older exported fixtures.
- [ ] Contrast and reduced motion pass; console and network contain no
      unexplained errors.
- [ ] Every recorded preview P2/P3 is enumerated; all P0–P2 are resolved before
      this task is accepted.
- [ ] Fixes are mobile-bounded and do not change backend or invent desktop UI.

## Touches

Frontend files only for bounded mobile corrections,
`tests/test_phase15_mobile_acceptance.py`, `tests/test_frontend_v2.py`, this task
and relevant progress evidence.

## Out of scope

Backend/schema/API changes, desktop redesign, deferred product capabilities,
phase acceptance or task archival.

## Verification

```bash
.venv/bin/python -m pytest -q tests/test_frontend_v2.py tests/test_phase15_interactions.py tests/test_phase15_mobile_acceptance.py
node --check app/static/app.js
git diff --check
```

Use `verify` with one fresh authenticated 390×844 scratch matrix; a single
happy-path screenshot is not sufficient evidence.

## Review

Append the bounded independent implementation review following the protocol.

## Session log

- 2026-08-12 Codex GPT-5: task split from former L-sized T-030; not claimed.
