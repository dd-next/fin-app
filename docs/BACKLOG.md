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

## Done — Phase 14: backend contract synchronization

Phase 14 completed the backend capabilities retained on the fast-track path to
the frozen mobile design. Requirements come from
[`specs/ACCOUNT_PERIODS-v2.1.md`](specs/ACCOUNT_PERIODS-v2.1.md) and the
accepted [`design/MOBILE-BACKEND-GAP-AUDIT.md`](design/MOBILE-BACKEND-GAP-AUDIT.md).
The owner-approved exclusions are recorded in
[`ADR-0010`](decisions/ADR-0010-preproduction-fast-track.md). The design assets
do not change in this phase.

Order followed `BUILD_PLAN-v2.md`: contract → schema → domain → API →
cross-domain capabilities → acceptance → docs. Detailed evidence is archived
in [`history/PROGRESS-phase-14.md`](history/PROGRESS-phase-14.md).

| ID | Task | Status | Size | Spec | Blocked by |
|----|------|--------|------|------|------------|
| [T-001](tasks/archive/T-001-mobile-backend-contract-sync.md) | Synchronize mobile design and backend contracts | done | M | design audit | — |
| [T-002](tasks/archive/T-002-period-model-migration.md) | Period model and migration | done | M | periods §3 | T-001 |
| [T-003](tasks/archive/T-003-ledger-derived-balance.md) | Ledger-derived `current_balance` and reconciliation input | done | M | periods §6, §6.1 | T-002 |
| [T-004](tasks/archive/T-004-period-lifecycle.md) | Lifecycle: manual close, natural expiry, successor rules | done | M | periods §4, §5 | T-002 |
| [T-005](tasks/archive/T-005-carry-next-day-policy.md) | `carry_next_day` policy in pure `app/budget.py` | done | M | periods §7.1, §7.3 | T-003 |
| [T-006](tasks/archive/T-006-redistribute-policy.md) | `redistribute_remaining_days` policy in pure `app/budget.py` | done | M | periods §7.2, §7.3 | T-003, T-005 |
| [T-007](tasks/archive/T-007-period-start-replay.md) | Period create/edit Start date semantics and snapshot replay | done | M | periods §8 + audit | T-002, T-003, T-004 |
| [T-008](tasks/archive/T-008-period-api-lifecycle-surface.md) | Period API and lifecycle surface | done | M | periods §9 | T-004, T-005, T-006, T-007 |
| [T-009](tasks/archive/T-009-remove-legacy-period-contracts.md) | Remove `funding_amount` / `remaining` / `planned` contracts | done | S | periods §3, §10 | T-008 |
| [T-010](tasks/archive/T-010-owner-private-period-permissions.md) | Owner-private period permissions for shared accounts | done | M | periods §11 | T-008, T-009 |
| [T-012](tasks/archive/T-012-mobile-valuation-rate-direction.md) | Manual valuation-rate mobile pair direction | done | M | audit: rates | T-001 |
| [T-013Q](tasks/archive/T-013Q-transfer-quote.md) | Exact one-amount same/cross-asset Transfer quote | done | M | audit: transfer | T-012 |
| [T-013E](tasks/archive/T-013E-transfer-execution.md) | Atomic execution of a bound Transfer quote | done | M | audit: transfer | T-013Q |
| [T-014F](tasks/archive/T-014F-financial-date-transaction-feed.md) | Stable financial-date persisted transaction feed | done | M | audit: feed order/mapping | T-001 |
| [T-014P](tasks/archive/T-014P-planned-feed-projection.md) | Planned projections through Transaction details | done | M | audit: planned rows | T-014F |
| [T-019](tasks/archive/T-019-mobile-plan-contract.md) | Mobile Plan-rule create/edit/detail contract | done | M | audit: Plan | T-001 |
| [T-021](tasks/archive/T-021-phase14-acceptance.md) | Lean Phase 14 backend acceptance | done | M | periods §12 + audit | T-009, T-010, T-012, T-013Q, T-013E, T-014F, T-014P, T-019 |
| [T-022](tasks/archive/T-022-phase14-spec-merge.md) | Merge accepted backend contracts into `FinnApp-v2.md` | done | S | all Phase 14 | T-021 |

