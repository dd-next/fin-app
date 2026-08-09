# FinApp v2.1 — account-period backend and budget logic requirements

Status: **proposed change specification; not yet implemented**.

This document records the agreed backend and domain-logic changes for account
periods. It is intended to become the implementation source for the next
period revision after approval. Until it is merged into
[`FinnApp-v2.md`](FinnApp-v2.md), that file remains the active release
authority.

Frontend composition, responsive layout, visual states, and the Claude
Design/Figma handoff are intentionally specified separately. This document
defines only the financial semantics and the public backend contract that the
frontend must be able to consume.

## 1. Product definition

An account period is an optional daily-spending mode for one account. It
answers one question:

> How much can be spent today so that the account's current money lasts until
> the selected end date?

A period is not a separate wallet, budget envelope, commitment, or mutable
balance. Accounts and every Operations command continue to work without a
period.

Typical spending accounts may use periods. Reserve, savings, investment,
crypto, or any other account may remain without one indefinitely.

## 2. Non-negotiable financial rules

- The posted signed `TransactionLeg` ledger remains the sole source of truth
  for the current account balance.
- Money calculations use `Decimal`, never `float`.
- Stored ledger values remain exact. API display values are quantized to the
  account asset precision with `ROUND_HALF_UP`.
- `app/budget.py` remains pure and imports no database or web-framework code.
- No scheduler, queue, worker, Redis, or background process is introduced.
  Day-boundary results are derived deterministically during synchronous reads.
- Periods remain owner-private. Shared-account users must not discover period
  existence, settings, daily allowance, or history.

## 3. Period data model

The new period model must support at least:

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

Rules:

- `account_id` and `asset_id` are immutable.
- `snapshot_at` is the exact UTC replay boundary derived from the selected
  workspace-local `start_date` and any predecessor boundary. `opening_balance`
  is the account's exact posted-ledger balance at that boundary.
- `snapshot_at` and `opening_balance` may be recomputed only as part of an
  atomic Start-date change on a current period. They become immutable when the
  period ends or closes; clients can never submit either value.
- `closing_balance` is nullable unless the user explicitly closes the period.
  Manual close captures it from the exact posted ledger balance.
- `start_date` is an owner-selected workspace-local date not later than today;
  omitting it on create selects today. Scheduled future periods are outside
  this revision.
- `end_date` is inclusive and must not precede `start_date`.
- `rollover_policy` uses one of the stable values defined in section 7.
- `funding_amount` is removed from the public model and must not participate in
  any calculation. A transitional storage column may exist only for a bounded
  migration and must not remain a source of truth.
- `planned` is removed from period responses and Operations period logic. The
  Plan subsystem otherwise remains unchanged.
- The current balance is derived live through the same ledger query used by
  Accounts. It must not be stored as another mutable period field.

The implementation must not expose two independently editable values that can
both appear to represent the money remaining on one account.

## 4. Optional lifecycle and status

An account may have zero or one active period. Having no period is a normal
state, not an error.

The externally visible lifecycle is:

```text
no period -> current -> ended or closed -> no period / new current period
```

- `current`: not closed and the workspace-local date is inside the inclusive
  start/end range.
- `ended`: not explicitly closed and the workspace-local date is after
  `end_date`.
- `closed`: `closed_at` is set, regardless of the originally planned end date.

An ended period is historical and read-only, does not block a successor, and
has `closed_at=null` and `closing_balance=null`. The backend must not pretend
that it captured a closing balance at the natural date boundary when no
immutable as-of balance snapshot exists. No lazy finalization or background
worker is required.

An ended period cannot be extended, edited, or manually closed after it has
ended. This prevents it from becoming current again beside a successor and
prevents a later live balance from being mislabeled as its historical closing
balance.

Financial Operations must remain enabled in every lifecycle state.
`available_today` is unavailable when there is no current period.

## 5. Closing and starting the next period

Closing means that the period stops immediately. It must do all of the
following atomically:

