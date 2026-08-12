# FinApp v2 — release specification

Status: **active and mandatory**; incorporates the accepted Phase 14 backend
contract and is the authority for Phase 15.

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

Workspace-scoped manual valuation-rate CRUD uses one canonical public
direction:

```text
1 Asset = X Main currency
```

For a VND workspace asset and USD Main currency, the pair is `VND → USD` and
the saved rate is the exact USD value of one VND. `PUT` accepts exactly a
positive plain Decimal string under `rate`; JSON numbers, exponent notation,
unknown fields, and values beyond Numeric(38,18) are rejected before mutation.
No canonical write computes or stores a reciprocal.

Responses expose `from_asset`, `to_asset`, exact Decimal-string `rate`, and
`source=manual`. The source is the path asset and the target is the workspace's
current Main currency. Legacy opposite-direction public fields are absent.
A manual rate belongs to one workspace and one Main-currency/asset pair and
cannot be inferred, read, changed, or deleted from another workspace.

When the owner changes Main currency, only rates whose saved Main-currency pair
matches the newly selected asset are eligible. Do not silently convert an old
manual rate or use it for the new Main currency; it may remain stored for its
original pair but is inactive until that Main currency is selected again.

An older stored opposite-direction row may remain readable for shipped account
valuation, but new transfer quoting requires the owner to resave it in the
canonical Asset-to-Main direction. No new API accepts the legacy direction.

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
1 VND = 0.000038034383082306 USD
15,258,400 VND = 580.34 USD after Main-precision presentation rounding
```

## 5. Account-specific periods

A period is an optional daily-spending mode for exactly one account. It uses
that account's asset and answers how much can be spent today for the live
ledger balance to last through an inclusive end date. Accounts and every
financial command work normally without a period. Periods are owner-private;
shared users cannot infer their existence, values, settings, or history.

### Period data and lifecycle

The authoritative period fields are:

```text
account_id
asset_id
start_date
end_date
snapshot_at
opening_balance
rollover_policy
created_at
closed_at
closing_balance
```

`account_id` and `asset_id` are immutable. `start_date` is an owner-selected
workspace-local date not later than today; omission selects today. `end_date`
is inclusive and cannot precede Start date. On create, the server derives the
UTC `snapshot_at` boundary and exact posted-ledger `opening_balance`; clients
cannot submit either value. A current period may change Start date, End date,
or policy. A Start-date change atomically reconstructs the snapshot and replay
partition without changing the live ledger balance.

The lifecycle is `current`, `ended`, or `closed`. Natural expiry is write-free:
an ended record is immutable with null `closed_at` and `closing_balance`.
Manual close atomically captures both the close time and exact ledger balance.
Either state permits an immediate successor, including on the same local day;
only another current period blocks create. Different accounts are independent.

### Membership and replay

There is no transaction-level period foreign key. The canonical movement set
is calculated per signed account leg in one captured time window. Every member
must satisfy `leg.account_id == period.account_id` and its parent transaction
must have `status=posted`, in addition to the applicable time bound:

```text
snapshot_at < leg.created_at <= closed_at           # manually closed
snapshot_at < leg.created_at <= reference_time      # current
snapshot_at < leg.created_at < period_end_boundary  # ended
```

The snapshot boundary is the later of local Start-day boundary and any
predecessor close/end boundary. Opening includes legs exactly at that boundary;
replay starts strictly after it. The transaction's financial date selects its
effective replay day and clamps to the period/replay boundaries. The
Transactions period filter uses the same movement set.

For a current period, `current_balance` is exactly the account's posted-ledger
balance. A derived, unstored `reconciliation_delta` adjusts the opening pool
when correction, Delete, or Undo changes a pre-period leg:

```text
window_net = exact sum of signed posted legs in the current period window
reconciliation_delta = current_balance - (opening_balance + window_net)
calculation_opening_balance = opening_balance + reconciliation_delta
```

Then `calculation_opening_balance + window_net == current_balance`. Closed
history keeps its immutable opening/closing snapshots even when later ledger
edits change the live account balance.

`funding_amount`, `remaining`, `account_balance`, and `planned` are removed
from the period contract. Period endpoints never query Plan. The account
balance always exists; `available_today` exists only for a current period.

### Daily allowance policies

Each period stores exactly one policy:

```text
carry_next_day | redistribute_remaining_days
```

Omission defaults to `redistribute_remaining_days`. Both algorithms use exact
Decimal internally and quantize API presentation to asset precision with
`ROUND_HALF_UP`.

For `carry_next_day`, the initial `daily_base` is the calculation opening pool
divided by inclusive period days. A completed day's complete non-negative
unused amount carries only into the next day and continues accumulating when
unused. After overspend, carry resets to zero and the remaining pool is divided
over later days.

For `redistribute_remaining_days`, every new local day divides the exact
start-of-day balance over all inclusive days still remaining:

```text
start_of_day_balance = current_balance - today_net
days_remaining = (end_date - today) + 1
available_today = start_of_day_balance / days_remaining + today_net
```

Movements are applied once. Rounding residue stays in the exact pool; a
negative balance may yield a negative allowance. `available_today` is
informational and never authorizes or blocks spending.

### Operations period cards and API

Operations always displays the selected account's current ledger balance. It
also displays `available_today` when a current period exists; otherwise Start
period is offered. No Plan amount reserves account money.

The period API stays under `/api/v1`:

```text
POST  /accounts/{account_id}/periods
GET   /accounts/{account_id}/periods/current
GET   /accounts/{account_id}/periods?scope=history
GET   /account-periods/{period_id}
PATCH /account-periods/{period_id}
POST  /account-periods/{period_id}/close
```

Current lookup returns an object or HTTP 200 JSON `null`. Ended/closed records
are read-only historical shapes without live balance or allowance fields.

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
- `Transfer` uses one source amount and destination account for same-asset or
  cross-asset movement through the bound quote/execute contract below.
- `Scan` remains a visible `Coming soon` placeholder with no OCR behavior.

All actions work even when the selected account has no period.

### Bound transfer quote and execution

`POST /api/v1/operations/transfer/quotes` accepts distinct source/destination
account IDs, one positive plain Decimal-string `from_amount`, and
`rate_source=manual`. A same-asset quote uses identity rate `1`. A cross-asset
quote derives the exact destination amount only through the current workspace
Main currency and canonical Asset-to-Main manual rates; it uses no external,
latest-exchange, legacy reciprocal, multi-hop, or foreign-workspace rate.

The source amount is validated once at source precision. Exact Decimal helpers
calculate source → Main → target without ambient-context rounding, then the
unrounded target result is quantized exactly once with `ROUND_HALF_UP` to the
destination asset precision. The quote is accepted only if the exact outgoing
Main value equals the exact incoming Main value after that target quantization
and before any Main/presentation rounding. Otherwise it returns
`422 Transfer amount cannot preserve Total capital` and writes nothing. This
equality gate prevents destination rounding from changing aggregate capital.

The server persists an immutable owner-private five-minute quote with exact
source/destination amounts and captured Main/rate dependencies. Quote creation
does not move money. `POST /api/v1/operations/transfer/quotes/{quote_id}/execute`
atomically verifies creator, current permissions, expiry, open state, and every
captured dependency, then posts the persisted amounts through the existing
transfer/exchange and period/Undo paths. The quote is single-use under
concurrency; any provisional failure rolls back both financial writes and the
claim so a still-valid quote remains retryable.

The existing direct same-asset transfer API remains supported for its shipped
editor workflow. The new quote surface is owner-private because it depends on
workspace-private Main currency and manual-rate state.

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

### Mobile financial-date feed

The richer existing `/transactions` API remains available. The mobile adapter
is `GET /api/v1/transaction-feed` with exact filters
`all|income|expense|transfer|planned`, a bounded limit, and an opaque versioned
cursor. It returns closed discriminated `transaction` and `planned` items in
one stable descending total order by financial date, sort timestamp, kind rank,
and item ID. Correction moves a persisted row according to its new financial
date; soft Delete retains it at that position with Deleted status.

Persisted transaction items retain the exact nested transaction and signed
legs. Exchanges render as mobile transfer while remaining identifiable as
`exchange`; adjustments remain identifiable non-convertible balance
corrections and appear only in All. Visibility and hidden-leg redaction reuse
the existing transaction permissions. Detail routes are
`/transaction-feed/transaction/{transaction_id}` and
`/transaction-feed/planned/{occurrence_id}`; hidden or foreign IDs share a
generic not-found response.

Open owner-private Plan occurrences join only All/Planned as explicit
non-ledger projections. Query and cursor validation finish before synchronous
idempotent Plan materialization. Planned rows never create transactions or
legs and never affect balances, Total capital, Available, periods, or Undo.
Only `planned|overdue` occurrences appear; completed items are represented by
their linked persisted transaction and skipped/archived items are absent.

## 8. Plan

Plan stays a future-events system: it never creates a financial transaction.
Existing recurrence generation remains idempotent and synchronous.

### Mobile rule contract

The existing five stored kinds and Plan routes remain authoritative. Create,
PATCH, list, and owner-private detail responses expose a mobile adapter without
changing storage:

| Stored kind | `mobile_kind` |
| --- | --- |
| `income` | `expectedIncome` |
| `required_expense` | `requiredExpense` |
| `subscription` | `subscription` |
| `reserve_transfer` | `reserveTransfer` |
| `other_expense` | `otherExpense` |

Mobile input may use those camelCase values. The single mobile `account_id`
maps to `default_to_account_id` with `account_field=to_account` for expected
income and to `default_from_account_id` with `account_field=from_account` for
expense/transfer kinds. Conflicting directional fields fail validation.
Existing category, asset, owner-privacy, Decimal amount, recurrence, and
`is_required` rules remain enforced.

Archiving a rule is the mobile Delete-rule consequence: it disables selection
and future generation, skips open occurrences, and retains resolved occurrence
history and every linked financial transaction.

### Rule card and details

Render one card per rule. The card exposes at most:

- the overdue occurrence closest to today, if any; and
- the nearest future occurrence.

If there are multiple overdue occurrences, show the nearest one and a badge
with the total overdue count. Completed, skipped, remaining overdue, and all
other future occurrences are available only in rule details. Do not show the
old long `Upcoming income` or global future-occurrence lists. Keep `Open`,
`Completed`, and `Show` controls compact.

### Occurrence Link and Skip only

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

An unresolved planned-feed detail exposes the ordered mobile actions
`edit_rule`, `skip`, and `link_transaction`. Skip resolves only that occurrence;
it never archives or edits the rule.

## 9. API, permissions, and compatibility removals

The release keeps the `/api/v1` boundary. The implementation may refine route
shapes, but must expose these capabilities:

- owner-only Main-currency read/update and workspace-scoped manual valuation
  rate list/save/delete;
- account-specific period list/create/read/update/close and current/history
  reads for an owner;
- Operations create commands, selected-account undo candidate read, and Undo;
- owner-private bound transfer quote/execute with exact captured dependencies;
- Transaction period filtering, details, correction, assignment, and soft
  Delete;
- the stable financial-date transaction/planned feed and its detail routes;
- Plan rule create/edit/list/detail/archive plus occurrence Link/Skip.

Remove public routes and clients for legacy Tracker periods/commitments and
Plan Pay/Receive. Do not preserve obsolete routes merely because current code
has them: the reset schema and documentation form the compatibility boundary.

Authorization is enforced server-side. A Plan item, an owner-private period,
or a rate from one workspace may never be inferred through IDs, list filters,
error messages, or aggregate results by another user.

### Explicit post-Phase-15 deferrals

Phase 15 does not implement or promise these controls; their backend tasks
remain ordered in the post-Phase-15 backlog:

- T-015 transaction-type conversion;
- T-016 category merge/delete across transactions and Plan rules;
- T-017 archived-account restoration.

Existing supported rename/archive, transaction correction, account archive,
and richer desktop/backend behavior remain intact. The mobile UI omits Type
conversion and category merge/delete, and its account archive copy does not
promise restoration. Owner-role transfer and automatic external rates remain
disabled `Coming soon` options.

## 10. Clean release reset and migration

Before replacing or deleting local `finapp.db`, create a timestamped,
recoverable copy in `.backups/` and record its SHA-256 checksum and restore
verification in `docs/PROGRESS.md`. Verify the backup can be opened before
continuing.

The release started with a clean database and a new Alembic history. No legacy
rows, commitments, or old workspace-level periods were migrated. Fresh
migration creates the release schema and seeds the eight required assets: VND,
USD, RUB, EUR, USDT, BTC, ETH, and TRX.

Until Phase 15 is accepted and the owner explicitly starts permanent use, the
database contains disposable pre-production test data under
[`ADR-0010`](../decisions/ADR-0010-preproduction-fast-track.md). The Phase 14/15
migration gate is limited to fresh `alembic upgrade head`, exactly one Alembic
head, schema constraints, `alembic check`, application startup, and `/health`.
Populated upgrades, downgrades, and preservation of current test rows are not
supported release gates. The known populated-`0002` ambient-Decimal risk is
accepted only because that migration path will not be used for permanent data.

This policy does not relax runtime Decimal precision, ledger derivation,
permissions, privacy, atomicity, or fresh-schema correctness. Once permanent
use begins, each later schema change must preserve the then-current database or
carry an explicit backup/reset decision.

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

Phases 8–13 retain their shipped acceptance evidence. Phase 14 is complete
only when the retained backend additions below and the ADR-0010 gate hold:

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
5. Optional account periods derive exact opening/current/closing values from
   ledger snapshots and replay; current balance always equals Accounts, natural
   expiry is immutable/write-free, and ended/closed periods permit successors.
6. Transfers/exchanges update both affected account periods. A same-asset
   internal transfer remains neutral to Total capital; a pre-period transaction
   does not double-count.
7. Period create/PATCH exposes only Start date, End date, and the two policies;
   no funded/remaining/planned field survives, and Available today never blocks
   spending.
8. Bound quote/execute derives and atomically posts exact same/cross-asset
   amounts with expiry, stale-dependency, concurrency, rollback, permission,
   period, captured-rate, and Undo behavior enforced.
9. The financial-date feed pages every persisted domain type and owner-private
   planned projections without lossy amounts, unstable cursors, fake ledger
   rows, or privacy leaks.
10. Plan exposes exact mobile kind/account create-edit-detail fields while
    preserving the five-kind subsystem and occurrence Skip/Link/archive
    semantics.
11. Sharing preserves account permissions and never reveals owner-private Plan,
    period, quote, rate, or hidden-leg data.
12. Scan and Analytics remain stable `Coming soon` views; the deferred
    T-015/T-016/T-017 controls are omitted.
13. Every written task has one independent read-only review with all blocking
    findings closed.
14. The lean retained-contract smoke, one full pytest, JavaScript syntax,
    `git diff --check`, one Alembic head, fresh upgrade/check, application
    startup, `/health`, and SPA root all pass. Populated upgrade and downgrade
    are intentionally outside this pre-production gate.
