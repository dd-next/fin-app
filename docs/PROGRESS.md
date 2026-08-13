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
| Active work | T-029 navigation/accessibility on `task/T-029-navigation-accessibility` |
| Next | Implement the readiness-reviewed T-029 acceptance criteria |
| Blocker | None |

## Phase 15 handoff — mobile redesign

Phase 14 is closed. Phase 15 has been decomposed into bounded T-023–T-031 task
files, including the required T-024/T-025/T-027/T-030 splits. ADR-0011 defines a
usable local preview after T-029 without calling the phase accepted. Batch
readiness review closed all P0–P2 findings. T-023, T-024A and T-024B are
locally accepted and `done`. T-025A mobile Accounts and account lifecycle are
also locally accepted after targeted tests, independent bounded review,
390×844 scratch-browser smoke and preserved desktop smoke passed with all
P0–P2 findings closed. T-025B Profile/categories/rates/sharing/logout is also
locally accepted after targeted 67-test, syntax/diff, isolated 390×844 browser
and preserved 1280×900 checks passed, with all reviewer P2 sharing-race
findings closed. T-026 was implemented from accepted integration `f3f747b`;
its reviewed implementation commit `de7cf41` is now locally accepted on
`finapp-v2-develop`. Its 33-test targeted gate, JavaScript/diff checks,
isolated 390×844 browser smoke and retained 1280×900 check passed, with all
independent-review P0–P3 findings closed after limited re-review. T-027A was
implemented from accepted integration `7821bab`; reviewed implementation
commit `bf7c3a8` is now locally accepted on `finapp-v2-develop`. Its 77-test
targeted gate, syntax/diff checks, isolated 390×844 browser matrix and preserved
1280×900 checks pass, and all implementation-review P0–P3 findings are closed.
T-027B's reviewed implementation `283215f` and T-028's reviewed implementation
`173ea51` are now locally accepted on `finapp-v2-develop`. T-028's exact
35-test target, syntax/diff, isolated 390×844 browser matrix and retained
1280×900 Plan regression passed; both Link-safety P2 findings are closed and no
P0–P3 finding remains. T-029 is next, remains unclaimed, and Phase 15 remains
incomplete.

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
