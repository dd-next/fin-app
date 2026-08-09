# Mobile design ↔ backend contract audit

Status: **accepted planning input, implementation pending** · 2026-08-09

This audit compares the final mobile source screen and written handoff with
the shipped backend and the proposed account-period v2.1 contract. It does not
edit the exported source geometry; later owner-approved behavioral corrections
are recorded in the written specs and `DESIGN-NOTES.md`. Every backend gap is routed to Phase 14 in
[`BACKLOG.md`](../BACKLOG.md); the mobile UI starts only in Phase 15.

## Authority used for the audit

1. `Finnapp mobile specification/Finapp Screen.dc.html` — final source screen,
   geometry, visible states, and interactions.
2. `Finnapp mobile specification/spec/01-foundations.md` through
   `08-acceptance.md`, `tokens.css`, and `design-tokens.json` — written and
   machine-readable handoff.
3. `Finnapp mobile specification/handoff/finapp-design-canvas.html` — portable
   overview of the same screen and state catalogue.

`Finapp Mobile Redesign.dc.html` is an overview canvas that imports the source
screen; it is not the implementation source. The other `.dc.html` files,
standalone duplicates, `.thumbnail`, and `uploads/` are raw material, not
acceptance authority.

## Required Phase 14 backend changes

| Area | Mobile design requires | Current backend / proposed spec | Required backend change | Task |
|---|---|---|---|---|
| Period source of money | Opening balance is captured from the account; current balance is live; no editable Funding or Remaining | Shipped API stores and accepts `funding_amount`, replays `remaining`, and exposes `planned` | Replace the model and contract with immutable opening/closing snapshots and ledger-derived current balance; remove legacy period money fields | T-002–T-010 |
| Allowance example | The reference shows opening `6,000,000`, current `5,980,000`, 15 days left, and Available today `685,882` | Accepted v2.1 now derives the value from a dated VND ledger fixture under `redistribute_remaining_days`; shipped backend has no matching regression | Implement the exact fixture in budget/API tests so every displayed value and `ROUND_HALF_UP` result is reproduced without hard-coded UI constants | T-005, T-006, T-021 |
| Rollover selection | Owner correction adds a Start/Edit checkbox, checked for `redistribute_remaining_days` and unchecked for `carry_next_day` | Backend/proposed spec supports both policies but previously defaulted to carry | Accept policy on create/update and default omitted values to `redistribute_remaining_days`; expose both through the existing period API | T-008 |
| Period start date | Start date is an interactive field on both Start period and Edit period | Accepted v2.1 contract now permits past/today on create and current-period PATCH, with explicit snapshot/replay semantics; shipped backend still fixes/locks it | Implement the accepted contract: reject future dates, recompute snapshot, membership, reconciliation input, and successor conflicts atomically. Scheduled future periods remain unsupported | T-007 |
| Available today | Owner correction defines it as informational; spending above it remains valid and may produce a negative/recalculated allowance | Backend/proposed period behavior already permits overspend and repeated overspend | Preserve the permissive write contract; remove the older mobile over-limit validation and add regression coverage that the allowance never acts as an authorization limit | T-008, T-027 |
| Automatic rates | Owner defers all external integrations; `Auto` remains a disabled `Coming soon` option | Backend already supports manual workspace rates | No Phase 14 integration. Preserve manual rates and expose only the mobile pair-direction correction; Phase 15 renders the disabled placeholder | T-012, T-025 |
| Rate direction | Pair choices are asset → Main currency, for example VND → USD and USDT → USD | Manual-rate input is `1 Main currency = X Asset`, the opposite displayed direction | Accept and return the mobile pair direction while storing an exact reciprocal where needed; never round through float | T-012 |
| Cross-asset Transfer | Transfer has one source amount and one destination selector, including accounts in another asset | Backend requires explicit From amount and To amount for a cross-asset exchange | Add quote/execute semantics that derive the destination amount from the selected rate source, bind execution to the quoted rate, and preserve exact signed legs and valuation invariants | T-013 |
| Planned ledger rows | Transactions has a real Planned filter and Planned rows mixed into its date-grouped feed; tapping any row opens Transaction details | Transactions exposes only persisted financial transactions; Plan occurrences are a separate API and must not affect balances | Add a discriminated feed projection that unions visible transactions with open Plan occurrences without creating fake ledger rows. A planned row uses the specified Transaction-details route with a discriminated planned detail/action payload; it is never silently redirected to Plan | T-014 |
| Feed ordering | Date groups and rows follow financial date | Transaction pagination orders by transaction id, so a corrected financial date can appear in the wrong group/order | Use a stable `(local_date, occurred_at/id)` cursor and prove correction, deletion, planned projection, and pagination ordering | T-014 |
| Adjustment/exchange rows | Mobile filters expose Income, Expense, Transfer, and Planned, while real opening/reconciliation adjustments and exchanges still appear in All | Backend has first-class `adjustment` and `exchange` types and richer desktop filters | Define stable mobile row/type/detail mapping: adjustments remain identifiable non-convertible balance corrections; exchanges render as transfer-like rows without losing their two-amount detail. Preserve richer desktop filters | T-014, T-015 |
| Transaction type edit | Edit transaction includes an editable Type field | `TransactionPatch` cannot change transaction type | Support validated type conversion by replacing signed legs atomically, rechecking permissions/period impact/category semantics, and preserving audit history | T-015 |
| Category merge/delete | Edit category exposes Merge into another and Delete; delete moves history to Uncategorized | Backend can rename/archive only; active and archived Plan rules also reference categories restrictively | Add merge and delete/archive-as-Uncategorized commands for transactions and Plan rules, usage counts, idempotency, workspace isolation, historical-link preservation, and regression proof that ledger amounts never change | T-016 |
| Account restoration | Archive confirmation promises that the account can be restored later | Backend archives accounts but has no restore command | Add owner-only restore with uniqueness handling; restored accounts re-enter totals according to their rates and `include_in_available` | T-017 |
| Owner role | Owner remains visible in the role picker as disabled `Coming soon` | Backend cannot safely transfer ownership across workspace-scoped data | No Phase 14 change and no blocker for the redesign; defer ownership architecture/implementation until after Phase 15 | T-025, Icebox |
| Plan rule shape | Mobile uses a dynamic account label and adds Skip beside Edit rule/Link transaction; Delete rule archives the rule | Backend has five kinds, source/destination fields, occurrence Skip, and rule archival | Define kind mapping, map Expected income account to destination and expense account to source, keep Skip occurrence-scoped, and guarantee archival retains linked transactions while disabling future selection/generation | T-019 |
| Logout | Owner correction removes the local-data/invite-only statement; logout is a normal server session action | Backend already revokes the session and supports username/password re-entry | No backend change. Phase 15 uses truthful server-side logout confirmation copy | T-025 |

