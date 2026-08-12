# FinApp — current state

What is true right now. This file is **state, not a log**: closed work moves to
[`history/`](history/) and detailed task evidence moves to
[`tasks/archive/`](tasks/archive/).

Read at the start of a session: [`../AGENTS.md`](../AGENTS.md), this file, then
the one task file you are working on. Nothing else by default.

- What to work on next → [`BACKLOG.md`](BACKLOG.md)
- Active release authority → [`specs/FinnApp-v2.md`](specs/FinnApp-v2.md)
- Mobile source hierarchy → [`design/DESIGN-NOTES.md`](design/DESIGN-NOTES.md)
- Why something is the way it is → [`DECISIONS.md`](DECISIONS.md)
- Closed evidence → [`history/`](history/)

## Release status

| | |
|---|---|
| Branch | `finapp-v2-develop` |
| Release v2 | shipped — Phases 8–14 complete |
| Schema head | accepted integration `0004_transfer_quotes` |
| Last full suite | **341 passed** (2026-08-12, Phase 14 close gate) |
| Active work | T-024B is claimed on `task/T-024B-mobile-overlays`; status is `in-progress` |
| Next | Implement and independently review the bounded mobile overlay controller |
| Blocker | None |

## Phase 15 handoff — mobile redesign

Phase 14 is closed. Phase 15 has been decomposed into bounded T-023–T-031 task
files, including the required T-024/T-025/T-027/T-030 splits. ADR-0011 defines a
usable local preview after T-029 without calling the phase accepted. Batch
readiness review closed all P0–P2 findings. T-023 is locally accepted and
`done`; T-024A is locally accepted and `done`; T-024B is claimed and
`in-progress` on its exact task branch.

Phase 15 authority and constraints:

- [`specs/FinnApp-v2.md`](specs/FinnApp-v2.md) contains the accepted backend
  contract and ADR-0010 migration policy.
- [`design/Finnapp mobile specification/AGENTS.md`](design/Finnapp%20mobile%20specification/AGENTS.md)
  gives the mobile reading order; `Finapp Screen.dc.html` is the final visual
  source, and `design-tokens.json`/`tokens.css` are the token sources.
- The reference viewport is 390×844. Desktop remains functional where no
  desktop redesign exists.
- Do not implement T-015 transaction conversion, T-016 category merge/delete,
  or T-017 account restoration. Owner and automatic rates stay disabled
  `Coming soon`; Scan and Analytics remain placeholders.
- Do not promise account restoration. Do not use native `select`, `alert`,
  `confirm`, or `prompt` in the mobile UI.
- Do not change the accepted backend contracts to compensate for frontend
  composition. Period values stay ledger-derived; Plan projections stay
  non-ledger; money/rates stay exact Decimal.
- [`ADR-0011`](decisions/ADR-0011-phase15-usable-preview-fast-track.md) permits
  targeted per-task gates and a local preview checkpoint; final P0–P2 closure,
  full tests, mobile acceptance, and desktop regression remain mandatory.
- Origin is intentionally not the task base. Local accepted
  `finapp-v2-develop` is authoritative until the owner later pushes/deploys.

## Last verified gates — Phase 14 (2026-08-12)

```text
retained-contract smoke                    7 passed in 1.06s
full pytest                                341 passed in 32.45s
node --check app/static/app.js             passed
git diff --check                           passed
alembic heads                              0004_transfer_quotes (single head)
fresh alembic upgrade head                 0001 -> 0002 -> 0003 -> 0004
fresh alembic check                        no new upgrade operations
scratch FastAPI /health                    200 {"status":"ok"}
scratch SPA /                              200 text/html
```

The database is disposable pre-production data under
[`ADR-0010`](decisions/ADR-0010-preproduction-fast-track.md). Populated upgrade,
downgrade, and current-test-data preservation were intentionally not Phase 14
gates. This does not relax runtime Decimal, ledger, permission, privacy,
atomicity, or fresh-schema correctness.

Detailed Phase 14 implementation, review, and gate evidence:
[`history/PROGRESS-phase-14.md`](history/PROGRESS-phase-14.md).

## Historical note

Phases 8–13 are recorded in
[`history/PROGRESS-phases-8-13.md`](history/PROGRESS-phases-8-13.md). Git history
preserves the earlier root-level implementation ledger. Root `PROGRESS.md` and
`BUILD_PLAN-v2.md` are compatibility pointers and must not override the active
files under `docs/`.
