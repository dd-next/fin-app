# FinApp — current state

What is true right now. This file is **state, not a log**: entries are replaced
as reality changes, and closed work moves to [`history/`](history/). If it
grows past roughly 150 lines, archive the oldest closed entry.

Read at the start of a session: [`../AGENTS.md`](../AGENTS.md), this file, then
the one task file you are working on. Nothing else by default.

- What to work on next → [`BACKLOG.md`](BACKLOG.md)
- Why something is the way it is → [`DECISIONS.md`](DECISIONS.md)
- Evidence for closed phases → [`history/PROGRESS-phases-8-13.md`](history/PROGRESS-phases-8-13.md)

## Release status

| | |
|---|---|
| Branch | `task/T-013E-transfer-execution` |
| Release v2 | shipped — Phases 8–13 complete, all §12 acceptance criteria evidenced |
| Schema head | accepted integration `0004_transfer_quotes` |
| Last full suite | **329 passed** (2026-08-11, T-013E final implementation gate) |
| Active work | T-002–T-013Q accepted; T-013E independently approved and awaiting local owner acceptance |
| Blocker | None |

Last verified checks, Phase 13 acceptance (2026-07-19):

```text
pytest                                    111 passed in 11.19s
node --check app/static/app.js            ok
alembic check                             no new upgrade operations
docker build -t finapp-v2 .               image built, 190 MB
docker compose down -v && up -d           clean volume migrates, /health ok
browser acceptance 480×900 and 1280×900   pass
```

These are historical results, not a claim about the current worktree. Re-run
them before relying on them.

## Active — Phase 14: backend contract synchronization

Status: **T-002–T-013Q accepted; T-013E is independently approved on its exact
task branch and awaits local owner acceptance.**

- T-002 replaced editable period funding storage with exact opening/closing
  ledger snapshots and stable rollover-policy constraints.
- Populated migration preflights incompatible legacy data, preserves period and
  rebase identities, and derives snapshot balances without `float`.
- T-002 gate: full pytest `116 passed`; JS syntax, fresh scratch migration,
  `alembic check`, and `git diff --check` passed. Detailed review evidence:
  [`tasks/T-002-period-model-migration.md`](tasks/T-002-period-model-migration.md).
- T-003 added one-cutoff ledger reconciliation for current periods, strict
  ended boundaries, and immutable closed-history projections. Full pytest
  `118 passed`; detailed evidence:
  [`tasks/T-003-ledger-derived-balance.md`](tasks/T-003-ledger-derived-balance.md).
- T-004 enforces write-neutral natural expiry, exact atomic manual close,
  immutable post-close history, and serialized exact-boundary successors. Full
  pytest `126 passed`; detailed evidence:
  [`tasks/T-004-period-lifecycle.md`](tasks/T-004-period-lifecycle.md).
- T-005 adds pure exact `carry_next_day` allowance math and a common immutable
  exact/presentation result contract while preserving legacy callers. Full
  pytest `142 passed`; detailed evidence:
  [`tasks/T-005-carry-next-day-policy.md`](tasks/T-005-carry-next-day-policy.md).
- T-006 adds exact `redistribute_remaining_days` math and the common pure
  policy dispatcher with redistribution as default. Full pytest `153 passed`;
  detailed evidence:
  [`tasks/T-006-redistribute-policy.md`](tasks/T-006-redistribute-policy.md).
- T-007 adds atomic Start-date replay with exact predecessor/snapshot
  reconstruction, chronological guards, resulting-ended behavior, and
  serialized stale-request protection. Full pytest `160 passed`; detailed
  evidence: [`tasks/T-007-period-start-replay.md`](tasks/T-007-period-start-replay.md).
- T-008 exposes exact current/ended/closed API shapes, policy create/PATCH,
  one-cutoff allowance reads, and canonical lifecycle-aware Transactions
  membership. Full pytest `173 passed`; detailed evidence:
  [`tasks/T-008-period-api-lifecycle-surface.md`](tasks/T-008-period-api-lifecycle-surface.md).
- T-009 removes the transitional period funding/remaining/planned and period
  confirmation contracts from schemas, routes, OpenAPI, and the existing
  desktop consumer. Exact forbidden-input mutation tests and all lifecycle
  shapes are independently approved; full pytest `224 passed`, Node syntax
  and diff-check passed. Detailed evidence:
  [`tasks/T-009-remove-legacy-period-contracts.md`](tasks/T-009-remove-legacy-period-contracts.md).
- T-010 makes owner-private period state non-authorizing for shared users while
  preserving owner ended-period confirmation, generic shared correction
  confirmation, every role/leg permission boundary, and closed snapshots.
  Focused privacy matrices, scratch FastAPI+SPA E2E, Node/diff checks, and full
  pytest `229 passed`; implementation review approved with no open P0–P3.
  Detailed evidence:
  [`tasks/T-010-owner-private-period-permissions.md`](tasks/T-010-owner-private-period-permissions.md).