## Already supported by the backend

These design requirements need frontend composition in Phase 15, not new
backend semantics:

- account creation with an opening ledger adjustment, storage/purpose, asset,
  institution, and `include_in_available`;
- ledger-derived account balances, Total capital, Available, and explicit
  unvalued assets;
- account reconciliation as a posted adjustment;
- account-scoped transaction history, date/account/period/type/category
  filters, details, corrections, assignment, and soft Delete;
- same-asset transfers, explicit cross-asset exchanges, optional exchange fees,
  and creator-scoped persistent Undo;
- owner-private periods and Plan, subject to the Phase 14 period rewrite;
- Plan occurrence materialization, linking, Skip, and non-financial behavior;
  mobile rule creation/editing still requires the T-019 adapter contract;
- account invitation links and existing Viewer/Editor/Contributor permissions;
  Owner remains a disabled mobile placeholder until post-redesign work;
- workspace/manual-rate CRUD, authentication, logout, and workspace settings.

## Backend capabilities the mobile design does not show

The backend may remain a superset. Preserve these for desktop until a desktop
design explicitly replaces them:

- Operations Undo;
- explicit exchange amounts and optional fee;
- Contributor access role;
- unassigned transaction assignment;
- Plan Skip and full occurrence history;
- investment/e-wallet/exchange/virtual account variants;
- transaction adjustment/exchange filters and full status details. Their mobile
  `All`-feed representation is still required by T-014/T-015.

Omission from the 390×844 screen is not permission to delete an existing
desktop or public API capability.

## Frontend-only Phase 15 work

No backend change is implied by the exact 390×844 geometry, safe areas,
mobile tab bar, no-scroll budgets, bottom sheets, branded confirmations,
custom picker presentation, keyboard mock state, motion, typography, target
sizes, empty states, or English copy. Phase 15 implements those requirements
while retaining the working desktop layout where no desktop specification
exists.

## Design-source inconsistencies that must not become hidden assumptions

- The source screen includes an old history fixture reading
  `closed · funding 3,500,000`, while the written handoff and v2.1 contract
  remove Funding. Treat that row as raw legacy fixture data; no public Funding
  field is reintroduced.
- The exported source still contains the older over-limit error state and omits
  the rollover checkbox. The owner-approved written correction controls Phase
  15: Available today is informational and Start/Edit period exposes the
  policy checkbox without otherwise changing geometry.
- The design uses `active|closed` presentation while the backend needs to
  distinguish current, naturally ended, and manually closed records. The
  mobile adapter may map both historical backend states to visible `closed`;
  the richer backend history is retained.
- The design labels Plan occurrence states as `planned|required|overdue|done`;
  the existing API uses `planned|completed|skipped|overdue` plus
  `rule.is_required`. The mobile adapter derives the visible labels without
  changing ledger or Plan semantics.

## Exit condition

Phase 14 is not complete until every row marked as a required backend change
has an accepted task result or an explicit owner-approved exception recorded
in an ADR. Phase 15 must not compensate for a missing backend contract with
hard-coded financial values or fake local state.
