# 07 · Data model

Enough structure to make the screens behave. Names are suggestions; the shapes are not.

## Account

```
id, name                     "Cash"
storage    cash | bank | card | crypto
purpose    spending | reserve | savings
asset      VND | USD | USDT
balance                      minor units + scale per asset
openingBalance               balance when the current period started
includeInAvailable  bool     the toggle in Add/Edit account
role       owner | editor | viewer
archived   bool
```

Row meta line is `storage · purpose` ("cash · spending"). The switcher meta line is
`asset · storage · purpose` ("VND · cash · spending").

## Spending period

```
id, accountId, startDate, endDate
openingBalance               snapshot at start
status     active | closed
```

One active period per account, at most. Closing writes the current balance into history
and makes the period read-only. Starting one snapshots the balance immediately.

`daysLeft` = whole days from today to `endDate`, inclusive, rendered as `15d`.

The backend supports both rollover policies. New periods default to
`redistribute_remaining_days`; the checked mobile checkbox selects it, while
unchecking selects `carry_next_day`. Available today is informational and does
not reject an expense when the value would be exceeded.

## Transaction

```
id, accountId, destinationAccountId?    (transfers only)
type       income | expense | transfer
amount, asset
financialDate                           the date that affects periods
category, note, createdBy
status     posted | planned | deleted
planItemId?                             set by Link transaction
```

Deleted transactions stay in history with a `Deleted` pill and stop affecting balances
and periods. Transfers create two visible movements and leave total capital unchanged.

## Category

`id, name, kind (income | expense)`. Deleting reassigns its transactions to
`Uncategorized`; merging moves them to the chosen category. Neither touches balances.

## Plan rule and plan item

```
rule:  id, kind (expectedIncome | requiredExpense), name, amount, asset,
       repeats (never | weekly | monthly | yearly), firstDue,
       accountId (destination for income, source for expense), required bool,
       active bool
item:  id, ruleId, dueDate, amount, status (planned | required | overdue | done),
       matchedTransactionId?
```

Plan never changes real balances. An item becomes `done` only when a transaction
is linked. Skip affects one occurrence only. Delete rule archives the rule:
linked transactions remain historical, while future items are no longer
generated or selectable.

## Exchange rate

`id, pair ("VND → USD"), source (manual), value`. Automatic daily rates are a
disabled `Coming soon` UI option and have no external integration in this phase.
An asset with no rate is excluded from Total capital and Available and renders as
`Not valued`; the Accounts banner counts those assets.

## Derived values

| Value | Rule |
|---|---|
| Total capital | Σ balances of non-archived accounts, converted; assets without a rate excluded |
| Available (Accounts) | Σ balances where `includeInAvailable`, converted |
| Available today | informational per-account allowance from the active period; may be exceeded |
| Filters badge | number of non-default filters |
| Open items / Completed | counts of plan items |
