# 06 · Content

All UI copy is English. These strings are final — do not paraphrase them in code.

## Voice

Say what happened to the user's money and what changes. Never explain the interface,
never apologise, never use exclamation marks, never use emoji. Sentence case everywhere
except kickers (uppercase) and group headers (uppercase).

## Navigation

Accounts · Transactions · Operations · Plan · Analytics

## Accounts

- `Total capital` · `Available`
- `2 assets have no rate — set one`
- Groups: `CASH` · `BANK` · `CRYPTO`; counts `1 account` / `2 accounts`
- Row sub-values: `Not valued` · `protected`
- `New account`
- Empty: `Add your first account` / `Cash, cards, wallets, reserves, and crypto all live here.` / `Add account`

## Transactions

- Chips: `All` `Income` `Expense` `Transfer` `Planned`
- `Filters`; status pills `Planned` `Deleted`; swipe `Plan` `Delete`
- Empty: `No transactions yet` / `Create financial events from Operations — they appear here.` / `Open Operations`

## Operations

- Segments: `Spend` `Add funds` `Transfer` `Scan`
- Card labels: `Balance` · `Available today` · `Period · 15d` · `No period` · `+ Start period`
- Fields: `Choose destination` · `Note (optional)`
- Submit: `Save spending` / `Add funds` / `Save transfer`
- Available today is informational; there is no over-limit error.
- Scan: `Coming soon` / `Scan is reserved for a later release. No OCR is performed.`
- Keyboard accessory: `Amount` / `Note` · `Done`

## Plan

- `Open items` · `Completed` · `UPCOMING` / `next 30 days` · `RULES` / `1 active`
- Pills: `planned` `required` `overdue`
- Empty: `Plan what comes next` / `Expected income, required expenses, subscriptions. Plan never changes real balances.` / `Add rule`
- Plan item actions: `Edit rule` · `Skip` · `Link transaction`
- Account field: `To account` for Expected income; `From account` for expense kinds.

## Settings and Profile

- Rate source: `Manual value`; disabled option `Auto · Coming soon`.
- Share role: disabled option `Owner · Coming soon`.
- Logout: `You will be signed out on this device. Your data stays safely in your workspace.`

## Analytics

- `Coming soon` / `Income, spending, and trends arrive once the core ledger is stable.`

## Hints (13/400, `#5F6875`)

- Start period — `Your current account balance will be used to calculate the daily allowance.`
- Edit period — `The daily allowance is recalculated from the account balance at the moment the period started.`
- Reconcile — `A correction entry is written to history. Existing transactions are untouched.`
- Edit transaction — `Editing rewrites the movement. Balances and the active period are recalculated on save.`
- Add category — `A category only groups transactions. Renaming it later keeps every past entry attached.`
- Plan item — `Plan items never change real balances until a transaction is linked.`
- Link transaction — `Only eligible posted transactions are shown.`
- Set a rate — `Rates apply to Total capital and Available. Without a rate an asset shows as Not valued.`

## Saved confirmations

- Spend — `The expense was written to Cash · VND. Available today was recalculated.`
- Add funds — `The funds were added to Cash · VND. Balance and Available today were recalculated.`
- Transfer — `The transfer was recorded. Both accounts were updated — total capital is unchanged.`

The account name and currency are interpolated from the selected account.

## Number formatting

- VND: thousands separated by commas, no decimals — `5,980,000`
- USD: two decimals — `1,250.00`
- USDT: six decimals — `1,400.000000`
- Signed amounts in the feed carry `+` or the minus sign `−` (U+2212), coloured
  positive / negative; transfers use `±` and stay neutral.
- Currency code is a separate 11/500 muted suffix, never part of the number.
