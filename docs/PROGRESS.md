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
| Last full suite | **426 passed** (2026-08-15, on `finapp-v2-develop` after the T-030A merge) |
| Active work | none claimed — T-030A accepted, T-030B is the next task |
| Next | T-030B desktop regression and the full Phase 15 runtime gate |
| Blocker | Owner must rule on the replaced design specification (see T-030A) |

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
P0–P3 finding remains. T-029's shared picker/confirmation navigation layer is
now locally accepted: reviewed implementation `0ac4693` was fast-forwarded into
`finapp-v2-develop` after its sole P2 desktop-logout finding was closed. Its
exact 11-test target, diff and forbidden-native-API checks were re-run at
acceptance and pass; the syntax gate stands on the implementation session's
bundled-Node run because no Node runtime exists in the acceptance environment.
The preview is usable under ADR-0011. The repository owner narrowed T-030A to
an iPhone 15 fast-track for Accounts, Transactions, and Operations after
reporting Safari regressions; Plan, Analytics, and desktop verification are
explicitly deferred. The reviewed implementation now fixes the reported core
tab-bar, mixed Planned feed, sheet geometry and focus-zoom regressions. Its
focused 72-test, JavaScript and diff gates pass, and disposable 393×852 plus
390×844 browser evidence passes with a clean console.

On 2026-08-14 the owner returned sixteen further iPhone Safari findings and
replaced the mobile design specification in the working tree, reopening T-030A
to `in-progress`. All sixteen are fixed: overlays now cover the tab bar with no
per-surface exception, sheet secondaries lost the inherited accent fill, the
swipe lane travels its real action width, Undo moved into the period card as
the specified 26×26 `↺`, the segmented pill and Transfer layout match the
spec, every editable control is at least 16px so Safari cannot focus-zoom, and
the avatar carries its 10px accent dot. Full pytest is **425 passed**, the
72-test target, `node --check` and `git diff --check` pass, and the 393×852
matrix plus 390×844 smoke verify each finding from the live DOM. The replaced
specification also reverts settled Phase 14 decisions that no finding depends
on — over-limit submit blocking, the rollover checkbox, the allowance formula,
Plan `Skip`, and the disabled `Coming soon` options — so those areas were left
at their accepted behaviour and need an owner ruling.

Two follow-up corrections landed on the same day: saving an operation is now
silent, with the form clearing and the cards recalculating in place, and
Transfer regained the 10px gap that made every mode share one layout. A third
fixed delivery rather than the UI — `index.html` was served without
`Cache-Control`, so iOS Safari kept a heuristically cached copy holding the old
asset version tokens and no fix could reach the device at all; `app/main.py`
now serves the entry document with `no-cache`.

The repository owner accepted T-030A on 2026-08-15 and it is `done`;
`finapp-v2-develop` fast-forwarded to `8bfa353` and re-ran clean at **426
passed**. The independent round-2 review and the actual iPhone 15 Safari matrix
were **waived, not satisfied**, and the `app/main.py` header is an accepted
exception to that task's `Touches` — see the task file. Phase 15 remains
incomplete and unaccepted: T-030B desktop regression and T-031 closure are
still open.

`finapp-v2-develop` has been pushed to `origin` on owner instruction, so the
remote integration branch now matches local accepted state. `finapp-v2` was not
deployed and no task branch was pushed.

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
- Local accepted `finapp-v2-develop` is authoritative. As of T-029 acceptance
  the owner has pushed it to `origin`; deployment to `finapp-v2` is still a
  separate, later owner decision.

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