1. capture `closed_at` in UTC;
2. capture `closing_balance` from the exact posted account ledger;
3. make the closed period immutable;
4. make the account immediately eligible for a new period.

A closed or naturally ended period must not block creation of a new period
because its original planned date range extends into the future. The previous
same-account rule that permanently rejects every overlapping historical date
range is superseded.

Only an existing current period blocks creation of another current period for
the same account. Since ended periods are read-only, they cannot later be
extended across a successor. Different accounts remain independent.

Closing and creating a new period on the same workspace-local calendar day is
valid. The canonical account movement window provides the precise boundary
for period allowance replay. Let `start_boundary` be the first UTC instant of
`start_date` in `Workspace.timezone`. If a predecessor closes or naturally
ends after that instant, use that predecessor boundary instead so a same-day
successor never replays its movements:

```text
snapshot_at = max(start_boundary, predecessor.closed_at or predecessor_end_boundary)
leg.account_id == period.account_id
transaction.status == posted
snapshot_at < leg.created_at <= period.closed_at   # closed period
snapshot_at < leg.created_at <= reference_time     # current period
snapshot_at < leg.created_at < period_end_boundary # ended period
```

`period_end_boundary` is the first UTC instant after the inclusive `end_date`
in `Workspace.timezone`. An ended period never includes a leg at or after that
boundary, so it cannot absorb successor-era activity. Its effective replay day
clamps to `end_date`. A current period uses the synchronous read time as
`reference_time`; a manually closed period uses `closed_at`.

Period creation must atomically reconstruct `opening_balance` from all current
posted legs whose `created_at <= snapshot_at`. Therefore a leg exactly at the
snapshot boundary is represented by opening and is not replayed again. A leg
exactly at the old period's close boundary belongs to the old period and is
also part of the successor opening snapshot, never its replay window.

Changing `start_date` on a current period atomically recomputes `snapshot_at`
and `opening_balance` from the same ledger partition, then replays the new
window. It creates no movement and cannot change `current_balance`. A future
date, `end_date < start_date`, or a boundary that would cross an accepted
successor is rejected.

The previous requirement that a movement's financial date must itself lie
inside the planned date range is superseded for allowance calculation. Every
posted balance movement in the canonical timestamp window must affect the
period so that it cannot drift from the account balance. The transaction's
workspace-local financial date is still the preferred replay day; values
before `start_date` clamp to `start_date`, and values after the current replay
day clamp to that replay day. This clamping rule must also be used by the
Transactions period filter so the filter and allowance audit expose the same
movement set.

Closed-period snapshots remain historical facts. Closing a period must not
make the account ledger permanently uneditable. A later correction, Delete,
or Undo changes the live ledger balance according to normal transaction rules
but must not rewrite the stored opening or closing snapshots of a closed
period.

## 6. Balance and period amounts

The old independently funded amount and replayed `Remaining` value are
removed.

For a current period:

```text
current_balance = account posted ledger balance
```

Therefore:

- expense, fee, transfer/exchange out, and negative adjustment decrease it;
- income, transfer/exchange in, and positive adjustment increase it;
- correction, Delete, and Undo recompute it from posted signed legs;
- transfers and exchanges update each participating account independently;
- the period never drifts from the account balance.

The period API field is named exactly `current_balance`, not `remaining` or
`account_balance`. The account balance may also be obtained from the existing
Accounts API, but both responses must derive it through the same ledger
service and must agree exactly before API quantization.

### 6.1 Reconciliation input for pure budget math

An immutable opening snapshot alone is insufficient when a later correction,
Delete, or Undo changes a leg that existed before the period. The pure budget
calculation therefore receives an explicit derived reconciliation input.

For a current period at reference time `T`:

```text
window_net = exact sum of signed posted account legs in the canonical period
             window through T
reconciliation_delta = current_balance - (opening_balance + window_net)
calculation_opening_balance = opening_balance + reconciliation_delta
```

`reconciliation_delta` is computed on read and is not stored as a mutable
balance. It incorporates changes to pre-period ledger truth exactly once. The
pure replay treats it as an adjustment to the opening pool, then applies each
window movement once by effective financial day. This guarantees:

