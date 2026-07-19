# FinApp v2 — release specification

Status: **active and mandatory** for the next FinApp v2 release.

This specification replaces the earlier Tracker/commitment v2 design. Read it
with [`../BUILD_PLAN-v2.md`](../BUILD_PLAN-v2.md),
[`../REVIEW_PROTOCOL-v2.md`](../REVIEW_PROTOCOL-v2.md), and
[`../PROGRESS.md`](../PROGRESS.md). Historical documents cannot override it.

## 1. Product boundary and baseline

FinApp is a self-hosted personal multi-asset finance application. It retains
the existing authenticated workspace, accounts, double-entry-style ledger,
account sharing, categories, Transactions, Plan, and Analytics placeholder.
This release replaces **Tracker** with **Operations** and replaces the
workspace-level commitment model with account-specific periods.

The first-release navigation is:

```text
Accounts → account balances, total capital, Available, financial settings
Transactions → history, filters, details, correction, assignment, Delete
Operations → Spend, Add funds, Transfer, Scan, account periods, Undo
Plan → recurring future events and Link + Skip
Analytics → Coming soon
```

All UI copy is English. The public API remains under `/api/v1`; the public
health endpoint is exactly `/health`.

### Out of scope

Do not add external market-rate providers, real Scan/OCR, full Analytics,
blockchain/exchange sync, bank APIs, XLSX, Google Sheets, Telegram Mini App,
savings goals, pools, category limits, a queue, worker, Redis, Celery, or
Prometheus. Docker is in scope only in Phase 13. HTTPS and a reverse proxy stay
outside Docker Compose. Editing username, display name, or password is also
deferred from this release.

## 2. Non-negotiable financial and platform rules

- Money and rates use `Decimal`, never `float`.
- Asset precision is explicit. Ledger storage supports crypto precision and no
  input or output may silently lose precision.
- Account balances, Total capital, Available, and period values are derived
  from posted signed ledger movements; no mutable balance aggregate is a
  source of truth.
- A posted financial transaction is never physically deleted by the public
  application. `Delete` and `Undo` are soft voids and recalculate derived
  values.
- `app/budget.py` is pure: it receives dates, Decimal values, and signed
  movements only. It imports neither database nor web framework code.
- The existing account-sharing roles remain owner, editor, contributor, and
  viewer. Every mutation checks every participating account. A user with only
  shared-account access never receives owner-private periods, Plan data,
  workspace totals, or hidden legs.
- No background worker is introduced. Recurrence materialization remains
  idempotent during normal synchronous Plan requests.

## 3. Retained ledger model

An account holds one asset. Its balance is the sum of its posted signed
`TransactionLeg.amount` values. An opening balance and reconciliation are
adjustments, not direct writes to a balance.

Every `TransactionLeg` has an immutable `created_at` timestamp set when the
leg is persisted. A correction must not rewrite that timestamp to manufacture
period membership; any replacement leg receives its own creation timestamp.

Transactions retain the existing semantic types:

```text
expense | income | transfer | exchange | adjustment
```

Transfers and exchanges have a signed leg for each participating account;
cross-asset exchanges may have a fee child expense. A root transaction is a
transaction without `parent_transaction_id`. A new transaction origin is
required:

```text
manual | operations
```

`operations` identifies a root financial event created from Operations. Child
fees belong to that root event and must follow it when it is voided. Existing
transactions keep their original source/origin semantics where possible; the
release reset does not migrate legacy financial rows into the new release
schema.

## 4. Main currency and valuation rates

`Workspace.base_asset` is the workspace **Main currency**. It is selected and
changed in `Financial settings` by the workspace owner. The selected asset
always values itself at exactly `1`.

### Manual valuation rates

Add workspace-scoped manual valuation-rate CRUD. The Financial settings UI
accepts a rate in this explicit direction:

```text
1 Main currency = X Asset
```

For example, `1 USD = 26,292 VND`. The backend uses `Decimal` to calculate the
reciprocal needed for valuation; it must not round through a float. A manual
rate belongs to one workspace and one Main-currency/asset pair. It cannot be
read, changed, or deleted from another workspace.

When the owner changes Main currency, only rates whose saved Main-currency pair
matches the newly selected asset are eligible. Do not silently convert an old
manual rate or use it for the new Main currency; it may remain stored for its
original pair but is inactive until that Main currency is selected again.

The API exposes reading, saving, and deleting manual valuation rates only
within the current workspace. The response must state the displayed input rate
and the calculated effective valuation rate without hiding precision.

### Valuation precedence and display

For a non-main asset, use exactly this precedence:

1. active manual rate for the current workspace and Main-currency pair;
2. the latest posted direct rate for that pair captured by an exchange in the
   same workspace (a reciprocal stored for that same direct exchange is
   permitted);
3. `Unvalued`.

Do not use another workspace’s rate and do not build multi-hop chains through a
third asset. Voided exchanges do not supply a live rate.

