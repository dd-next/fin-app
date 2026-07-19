# SPEC-4 — Family finance expansion

> Historical specification for the completed family-finance branch. The active
> specification is [`FinnApp-v2.md`](FinnApp-v2.md). All
> instructions below are archival and must not be executed.

This addendum supersedes the single-user/single-period limitations in
`SPEC.md`. Existing daily-budget replay semantics remain unchanged.

## 1. Product intent

FinApp evolves from a personal daily allowance tracker into a lightweight
family finance manager for two people, without adding bank integrations,
multi-currency accounting, debt settlement, or background infrastructure.

The product supports personal and shared financial spaces, historical budget
periods, categories and category limits, budget pools, and cross-period
savings goals.

## 2. Workspaces and access

- Every user owns one personal workspace.
- Users may also belong to shared workspaces.
- Periods, categories, pools, and goals belong to a workspace; periods are not
  shared directly with individual users.
- Shared roles are `owner` and `editor`. Both edit financial data; only an
  owner manages members and invitations.
- Web authentication uses username/password plus opaque server-side sessions.
- All object access is checked through workspace membership.

## 3. Periods and operations

- Periods are preserved permanently; creating a period never deletes another.
- Period date ranges may not overlap inside one workspace. Personal and shared
  workspaces may have parallel periods.
- Period state (`upcoming`, `current`, `ended`) is derived from inclusive dates.
- Ended periods can be corrected after explicit confirmation.
- An operation has an explicit `occurred_on` financial date and a separate
  technical creation timestamp.
- Legacy operations without a category remain valid as Uncategorized.
- Period totals, category totals, pool totals, and goal balances are derived
  from operations rather than stored as mutable aggregates.

## 4. Categories and limits

- Categories are reusable workspace-level definitions and are archived rather
  than deleted after use.
- Only expenses may reference a category in this increment.
- Category limits are optional and belong to `(period, category)`.
- Before pools exist, configured category limits may not sum above the period
  total.
- Actual overspending is never blocked. The operation is saved and the API
  returns a warning containing limit, spent amount, and overage.

## 5. Pools

- A pool is a reusable workspace-level definition such as Home or Food.
- Each period assigns an optional allocation to a pool.
- A category belongs to at most one pool in a specific period.
- Category limits within a pool may not sum above the pool allocation.
- Pool allocations, unpooled category limits, and planned savings
  contributions may not sum above the period total.
- Actual spending may exceed a pool and produces a warning.
- Pool balances do not roll into the next period automatically.
- New-period creation may explicitly clone the previous period's plan.

## 6. Savings goals

- Savings goals persist across periods and have a target amount plus an
  optional target date.
- `transfer_to_goal` decreases the period balance and increases the goal.
- `transfer_from_goal` performs the inverse and may not make the goal negative.
- Transfers are represented in the operation ledger and are atomic.

## 7. API and export

- New public application routes live under `/api/v1` and always carry an
  explicit workspace identifier. Period history, corrections, plans, and
  exports use explicit period identifiers; current-period read/write shortcuts
  may exist for simple clients.
- Authentication routes provide login, logout, and current-user context.
- Mutation responses include the updated summary and any soft warnings.
- XLSX export is period-specific and includes operation category, pool, savings
  goal, and author information when available.
- Legacy root financial routes are removed after the frontend transition.
- Google Sheets synchronization is not expanded. A future Apps Script
  integration must use a workspace-scoped read-only credential.

## 8. Migration and compatibility

- Existing `finapp.db` data is assigned to the first owner's personal
  workspace.
- Existing amounts, dates, comments, kinds, and budget results must survive.
- The physical `expense` table is renamed to `operation`.
- Existing operation financial dates are backfilled from their local
  `created_at` dates.
- SQLite remains supported for the family beta. Postgres, HTTPS, and backups
  are required before opening registration to external users.

## 9. Acceptance criteria

1. Creating a period does not remove history.
2. Periods cannot overlap inside a workspace.
3. Personal and shared workspace data is access-isolated.
4. Two shared members see the same operations and summaries.
5. Category and pool plan sums are validated without blocking real spending.
6. Reclassifying or deleting an operation recomputes all derived totals.
7. Savings transfers atomically affect both the period and the goal.
8. A pre-SPEC-4 database upgrades without losing financial rows or changing
   the resulting daily-budget calculation.
9. All automated tests and the scratch-DB browser verification pass.