```text
calculation_opening_balance + window_net == current_balance
```

For a closed period, history uses the stored `opening_balance` and
`closing_balance` snapshots and never substitutes the live current account
balance. Closed history must not be recalculated from subsequently mutable
transaction rows.

## 7. Unused daily allowance policy

Each period has an explicit `rollover_policy`. The supported values are:

```text
carry_next_day
redistribute_remaining_days
```

The default is `redistribute_remaining_days`. Clients may explicitly select
either policy when creating or editing a current period.

For the formulas below:

```text
pool_start = calculation_opening_balance
net_day = exact sum of that day's signed balance effects
balance_after_day = pool_start + exact sum of net_day through that day
days_total = (end_date - start_date) + 1
```

A negative `net_day` is spending/outflow; a positive `net_day` is
income/inflow. Each signed effect is applied exactly once.

### 7.1 `carry_next_day`

The initial exact daily base is:

```text
daily_base = pool_start / days_total
carry = 0
```

For each completed day:

```text
available_end = daily_base + carry + net_day
```

When `available_end >= 0`, the next carry becomes the complete
`available_end`; `daily_base` stays unchanged. The amount is not divided among
all future days.

If it also remains unused on the next day, it continues accumulating forward.

Example with a base allowance of `100`:

```text
day 1: available 100, spent 60, unused 40
day 2: available 140
day 2 spent 0
day 3: available 240
```

This is the existing carry behavior in `app/budget.py`; it remains supported
but is no longer the default.

### 7.2 `redistribute_remaining_days`

At the start of each new workspace-local day, the exact start-of-day balance
is redistributed evenly across every day still remaining in the inclusive
period, including the new current day. No separate carry amount is added to
only the next day.

For a synchronous read during day `D`:

```text
today_net = exact sum of signed effects assigned to D
start_of_day_balance = current_balance - today_net
days_remaining = (end_date - D) + 1
daily_base = start_of_day_balance / days_remaining
available_today = daily_base + today_net
```

`current_balance` already contains `today_net`; subtracting it before division
and adding it once afterward prevents double counting. Replaying an earlier
day uses the corresponding balance before that day's effects in the same way.

Example:

```text
opening balance: 1,000
period length: 10 days
day 1 base: 100
day 1 spent: 60
balance after day 1: 940
days remaining: 9
day 2 base: 940 / 9 = 104.444...
```

The calculation retains exact Decimal precision internally. API presentation
rounds to the asset precision; rounding residue remains in the exact pool and
must not be silently lost. The final day exposes the complete exact balance
remaining after presentation quantization.

### 7.3 Shared behavior

For both policies:

- movements recorded during the current day change the account balance and
  today's available amount using their signed account-leg effect;
- underspending never creates or destroys money;
- under `carry_next_day`, if a completed day has `available_end < 0`, carry is
  reset to zero and the next exact `daily_base` becomes
  `balance_after_day / number_of_days_after_that_day`; repeated overspends
  repeat this rule from the newly rebased pool;
- under `redistribute_remaining_days`, every new day already performs that
  exact rebase, regardless of whether the preceding day was under or over;
- a negative account balance may produce a negative daily allowance and must
  not be coerced to zero;
- date boundaries use `Workspace.timezone`, not the server's local timezone;
- a one-day period never divides by zero;
- results are derived on read without persisting a mutable daily-balance
  aggregate.

The period policy replaces any public concept of an ad hoc user-triggered
`RebaseEvent`. A separate one-off rebase action is outside this revision unless
it is designed explicitly later.

## 8. Policy creation and editing

- Creating a period accepts optional `start_date`, required `end_date`, and
  optional `rollover_policy`.
- Omitting `rollover_policy` selects `redistribute_remaining_days`.
- Creating a period accepts an explicit workspace-local `start_date` that is
  not later than today; omitting it selects today.
- The backend derives `snapshot_at` and captures `opening_balance`; clients
  cannot submit or override either field.