- T-012 implements exact Decimal-string `Asset → Main` manual rates,
  canonical/legacy direction-tagged storage, and guarded migration/downgrade.
  Fresh implementation re-review approved the complete committed range with no
  open P0–P3; scratch FastAPI+SPA E2E, full pytest `268`, Node syntax, and diff
  checks passed, and reviewed commit `437b5fa` was accepted locally by
  fast-forward. Detailed evidence:
  [`tasks/T-012-mobile-valuation-rate-direction.md`](tasks/T-012-mobile-valuation-rate-direction.md).
- The L-sized transfer row is split into bounded quote and execution tasks.
  T-013Q now persists exact owner-private same/cross-asset quotes, derives
  cross-asset amounts only through canonical manual Asset-to-Main rates, and
  records immutable dependencies for T-013E. Fresh cumulative review approved
  the full manifest with no open P0–P3; full pytest `322`, Node syntax, and
  diff checks passed. Reviewed commit `9f02bf1` was accepted locally by
  fast-forward. T-013E atomically executes the persisted amounts through the
  existing transfer/exchange, period, captured-rate, and Undo paths; exact
  concurrency, stale/expiry, rollback, privacy, and OpenAPI coverage passed.
  Fresh implementation re-review approved with no open P0–P3; full pytest
  `329`, Node syntax, and diff checks passed. Local owner acceptance remains.
  Detailed evidence: [`tasks/T-013Q-transfer-quote.md`](tasks/T-013Q-transfer-quote.md)
  and [`tasks/T-013E-transfer-execution.md`](tasks/T-013E-transfer-execution.md).

Requirements live in
[`specs/ACCOUNT_PERIODS-v2.1.md`](specs/ACCOUNT_PERIODS-v2.1.md) and
[`design/MOBILE-BACKEND-GAP-AUDIT.md`](design/MOBILE-BACKEND-GAP-AUDIT.md).
They are proposed changes: `specs/FinnApp-v2.md` remains the shipped release
authority until T-022 merges the accepted Phase 14 result into it.

The period work makes periods optional, replaces editable Funding/Remaining
with the real ledger balance, removes Planned from period logic, permits a
successor after close/expiry, and defines exact Decimal allowance formulas.
The mobile audit adds the backend contracts the frozen redesign also needs:
manual rate direction, transfer quoting, planned feed projection, transaction
type conversion, category/account lifecycle, and the Plan mobile adapter.
Mobile UI implementation is a separate Phase 15.

Review evidence for the specification itself (2026-08-08):

- `period_v21_spec_review` — five P1 and two P2 gaps in reconciliation,
  redistribution, natural expiry, membership, formulas, API, and history; all
  resolved.
- `period_v21_spec_rereview` — one P1 ended-window cutoff and one P2 example
  error; both fixed.
- `period_v21_spec_final_review` — **APPROVED, no P0–P3 findings** for the
  period-only proposal. The later mobile comparison required a coherent
  `685882` fixture and explicit start-date reconciliation; T-001 added both.
  Available today is owner-confirmed as informational and never blocks
  spending.
- `git diff --check` on the specification and this file — passed. No
  application code, migration, database, or frontend file changed.

Period decisions are recorded in
[ADR-0005](decisions/ADR-0005-periods-are-optional-and-ledger-derived.md); the
frozen-design/backend-first order is
[ADR-0007](decisions/ADR-0007-mobile-design-is-frozen-and-backend-first.md).

Task breakdown and order: [`BACKLOG.md`](BACKLOG.md). T-001 is accepted;
T-002 passed independent readiness review and is the first implementation task.

## Workflow and design handoff

`docs/` was reorganised around a task-based flow: `BACKLOG.md` for priority,
`tasks/` for the unit of work and its handoff, `DECISIONS.md` for durable
decisions, `design/` for design truth, `history/` for closed evidence.
`CLAUDE.md` is now a symlink to `AGENTS.md` so both agent vendors read one
file. The phase discipline from `BUILD_PLAN-v2.md` and the reviewer protocol
are unchanged — a task is the logical block those documents already require.

The 2026-08-09 consistency pass makes the task file the detailed evidence
authority and `PROGRESS.md` the phase summary, separates task commits from the
owner's phase-closing commit, defines atomic branch claims and sequential
handoffs, and makes read-only reviewer output verbatim evidence. The mobile
source hierarchy is recorded in `design/DESIGN-NOTES.md`; raw uploads and early
canvases are outside the intended Git set.

## Entry template

Copy this when a task or phase closes. Do not record completion without every
line being evidenced.

```md
### <T-NNN or Phase N> — <name> (YYYY-MM-DD)

- Status: [~] / [x] / [!]
- Completed: <2–4 concise implementation facts>
- Reviewer: <reviewer task name → findings → resolution>
- Tests: `<exact command>` — <exact pass/fail result>
- Checks: <migration/browser/Docker/diff evidence the work required>
- Decisions: <link the ADR, do not restate it here>
- Blocker (if any): <cause and attempted fixes>
```

## Historical note

Git history preserves the earlier root-level implementation ledger. Root
`PROGRESS.md` and `BUILD_PLAN-v2.md` are compatibility pointers and must not be
used to skip the current work.
