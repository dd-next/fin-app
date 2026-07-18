# BUILD_PLAN-v2.md — FinApp v2 phases

The authoritative specification is `specs/FinnApp-v2.md`. The old
`BUILD_PLAN.md` and numbered SPEC addenda describe completed earlier versions
and are not active requirements on this branch.

Every phase ends with relevant tests, the complete test suite, an update to
`PROGRESS.md`, and a separate commit. The repository must remain runnable at
every checkpoint.

## V2 Phase 0 — Specification authority

- Make `specs/FinnApp-v2.md` decision-complete and authoritative.
- Point `AGENTS.md`, `CLAUDE.md`, README, and `PROGRESS.md` at the v2 files.
- Mark previous specifications and `BUILD_PLAN.md` as historical.
- Record the agreed release boundary and destructive-reset policy.

Tests: current full suite and JavaScript syntax check stay green.

## V2 Phase 1 — Clean identity, workspace, assets, and categories

- Back up the exact local `finapp.db` to `.backups/finapp-pre-v2-<timestamp>.db`.
- Remove the old local database and replace the old Alembic chain with a fresh
  v2 chain. Legacy rows are not migrated.
- Implement always-on web authentication with open registration, login,
  logout, current user, persistent opaque sessions, and automatic personal
  workspace creation.
- Add workspace base asset/timezone, global assets with explicit decimals, and
  workspace categories.
- Seed VND, USD, RUB, EUR, USDT, BTC, ETH, and TRX idempotently.
- Remove Telegram, Google Sheets, bootstrap-owner, goals, pools, limits, XLSX,
  and their unused dependencies/routes/tests.
- Serve a small authenticated shell so the app is runnable before later UI
  phases.

Tests: clean `alembic upgrade head`, auth/session isolation, registration,
asset precision validation, category isolation, `/health`, app boot.

## V2 Phase 2 — Accounts and double-entry-style ledger

- Add Account, Transaction, TransactionLeg, and exchange-derived rate storage.
- Implement accounts, opening-balance adjustment, reconcile, archive, account
  history, total capital, available total, and unvalued-asset reporting.
- Implement expense, income, same-asset transfer, cross-asset exchange,
  adjustment, fee child transaction, accountless transaction, account
  assignment, correction, and void.
- Freeze the base-currency value used by a period at transaction time.
- Use the latest posted direct or inverse exchange rate for live summaries;
  require a per-transaction base equivalent when no rate exists.
- Never hard-delete a posted financial transaction through the public API.

Tests: ledger invariants, Decimal/asset scale, balances, available exclusions,
exchange rates, transfer neutrality, fees, unassigned operations, corrections,
void, filtering, pagination, and workspace isolation.

## V2 Phase 3 — Account sharing and permission enforcement

- Add AccountAccess and one-time expiring AccountInvitation links.
- Support owner, editor, contributor, and viewer permissions exactly as defined
  in the specification.
- Show invited users only shared accounts and related transaction legs; redact
  inaccessible legs and expose `has_hidden_legs`.
- Require edit rights on every participating account for multi-account
  mutations; contributors can add only expenses to the shared account.
- Keep workspace Plan, Tracker, other accounts, and aggregate totals private.

Tests: invitation lifecycle, all role capabilities/denials, hidden-leg
redaction, multi-account permission checks, expired/reused tokens, and no
workspace-total leakage.

## V2 Phase 4 — Accounts and Transactions frontend

- Replace the legacy SPA with the five-section shell: Accounts, Transactions,
  Tracker, Plan, Analytics.
- Build Accounts: total capital, Available, asset groups, unvalued warnings,
  create/edit/reconcile/archive, details/history, and sharing.
- Build Transactions: filters, expense/income/transfer/exchange/adjustment
  forms, edit, void, account assignment, category, comment, date, and author.
- Show Analytics as a stable `Coming soon` placeholder.
- Keep all copy English and all primary controls usable at phone and desktop
  widths.

Tests: API integration remains green, JavaScript syntax, DOM/UI smoke checks,
and scratch-browser flows for accounts, transactions, sharing, and responsive
navigation.

## V2 Phase 5 — Plan rules and occurrences

- Add PlanRule and PlanOccurrence for income, required expense, subscription,
  reserve transfer, and other expense.
- Support once, weekly, monthly, and yearly recurrence. Clamp monthly/yearly
  dates to the last valid day and materialize a rolling 12-month horizon
  idempotently when rules are created, edited, or listed.
- Implement planned/completed/skipped/overdue states and explicit linking to an
  existing or newly created transaction.
- Add Plan UI for upcoming income, required spending, subscriptions, reserve
  transfers, overdue items, and plan-vs-actual.

Tests: recurrence boundaries/leap years, no duplicate occurrences, rule edits,
pay/receive/skip/link flows, account/category validation, and plan permissions.

## V2 Phase 6 — Tracker periods and commitments

- Add BudgetPeriod, BudgetCommitment, and RebaseEvent; preserve non-overlapping
  period history and explicit ended-period correction confirmation.
- After a planned income is received, return a proposed period from its local
  date through the day before the next planned income; require confirmation.
- Snapshot required expenses and reserve transfers as commitments.
- Use planned commitment value before fulfillment and actual frozen base value
  after fulfillment; exclude the linked transaction from ordinary daily spend.
- Generalize pure budget math to the base asset quantum while preserving
  carry-over, overspending rebase, live pending preview, deletion/void
  recomputation, and next-day savings decisions.
- Build Tracker UI for today, remaining period, commitments, quick expense,
  history, proposal confirmation, and ended-period correction.

Tests: pure budget matrix, multi-asset frozen valuation, period proposal,
overlap, commitment plan-vs-actual, no double deduction, opening-income
exclusion, carry/rebase/prompt, history, and corrections.

## V2 Phase 7 — Final integration and release verification

- Complete accessibility, empty/loading/error states, responsive layout, and
  permission-aware controls across all five sections.
- Update README and Russian manual test cases to match actual labels/routes.
- Remove dead legacy code, tests, dependencies, and documentation references.
- Verify fresh install, migration, registration, all API flows, SPA behavior,
  and every acceptance criterion in the authoritative specification.

Tests: complete `pytest`, JavaScript syntax, fresh-DB Alembic check, and
scratch-DB browser E2E at 480×900 and 1280×900.

## Future work — not active phases

- Blockchain/exchange read-only synchronization and import inbox.
- Full Analytics API and reports.
- XLSX export.
- External market-rate providers.
- Bank API integrations, Telegram Mini App, and Google Sheets.