The external-rate, ownership-transfer, and invite-only session questions did
not block Phase 14: Auto and Owner are disabled placeholders, and logout keeps
the existing server-session model.

## Next — Phase 15: mobile redesign

Phase 15 uses the frozen mobile specification after accepted T-022. Desktop
remains functional and is preserved where no desktop redesign exists. Under
ADR-0010, Phase 15 omits transaction-type conversion, category merge/delete,
and account-restoration controls and does not promise restoration. ADR-0011
defines the usable-preview fast-track. T-023 is the only initial task; later
rows remain blocked until their accepted dependencies land.

| ID | Task | Status | Size | Spec | Blocked by |
|----|------|--------|------|------|------------|
| [T-023](tasks/T-023-mobile-shell.md) | Import approved tokens and responsive mobile shell | done | M | design §01 | T-022 |
| [T-024A](tasks/T-024A-mobile-primitives.md) | Build reusable mobile visual primitives | done | M | design §01–§02 | T-023 |
| [T-024B](tasks/T-024B-mobile-overlays.md) | Establish sheets, pickers, and confirmations | done | M | design §02, §04–§05 | T-024A |
| [T-025A](tasks/T-025A-mobile-accounts.md) | Accounts and account lifecycle | done | M | design §03.1, §04 | T-024B |
| [T-025B](tasks/T-025B-mobile-profile-access.md) | Profile, categories, rates, sharing, and logout | backlog | M | design §04–§06 | T-025A |
| [T-026](tasks/T-026-mobile-transactions.md) | Transactions feed, filters, details, correction, and swipe | backlog | M | design §03.2, §05 | T-024B |
| [T-027A](tasks/T-027A-mobile-operations.md) | Operations action surface and exact Save flows | backlog | M | design §03.3, §05 | T-024B |
| [T-027B](tasks/T-027B-mobile-periods.md) | Account-period cards and lifecycle | backlog | M | design §03.3, §04–§05 | T-027A |
| [T-028](tasks/T-028-mobile-plan-analytics.md) | Plan rule/occurrence flows and Analytics placeholder | backlog | M | spec §8, design §03.4–§03.5 | T-019, T-024B |
| [T-029](tasks/T-029-navigation-accessibility.md) | Integrate navigation, keyboard, motion, and accessibility | backlog | M | design §05, §08 | T-025B, T-026, T-027B, T-028 |
| [T-030A](tasks/T-030A-mobile-acceptance.md) | Pass the 390×844 mobile acceptance matrix | backlog | M | design §01–§08 | T-029 |
| [T-030B](tasks/T-030B-desktop-regression.md) | Preserve desktop and run the Phase 15 regression gate | backlog | M | build plan Phase 15 | T-030A |
| [T-031](tasks/T-031-phase15-close.md) | Assemble Phase 15 closure evidence | backlog | S | all Phase 15 | T-030B |

## Deferred — after Phase 15

These owner-deferred capabilities remain in backlog, but do not block Phase 14
or the mobile redesign. They are not Icebox ideas: they should be reconsidered
after the application becomes comfortable enough for permanent use.

| ID | Task | Status | Size | Spec | Blocked by |
|----|------|--------|------|------|------------|
| T-015 | Transaction type conversion and mobile type/detail boundaries | backlog | L | audit: edit transaction | T-014P |
| T-016 | Category merge/delete for transactions and Plan rules | backlog | M | audit: categories | T-001 |
| T-017 | Restore archived accounts | backlog | S | audit: accounts | T-001 |

## Icebox

Not scheduled. Rows here are notes, not commitments.

| ID | Task | Note |
|----|------|------|
| T-032 | Implement Owner invitation and safe ownership/workspace transfer | Explicitly deferred until after the mobile redesign; Phase 15 shows disabled `Owner · Coming soon`. |
| T-033 | External automatic daily rates | Explicitly deferred; Phase 15 supports manual input and a disabled `Auto · Coming soon` option. |

## Closed evidence

Archived task files live in [`tasks/archive/`](tasks/archive/). Phases 8–13 are
recorded in [`history/PROGRESS-phases-8-13.md`](history/PROGRESS-phases-8-13.md)
and Phase 14 in [`history/PROGRESS-phase-14.md`](history/PROGRESS-phase-14.md).