- A current period's `start_date`, `end_date`, and `rollover_policy` may be
  changed by the owner. The response must immediately return values
  recalculated from the selected period start under the new policy.
- An ended or closed period is read-only.
- The update request accepts only `start_date`, `end_date`, and
  `rollover_policy`. It rejects `snapshot_at`, all balance snapshots, ownership
  fields, and removed fields.
- Changing policy affects allowance presentation only. It never creates a
  transaction or changes the ledger balance.

## 9. Required API semantics

The public routes remain under `/api/v1` and use this contract:

```text
POST  /accounts/{account_id}/periods
GET   /accounts/{account_id}/periods/current
GET   /accounts/{account_id}/periods?scope=history
GET   /account-periods/{period_id}
PATCH /account-periods/{period_id}
POST  /account-periods/{period_id}/close
```

Create request:

```json
{
  "start_date": "2026-08-08",
  "end_date": "2026-08-23",
  "rollover_policy": "redistribute_remaining_days"
}
```

The request must reject client-provided `snapshot_at`, `funding_amount`,
`opening_balance`, `closing_balance`, `current_balance`, `account_balance`, or
`planned` fields.

Current-period response:

The following dated fixture derives every displayed financial value in the
example. Workspace timezone is `Asia/Ho_Chi_Minh`; reference time is
2026-08-09 12:00 local; the inclusive end date is 2026-08-23, so 15 days
remain:

```text
opening_balance at 2026-08-08 boundary                    6,000,000 VND
2026-08-08 posted expense                                  -327,731 VND
start_of_day_balance on 2026-08-09                         5,672,269 VND
2026-08-09 posted income (today_net)                       +307,731 VND
current_balance                                             5,980,000 VND
daily_base = 5,672,269 / 15                       378,151.266666… VND
available_today exact = daily_base + 307,731      685,882.266666… VND
available_today API at VND precision                          685,882 VND
```

No planned item contributes to this fixture.

```json
{
  "id": 42,
  "account_id": 7,
  "start_date": "2026-08-08",
  "end_date": "2026-08-23",
  "snapshot_at": "2026-08-07T17:00:00Z",
  "opening_balance": "6000000",
  "current_balance": "5980000",
  "available_today": "685882",
  "rollover_policy": "redistribute_remaining_days",
  "status": "current",
  "created_at": "2026-08-08T08:00:00Z",
  "closed_at": null,
  "closing_balance": null
}
```

When no current period exists,
`GET /accounts/{account_id}/periods/current` returns HTTP `200` with JSON
`null`. It must not fabricate `0` or `N/A` financial values.

Update request:

```json
{
  "start_date": "2026-08-06",
  "end_date": "2026-08-31",
  "rollover_policy": "carry_next_day"
}
```

All three fields are optional, but at least one must be present. No generic
confirmation flag is part of this update because ended and closed periods are
read-only before an update is evaluated.

Closing the period returns the closed record with `closed_at` and
`closing_balance`. A subsequent create request for that account must be
accepted immediately, including on the same local date.

Period history remains available to the owner. Each history item returns only
historical facts:

```json
{
  "id": 41,
  "account_id": 7,
  "start_date": "2026-08-06",
  "end_date": "2026-08-22",
  "snapshot_at": "2026-08-05T17:00:00Z",
  "opening_balance": "6000000",
  "rollover_policy": "carry_next_day",
  "status": "closed",
  "created_at": "2026-08-06T08:00:00Z",
  "closed_at": "2026-08-08T08:00:00Z",
  "closing_balance": "5980000"
}
```

History does not expose live `current_balance`, `available_today`, `planned`,
or an independently replayed `remaining` value. An ended item uses the same
shape with `status=ended`, `closed_at=null`, and `closing_balance=null`. These
nulls explicitly mean that no immutable closing snapshot was taken; they must
not be filled from the later live account balance.

## 10. Plan separation

The Plan subsystem remains a separate source of expected future events.

- Period APIs do not query `PlanRule` or `PlanOccurrence`.
- Operations period responses do not expose `planned`.
- Planned events do not reserve account money, change account balance, or
  change `available_today`.
