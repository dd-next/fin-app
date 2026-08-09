# FinApp — backlog

The single ordered list of upcoming work. Whatever sits at the top of **Next**
and is not blocked is what gets picked up. Nothing else decides priority.

Only the repository owner reorders this file. An agent may append a row to
**Icebox** when it discovers work outside the current task; it never reorders
rows, never promotes its own row into Next, and never starts an Icebox row.

- Status: `backlog` · `todo` · `in-progress` · `review` · `done`
- Size: `S` comfortably fits one session · `M` fills one session · `L` must be
  split before it is started

A row becomes workable only once it has a task file under
[`tasks/`](tasks/). Writing that file is the Specify step and is itself work —
see [`AGENTS.md`](../AGENTS.md) § Session protocol.

## Next — Phase 14: backend contract synchronization

Phase 14 completes every backend capability required by the frozen mobile
design before the UI redesign starts. Requirements come from
[`specs/ACCOUNT_PERIODS-v2.1.md`](specs/ACCOUNT_PERIODS-v2.1.md) and the
accepted [`design/MOBILE-BACKEND-GAP-AUDIT.md`](design/MOBILE-BACKEND-GAP-AUDIT.md).
The design assets do not change in this phase.

Order follows `BUILD_PLAN-v2.md`: contract → schema → domain → API → cross-domain
capabilities → acceptance → docs. Do not start Phase 15 while any Phase 14
backend gap remains open.

| ID | Task | Status | Size | Spec | Blocked by |
|----|------|--------|------|------|------------|
| [T-001](tasks/T-001-mobile-backend-contract-sync.md) | Synchronize mobile design and backend contracts | done | M | design audit | — |
| [T-002](tasks/T-002-period-model-migration.md) | Period model and migration | done | M | periods §3 | T-001 |
| [T-003](tasks/T-003-ledger-derived-balance.md) | Ledger-derived `current_balance` and reconciliation input | done | M | periods §6, §6.1 | T-002 |
| [T-004](tasks/T-004-period-lifecycle.md) | Lifecycle: manual close, natural expiry, successor rules | done | M | periods §4, §5 | T-002 |
| [T-005](tasks/T-005-carry-next-day-policy.md) | `carry_next_day` policy in pure `app/budget.py` | done | M | periods §7.1, §7.3 | T-003 |
| [T-006](tasks/T-006-redistribute-policy.md) | `redistribute_remaining_days` policy in pure `app/budget.py` | done | M | periods §7.2, §7.3 | T-003, T-005 |
| [T-007](tasks/T-007-period-start-replay.md) | Period create/edit Start date semantics and snapshot replay | done | M | periods §8 + audit | T-002, T-003, T-004 |
| [T-008](tasks/T-008-period-api-lifecycle-surface.md) | Period API and lifecycle surface | done | M | periods §9 | T-004, T-005, T-006, T-007 |
| T-009 | Remove `funding_amount` / `remaining` / `planned` contracts | backlog | S | periods §3, §10 | T-008 |
| T-010 | Owner-private period permissions for shared accounts | backlog | M | periods §11 | T-008 |
| T-012 | Manual valuation-rate mobile pair direction | backlog | M | audit: rates | T-001 |
| T-013 | One-amount same/cross-asset Transfer quote and execution | backlog | L | audit: transfer | T-012 |
| T-014 | Financial-date feed: Planned plus adjustment/exchange projections | backlog | L | audit: feed | T-001 |
| T-015 | Transaction type conversion and mobile type/detail boundaries | backlog | L | audit: edit transaction | T-014 |
| T-016 | Category merge/delete for transactions and Plan rules | backlog | M | audit: categories | T-001 |
| T-017 | Restore archived accounts | backlog | S | audit: accounts | T-001 |
| T-019 | Mobile Plan-rule create/edit/detail contract | backlog | M | audit: Plan | T-001, T-016 |
| T-021 | Phase 14 backend acceptance matrix | backlog | L | periods §12 + audit | T-009, T-010, T-012–T-017, T-019 |
| T-022 | Merge accepted backend contracts into `FinnApp-v2.md` | backlog | S | all Phase 14 | T-021 |

Every `L` row must be split into reviewed `S`/`M` task files before it is
claimed. The external-rate, ownership-transfer, and invite-only session
questions no longer block Phase 14: Auto and Owner are disabled placeholders,
and logout keeps the existing server-session model.

## Later — Phase 15: mobile redesign

Phase 15 uses the frozen mobile specification only after T-022 closes Phase
14. Desktop remains functional and is preserved where no desktop redesign
exists.

| ID | Task | Status | Size | Spec | Blocked by |
|----|------|--------|------|------|------------|
| T-023 | Import approved tokens and responsive mobile shell | backlog | M | design §01 | T-022 |
| T-024 | Mobile primitives, sheets, pickers, and confirmations | backlog | L | design §02, §04 | T-023 |
| T-025 | Accounts, Profile, manual rates, logout, and sharing placeholders | backlog | M | design §03.1, §04 | T-024 |
| T-026 | Transactions feed, filters, details, correction, and swipe flows | backlog | M | design §03.2, §05 | T-024 |
| T-027 | Operations/period flows and informational Available today | backlog | L | design §03.3, §05 | T-024, T-022 |
| T-028 | Plan three-action row, settings, and Analytics placeholder | backlog | M | design §03.4–§03.5 | T-019, T-024 |
| T-029 | Navigation graph, keyboard states, motion, and accessibility | backlog | M | design §05, §08 | T-025–T-028 |
| T-030 | 390×844 acceptance and desktop regression matrix | backlog | L | design §08 | T-029 |
| T-031 | Phase 15 documentation and release close | backlog | S | all Phase 15 | T-030 |

## Icebox

Not scheduled. Rows here are notes, not commitments.

| ID | Task | Note |
|----|------|------|
| T-032 | Implement Owner invitation and safe ownership/workspace transfer | Explicitly deferred until after the mobile redesign; Phase 15 shows disabled `Owner · Coming soon`. |
| T-033 | External automatic daily rates | Explicitly deferred; Phase 15 supports manual input and a disabled `Auto · Coming soon` option. |

## Done

Archived task files live in [`tasks/archive/`](tasks/archive/). Phases 8–13 are
recorded in [`history/PROGRESS-phases-8-13.md`](history/PROGRESS-phases-8-13.md).
