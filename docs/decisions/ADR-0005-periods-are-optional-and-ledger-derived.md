# ADR-0005 — Periods are optional and derive from the ledger

Status: accepted · 2026-08-08 · source: `specs/ACCOUNT_PERIODS-v2.1.md`

## Context

The shipped v2 period carried an editable `funding_amount` and a replayed
`Remaining` value. Together with the account's real ledger balance that gave
the user two numbers that both looked like "the money on this account" and
could disagree. The period also consumed `planned`, which coupled it to the
Plan subsystem.

## Decision

- A period is an optional daily-spending mode on one account. Having no period
  is a normal state; every Operations command works without one.
- The posted signed `TransactionLeg` ledger is the only source of the current
  balance. `current_balance` is derived, never stored.
- `funding_amount` is removed from the model and from every calculation.
- `planned` is removed from period logic; Plan stays a separate source of
  expected future events and never reserves account money.
- `opening_balance` is an immutable snapshot; later changes to pre-period
  ledger truth enter the pure calculation once, through a derived
  `reconciliation_delta`.
- A naturally ended period is immutable with `closed_at=null` and
  `closing_balance=null`. The backend does not invent a historical balance for
  a boundary it never observed, because there is no as-of ledger event log.
- Closing early captures an exact `closing_balance` and permits a successor
  immediately, even when the original planned end date is later.

## Consequences

- Two independently editable representations of the same money cannot exist.
- Closed-period history is a snapshot and is never recalculated from rows that
  later changed.
- The old rule that rejected every overlapping historical date range on one
  account is superseded: only a *current* period blocks a new one.
- The document remains proposed until Phase 14 is accepted and merged into
  `specs/FinnApp-v2.md`; until then `specs/FinnApp-v2.md` is the active
  authority.