Total capital, Available, and every account valued balance are quantized with
`ROUND_HALF_UP` to the Main currency's asset precision. A USD amount is always
shown with exactly two fractional digits. Ledger values remain exact before
display quantization.

Mandatory regression example:

```text
1 USD = 26,292 VND
15,258,400 VND = 580.34 USD
```

## 5. Account-specific periods

A period belongs to exactly one account and uses that account's asset. Periods
of different accounts may overlap. Date ranges of periods for the same account
must not overlap and history is retained permanently.

### Period data and lifecycle

At minimum a period records:

```text
account_id
asset_id
start_date
end_date
funding_amount
created_at
closed_at
```

Creating a period requires start date, end date, and funding amount. The UI
pre-fills funding with the account's current ledger balance, but the user may
replace it before saving. `funding_amount` is a snapshot at creation time, not
a replay of earlier activity.

- `account_id` and `asset_id` never change after creation.
- Dates and funding may be edited directly while a period is upcoming or
  current.
- Funding/date edits and correction or soft void of a posted financial record
  that changes a naturally ended period require explicit confirmation.
- A closed period is read-only.
- Creating, editing, or closing a period is owner-private; shared-account
  users do not learn its existence.

### Membership and replay

There is no single `Transaction.budget_period_id`. Membership is calculated per
account leg. A posted leg affects a period only when all conditions hold:

1. the leg belongs to the period's account;
2. the leg's immutable `created_at` is strictly after `period.created_at`;
3. its local financial date is inside the inclusive period date range.

This protects the funding snapshot: a transaction that existed before period
creation is not counted again. A transfer or exchange can legitimately affect
two simultaneous account periods—negative source leg in one and positive
destination leg in the other.

The derived period amount starts with funding and applies these signed
movements:

| Movement | Effect |
| --- | --- |
| expense, fee, transfer/exchange out, negative adjustment | decreases the account period |
| income, transfer/exchange in, positive adjustment | increases the account period |

The overall internal transfer remains neutral for Total capital. Voiding or
correcting a qualifying transaction recomputes both affected account periods.

`Available today` continues to use the pure daily-budget calculation with this
period's signed movement input. `Remaining` is the current replayed amount.
The detailed daily algorithm must stay deterministic and regression-tested in
`app/budget.py` rather than be reimplemented in the UI or database layer.

### Operations period cards

For the selected account Operations displays compact cards:

```text
Available today | Remaining | Planned
```

`Planned` is informational only: the sum of open (planned or overdue) Plan
items for the selected account whose due dates lie inside the period. It does
not reserve funding and does not reduce `Remaining`. Without a current period,
the three values are `N/A`, an `Add period` call to action is shown, and all
financial Operations remain usable.

`BudgetCommitment`, commitment snapshots, workspace-level period links,
frozen multi-asset period valuation, and their APIs are removed from the new
release schema and public API.

## 6. Operations

`Operations` replaces `Tracker` in navigation, labels, URLs, API naming, and
test scenarios. It is an action surface, not a history surface.

### Selector and persistence

The selector order is fixed:

1. `Spend`
2. `Add funds`
3. `Transfer`
4. `Scan`

On a first visit, `Spend` is active. The most recently selected selector and
account are kept locally and restored after reload when still accessible; a
missing, archived, or inaccessible account falls back safely to a valid
account. Operations does not render a list of recent transactions.

- `Spend` creates an expense.
- `Add funds` creates income.
- `Transfer` creates a same-asset transfer from one amount, or a cross-asset
  exchange from explicit `From amount` and `To amount`; `Add fee` is optional
  and creates the related fee behavior.
- `Scan` remains a visible `Coming soon` placeholder with no OCR behavior.

All actions work even when the selected account has no period.

### Persistent Undo

Every selector shows only one compact `Undo` control for the selected account.
The server determines the candidate: the most recent eligible **root** posted
transaction created by the current user through Operations that has a leg on
that account. The result survives browser reload.

Undo soft-voids that root and its relevant children, so balances and all
affected account periods replay. It never hard-deletes a financial record.
After Undo, the control disappears and must **not** fall back to an older
transaction. Persist a consumed/cursor state for this user/account so that
server-side behavior is deterministic after reload. A later newly-created
Operations transaction can establish a new candidate.

If the undone root has legs on multiple accounts, consume it atomically for the
creator on **every** participating account. Thus Undoing a transfer from its
source account also prevents its destination account from falling back to an
older candidate. A new later Operations root establishes a candidate normally
for each account on which it has a leg.

Expose an authenticated API to fetch the selected account's latest undoable
transaction and a command to Undo it. Both endpoints enforce account rights
and the current user's creator identity.

## 7. Transactions

Transactions remains the ledger history and management surface, but it no
longer creates new financial events: remove `Add transaction` and equivalent
creation controls. Creation happens only through Operations.

Keep list filters, details, correction, account assignment, and status views.
Add a `Period` filter whose choices are rendered as:

```text
Account · dates · status
```

The filter returns transactions with a qualifying leg on the selected period's
account using the exact membership/snapshot rules in section 5; it includes
expenses, income, transfers, and exchanges.

