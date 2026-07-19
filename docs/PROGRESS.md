# FinApp v2 — release progress ledger

This is the active progress file for the new FinApp v2 release. Read
[`specs/FinnApp-v2.md`](specs/FinnApp-v2.md),
[`BUILD_PLAN-v2.md`](BUILD_PLAN-v2.md), and
[`REVIEW_PROTOCOL-v2.md`](REVIEW_PROTOCOL-v2.md) before resuming work.

Status legend: `[ ]` not started · `[~]` in progress · `[x]` completed · `[!]` blocked

## Current release plan

- [x] Phase 8 — Documentation and specification reset
- [ ] Phase 9 — Clean release schema
- [ ] Phase 10 — Financial correctness
- [ ] Phase 11 — Operations and account periods UI
- [ ] Phase 12 — Transactions and Plan
- [ ] Phase 13 — Docker and release verification

## Starting point — 2026-07-19

- The repository contains a prior Tracker/commitment prototype and its prior
  completion ledger. It is historical evidence only and does not meet this
  release's Operations/account-period/Plan requirements.
- This documentation package defines the new release boundary. No application
  code, migration, database, or runtime behavior is changed by this setup.
- Clarification locked for future implementation: ended-period funding/date
  edits and correction/soft void require explicit confirmation; a closed period
  remains read-only. Phase 10 must test this distinction.
- Before Phase 9, create and verify a timestamped backup of local `finapp.db`.
  Record its path, SHA-256 checksum, and open/restore verification here.

## Phase log

### Phase 8 — Documentation and specification reset (2026-07-19)

- Status: [x]
- Completed: consolidated all active documents under `docs/`, with active and
  historical specifications under `docs/specs/`; root v2 files are
  compatibility pointers and root `specs/` is removed. Defined Main currency,
  Operations/Undo, account periods, revised Transactions/Plan, clean reset,
  Docker delivery, manual acceptance, and the mandatory review protocol.
- Reviewer blocks: authority map → `phase8_authority_review` → APPROVED with no
  findings; specification → `phase8_spec_review` → two P1 findings (ended
  confirmation and exchange neutrality) fixed → `phase8_spec_rereview`
  APPROVED; execution/acceptance → `phase8_execution_review` → restore-proof,
  coverage, fresh-path, and Docker-command findings fixed →
  `phase8_execution_rereview` APPROVED with no unresolved P0–P2.
- Tests: `env -u DATABASE_URL PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m
  pytest -p no:cacheprovider -q` — **81 passed in 7.87s**;
  `node --check app/static/app.js` — passed; `PYTHONDONTWRITEBYTECODE=1
  .venv/bin/python -m compileall -q app tests` — passed; `.venv/bin/pip check`
  — no broken requirements; `git diff --check` — passed.
- Checks: active document targets exist, root `specs/` is absent, no stale
  pre-relocation active paths remain, and the documentation authority map is
  internally consistent.
- Decisions / assumptions: ended-period funding/date edits and financial
  correction/soft void require confirmation; closed periods are read-only.
  Only same-asset internal transfers are required to stay neutral to Total
  capital; cross-asset exchange valuation follows active rates.
- Blocker: none.

## Required phase-entry template

Copy this structure for every phase. Do not mark a phase complete without every
line being evidenced.

```md
### Phase N — <name> (YYYY-MM-DD)

- Status: [~] / [x] / [!]
- Completed: <2–4 concise implementation facts>
- Reviewer blocks: <block → reviewer task name → findings → resolution>
- Tests: `<exact command>` — <exact pass/fail result>
- Checks: <migration/browser/Docker/link/diff evidence required by the phase>
- Decisions / assumptions: <only decisions not already specified>
- Blocker (if any): <cause and attempted fixes>
```

## Historical note

Git history preserves the earlier root-level implementation ledger. The current
root-level `PROGRESS.md` is only a compatibility pointer and must not be used to
skip the phases above.
