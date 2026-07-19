# FinApp v2 — manual acceptance scenarios

These scenarios validate the release specified in
[`FinnApp-v2.md`](FinnApp-v2.md). The application UI must be English; the
instructions are Russian for the implementation/review team.

Use a scratch database or Docker volume. Never use the working `finapp.db` for
manual test data.

## Preparation

```sh
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
FINAPP_MANUAL_DIR="$(mktemp -d)"
export DATABASE_URL="sqlite+aiosqlite:///$FINAPP_MANUAL_DIR/finapp-v2-manual.db"
alembic upgrade head
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000` in two isolated browser sessions when a scenario
uses two workspaces or account sharing.

## MT-01 — Main currency, manual rates, and workspace isolation

1. Create workspace A with Main currency USD and an account holding
   `15,258,400 VND`.
2. In `Financial settings`, save `1 USD = 26,292 VND` as a manual rate.
3. Check Total capital, Available, and the account valued balance.
4. Change Main currency to EUR and verify the saved USD/VND rate is inactive;
   change Main currency back to USD and verify the rate is active again.
5. Delete the manual rate. Create an exchange in A that supplies the same
   direct USD/VND pair, then check fallback.
6. Void that exchange and check that VND becomes `Unvalued`.
7. In workspace B create a conflicting USD/VND exchange rate and verify that
   workspace A does not change.

Expected: A shows `580.34 USD`, values use two USD decimals and `ROUND_HALF_UP`;
manual rate wins, deletion falls back only to A's exchange, and B's rate never
leaks into A. Changing Main currency never silently converts a saved pair.

## MT-02 — Operations selector and period-free financial actions

1. Open `Operations` with no period on the selected account.
2. Verify the selector order `Spend`, `Add funds`, `Transfer`, `Scan` and that
   first open selects `Spend`.
3. Create an expense through `Spend`, income through `Add funds`, a same-asset
   transfer, and a cross-asset exchange with optional fee.
4. Switch selectors/accounts, reload, and verify local selector/account
   restoration. Open `Scan`.
5. Confirm that Operations contains no recent-operation list.

Expected: all financial actions post correctly without a period; Scan shows
`Coming soon`; inaccessible/archived remembered accounts safely fall back.

## MT-03 — Account-specific periods and signed replay

1. Create Account A and Account B with the same asset, plus Account C with a
   different asset. Create overlapping periods for A, B, and C.
2. Try to create an overlapping period for A.
3. Before creating a period for A, post an expense; create the period with
   funding `900` and verify that prior expense is not replayed again.
4. Post an expense, income, negative/positive adjustment, a same-asset transfer
   A → B, and a cross-asset exchange A → C after the periods exist.
5. Correct a qualifying transaction and verify its existing leg timestamp is
   not rewritten; if correction replaces a leg, verify the replacement has its
   own timestamp and membership is recalculated from it.
6. Inspect `Available today`, `Remaining`, and `Planned`; then void a
   qualifying transaction.
7. Let one period end: verify funding/date edits and correction/void require
   explicit confirmation and succeed after it. Close another and test
   read-only behavior.

Expected: A and B can overlap, A cannot overlap itself; funding starts at 900;
post-snapshot signed legs update only their account periods; transfer lowers A
and raises B without changing Total capital; exchange lowers A and raises C,
while its valued Total capital follows the active valuation rates. Ended changes
require confirmation; closed period is immutable; no record uses a single
period link; corrections cannot forge a historical leg timestamp to change
period membership.

## MT-04 — Persistent selected-account Undo

1. Through Operations, create a root expense on Account A and inspect `Undo`
   from each selector.
2. Reload the page and verify the same Undo candidate remains.
3. Trigger Undo and check ledger history, balances, and relevant periods.
4. Verify Undo disappears rather than selecting an older operation.
5. Create an Operations transfer A → B, Undo it from A, then inspect B and
   verify that it also cannot fall back to an older candidate.