Replace the visible `Void` control with compact `×` and tooltip `Delete`.
Before deletion, show a confirmation that the record remains in history but no
longer affects balances or periods. The resulting soft-voided record is shown
as `Deleted` when the status filter includes it. The public UI and API must no
longer advertise legacy `Void` terminology as the primary action.

## 8. Plan

Plan stays a future-events system: it never creates a financial transaction.
Existing recurrence generation remains idempotent and synchronous.

### Rule card and details

Render one card per rule. The card exposes at most:

- the overdue occurrence closest to today, if any; and
- the nearest future occurrence.

If there are multiple overdue occurrences, show the nearest one and a badge
with the total overdue count. Completed, skipped, remaining overdue, and all
other future occurrences are available only in rule details. Do not show the
old long `Upcoming income` or global future-occurrence lists. Keep `Open`,
`Completed`, and `Show` controls compact.

### Link and Skip only

Remove `Pay` and `Receive` from both UI and public API. The only occurrence
actions are:

- `Link` — attach an already posted transaction; and
- `Skip` — mark the occurrence skipped.

Link validates semantic type, not account or asset equality:

| Rule kind | Allowed posted transaction type |
| --- | --- |
| income | income |
| required expense, subscription, other expense | expense |
| reserve transfer | transfer |

Different actual account and asset are valid. A linked occurrence response
returns the actual amount and actual asset. Linking does not move a transaction
between periods; the transaction's own signed legs already determine period
membership. Invalid type, non-posted transaction, inaccessible transaction, or
an already resolved occurrence is rejected.

## 9. API, permissions, and compatibility removals

The release keeps the `/api/v1` boundary. The implementation may refine route
shapes, but must expose these capabilities:

- owner-only Main-currency read/update and workspace-scoped manual valuation
  rate list/save/delete;
- account-specific period list/create/read/update/close and current/history
  reads for an owner;
- Operations create commands, selected-account undo candidate read, and Undo;
- Transaction period filtering, details, correction, assignment, and soft
  Delete;
- Plan rule/details reads and occurrence Link/Skip only.

Remove public routes and clients for legacy Tracker periods/commitments and
Plan Pay/Receive. Do not preserve obsolete routes merely because current code
has them: the reset schema and documentation form the compatibility boundary.

Authorization is enforced server-side. A Plan item, an owner-private period,
or a rate from one workspace may never be inferred through IDs, list filters,
error messages, or aggregate results by another user.

## 10. Clean release reset and migration

Before replacing or deleting local `finapp.db`, create a timestamped,
recoverable copy in `.backups/` and record its SHA-256 checksum and restore
verification in `docs/PROGRESS.md`. Verify the backup can be opened before
continuing.

The release starts with a clean database and a new Alembic history. No legacy
rows, test rows, commitments, or old workspace-level periods are migrated.
Fresh migration must create only the release schema and seed the eight required
assets: VND, USD, RUB, EUR, USDT, BTC, ETH, and TRX.

## 11. Docker delivery

Docker is implemented only in Phase 13:

- one non-root Python 3.12 application container;
- Alembic migration runs before Uvicorn and migration failure prevents startup;
- `/health` is the container healthcheck;
- SQLite resides in persistent volume path `/data/finapp.db`;
- Compose runs exactly one application replica;
- TLS/reverse proxy are external to Compose.

The README must document build, start, persistent-volume behavior, backup, and
restore. Deployment verification proves data survives a container restart.

## 12. Release acceptance criteria

The release is complete only when all of the following hold:

1. Main currency selection and workspace-isolated valuation rates work, with
   manual override/delete/fallback precedence and correct `ROUND_HALF_UP`
   formatting.
2. Total capital, Available, and account valued balances use only the current
   workspace's permitted valuation rate; the VND/USD regression example passes.
3. Operations opens on `Spend`, preserves selector/account locally, has the
   required selector order, supports all financial actions without a period,
   and never lists operation history.
4. Undo is server-persistent, creator/account scoped, soft-voids correctly,
   survives reload, and never falls back to an older transaction.
5. Account periods have snapshot funding and signed-leg replay; same-account
   periods cannot overlap while different-account periods can.
6. Transfers/exchanges update both affected account periods. A same-asset
   internal transfer remains neutral to Total capital; a pre-period transaction
   does not double-count.
7. Transactions has period filtering, details/correction/assignment, and
   soft `× Delete` with a visible `Deleted` status; it has no add flow.
8. Plan has one card per rule, at most overdue-plus-next on the card, and only
   Link/Skip; cross-asset/account semantic linking works and Pay/Receive routes
   are absent.
9. Sharing preserves account permissions and never reveals owner-private Plan
   or period data.
10. Scan and Analytics remain stable `Coming soon` views.
11. Every logical block has passed independent reviewer-subagent review.
12. Full tests, JavaScript check, fresh migration, phone/desktop scratch-browser
    acceptance, Docker persistence, and documented backup/restore all pass.