- A future concept such as required upcoming expenses must be designed
  separately with explicit sign and cash-flow semantics.

## 11. Permissions and privacy

- Only the account owner may create, read, edit, close, or list periods.
- A shared-account editor, contributor, or viewer may continue performing only
  the financial actions allowed by their account role, without learning
  whether a period exists.
- Generic transaction success/error responses must not reveal hidden period
  state to shared users.
- Every participating account in a transfer or exchange retains its existing
  permission checks.

## 12. Required acceptance scenarios

Implementation is not complete until automated tests cover at least:

1. An account with no period supports Spend, Add funds, Transfer, Exchange,
   correction, Delete, and Undo according to existing permissions.
2. Creating a period derives `snapshot_at` from Start date and predecessor
   boundaries and captures the exact ledger balance at that boundary as
   `opening_balance`; no funding field is accepted.
3. Active `current_balance` always equals the Accounts ledger balance after
   expense, income, transfer in/out, exchange, fee, adjustment, correction,
   Delete, and Undo.
4. Closing early captures exact `closing_balance` and permits a new period
   immediately even when the old planned end date is later.
5. Natural expiry produces an immutable ended record with null close fields,
   permits a successor, and cannot later be extended or closed using a
   successor-era balance.
6. Closing and reopening on the same local day never double-counts or drops a
   leg, including equality at either timestamp boundary.
7. A second simultaneous current period for the same account is rejected, and
   a predecessor cannot be extended across an existing successor.
8. Periods on different accounts remain independent.
9. `carry_next_day` carries the complete unused amount only to the following
   day and continues accumulating it when unused.
10. `redistribute_remaining_days` spreads the exact start-of-day balance over
    all remaining inclusive days and preserves rounding residue.
11. A midday income or expense under `redistribute_remaining_days` is applied
    exactly once.
12. Correction, Delete, or Undo of a pre-period leg produces the exact derived
    reconciliation delta and keeps `available_today` aligned with the live
    balance.
13. Backdated, future-dated, replacement, and boundary-equality legs follow the
    canonical timestamp window and effective-day clamping rules.
14. Overspend, repeated overspend, zero spend, income during a period,
    negative balances, one-day periods, timezone boundaries, and maximum
    supported asset precision are covered under both policies.
15. Omitting `rollover_policy` selects `redistribute_remaining_days`; explicitly
    selecting either policy is preserved on create and update.
16. Creating with a past date or today succeeds, a future Start date fails,
    and `end_date < start_date` fails.
17. Changing Start date on a current period atomically recomputes `snapshot_at`,
    opening snapshot, replay membership, and allowance without changing the
    live ledger balance; ended/closed periods reject it.
18. A selected past Start date reconstructs opening at the exact local-day
    boundary and replays every later posted leg exactly once, including
    same-day predecessor/successor boundary cases.
19. Spending above Available today remains accepted; the resulting allowance
    may be negative and never acts as an authorization or validation limit.
20. Changing `rollover_policy` recalculates allowance without creating a
    transaction or changing balance.
21. Closed-period snapshots remain immutable while later ledger corrections
    still affect the live account balance.
22. Current lookup always returns an object or HTTP `200` JSON `null`; history
    distinguishes a manually closed snapshot from a naturally ended record
    with null close fields.
23. Period and Operations responses contain no `funding_amount`, `remaining`,
    or `planned` contract fields from the old model.
24. Shared-account users cannot discover period existence or values.
25. `app/budget.py` remains pure and the implementation introduces no
    background infrastructure.

## 13. Explicitly deferred frontend work

This document does not prescribe component layout, mobile breakpoints, visual
hierarchy, bottom sheets, button placement, typography, or Figma structure.

The separate design handoff must nevertheless respect these backend truths:

- account balance always exists;
- a period is optional;
- `available_today` exists only for a current period;
- Funding and Planned are absent;
- the user selects one of the two rollover policies;
- closing permits starting another period immediately.