6. In a second user session, create an Operations transaction on a shared
   account. In the first session verify that transaction ID is never returned
   as the first user's Undo candidate.
7. Create a new Operations transaction as the first user and verify it becomes
   the only new candidate. Test an account created by another user and a
   transaction not created through Operations.

Expected: only the latest eligible root transaction by the current user for
the selected account is undoable; Undo soft-voids it and related fee child;
creator/account boundaries, all legs of an undone root, and reload behavior are
server-enforced.

## MT-05 — Transactions period filter and Delete

1. Create qualifying expense, income, transfer, and exchange legs after a
   selected account period begins.
2. Open `Transactions`, choose `Period`, and inspect label
   `Account · dates · status` and returned records.
3. Verify there is no `Add transaction` action.
4. Open details, correct and assign a transaction, then use `×` with tooltip
   `Delete`.
5. Confirm the delete dialog and filter status to show the deleted record.

Expected: filter uses account-leg/snapshot membership, including transfers and
exchanges; Delete preserves history as `Deleted` but recalculates balances and
periods; UI does not present legacy `Void` as the primary action.

## MT-06 — Plan cards, Link, and Skip

1. Create recurring income, expense, and reserve-transfer rules with several
   past and future occurrences.
2. On the main Plan view inspect each rule card and its details.
3. Attempt to find Pay/Receive controls or routes.
4. Link a posted income to an income occurrence using a different asset/account;
   repeat with a posted expense for an expense rule and transfer for reserve.
5. Attempt a semantic mismatch; skip another occurrence; inspect actual amount
   and actual asset after link.

Expected: one card per rule shows at most nearest overdue plus nearest future,
with overdue badge; all other occurrence history is in details; only Link/Skip
exist; cross-asset/account link works only for the correct semantic type.

## MT-07 — Sharing and private boundaries

1. Share an account with editor, contributor, and viewer sessions.
2. In each session test Operations actions permitted by that role.
3. Try IDs and filters for the owner's manual rates, periods, Plan rules,
   occurrences, totals, and other accounts.
4. Create a multi-account transfer where one account is inaccessible.

Expected: account permissions remain intact; owner-private rates/periods/Plan
and totals are not disclosed; inaccessible legs are redacted as appropriate;
multi-account mutations require rights to every account.

## MT-08 — Responsive and accessibility release pass

At `480×900` and `1280×900`:

1. Navigate Accounts, Transactions, Operations, Plan, and Analytics.
2. Use Operations forms, period dialogs, Delete confirmation, Plan Link/Skip,
   and Financial settings with keyboard only.
3. Inspect visible focus, labels, errors, loading state, tap targets, and
   horizontal overflow.
4. Check browser console and visible copy.

Expected: no horizontal scroll, primary touch controls are at least 44 px,
focus/dialog behavior works, console is clean, and all UI copy is English.

## MT-09 — Fresh schema and Docker persistence

1. Run fresh Alembic migration on a scratch SQLite URL and confirm the eight
   seeded assets and no legacy commitment/workspace-period tables.
2. Run `docker build -t finapp-v2 .` and validate `docker compose config`.
3. Start the Compose stack, check `/health`, create test data, restart the app,
   and verify data persists.
4. Follow README backup/restore instructions on a scratch volume.

Expected: migration and app startup are clean, only one app replica runs,
SQLite uses `/data/finapp.db`, `/health` is healthy, data survives restart, and
the documented restore succeeds.

## Automated release commands

```sh
.venv/bin/python -m pytest -q
node --check app/static/app.js
git diff --check
FINAPP_FRESH_DIR="$(mktemp -d)"
DATABASE_URL="sqlite+aiosqlite:///$FINAPP_FRESH_DIR/finapp-v2-fresh.db" alembic upgrade head
```

Phase 13 additionally runs the Docker commands and records exact outcomes in
`docs/PROGRESS.md`.
