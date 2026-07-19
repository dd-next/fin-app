# FinApp v2 — implementation build plan

Authoritative requirements are in
[`specs/FinnApp-v2.md`](specs/FinnApp-v2.md). This plan is deliberately
sequential: do not begin a later phase until the current phase is committed and
its `docs/PROGRESS.md` entry has all required evidence.

For every logical block, follow [`REVIEW_PROTOCOL-v2.md`](REVIEW_PROTOCOL-v2.md).
Each reviewer sub-agent is read-only and independent from the author of the
block. A phase commit is forbidden until its review findings are closed.

## Universal implementation rules

1. Inspect the current worktree before edits and preserve unrelated user
   changes.
2. Work in the stated block order: schema/migration → domain → API → UI →
   tests → docs. Split a block if this would hide unrelated behavior.
3. After each written block: targeted tests, a separate reviewer sub-agent,
   fixes, and re-review if findings changed logic/tests.
4. At phase end run complete `pytest`, `node --check app/static/app.js`,
   `git diff --check`, and the phase-specific checks below.
5. Update `docs/PROGRESS.md` with 2–4 concise work lines, exact commands and
   outcomes, reviewer task/findings/resolution, and decisions/assumptions.
6. Commit only the phase using `v2 phase N: <short summary>`.

## Phase 8 — Documentation and specification reset

Purpose: make the new release executable by future agents before product code
changes.

### Blocks

1. **Authority map** — create the active `docs/` package, relocate
   specifications to `docs/specs/`, and redirect AGENTS, CLAUDE, README, and
   root v2 compatibility pointers.
2. **Decision-complete specification** — document Main currency/rates,
   Operations/Undo, account periods, Transactions, Plan, reset, Docker, and
   acceptance invariants.
3. **Execution and acceptance material** — create this plan, the reviewer
   protocol, progress ledger, and manual test scenarios.

### Phase checks

- all active documentation links resolve;
- no active document claims Tracker/commitments or Plan Pay/Receive are the
  release target;
- `git diff --check` passes.

## Phase 9 — Clean release schema

Purpose: replace incompatible release storage safely and establish models that
make account-centric behavior possible.

### Blocks

1. **Backup and reset** — create timestamped `.backups/finapp-pre-v2-<UTC>.db`,
   SHA-256 it, verify it opens, restore it to a separate scratch path, verify
   the restored copy opens, record all proof, then replace only the local
   release database and Alembic history. Do not import old rows.
2. **Schema and migration** — add workspace-scoped manual valuation rates,
   `Transaction.origin`, immutable `TransactionLeg.created_at`, account-bound
   periods, and persisted Undo consumed/cursor state; remove
   `BudgetCommitment`, workspace-period associations, one-period transaction
   links, and frozen multi-asset period valuation.
3. **Schema-facing API/model cleanup** — remove unsupported legacy model/API
   references and seed the eight assets in a fresh schema.
4. **Migration regression tests** — prove clean upgrade, no legacy tables,
   seeded assets, backup safety evidence, and application startup.

### Phase checks

- backup and its separate scratch-restored copy both open; checksum and restore
  proof are recorded;
- fresh `alembic upgrade head` creates only release tables and eight assets;
- no runtime reference to `BudgetCommitment`, `budget_period_id`, or legacy
  workspace periods remains;
- complete suite and fresh-db startup pass.

## Phase 10 — Financial correctness

Purpose: make valuation and account-period replay correct before building UI.

### Blocks

1. **Rate isolation and manual precedence** — scope exchange rate lookup to
   workspace; add manual rate CRUD, reciprocal Decimal calculation, explicit
   fallback, and Main currency change handling.
2. **Money presentation** — centralize Main-currency quantization with
   `ROUND_HALF_UP`; preserve full stored Decimal precision.
3. **Account-period replay** — implement account-leg membership, snapshot
   boundary, signed movement replay, same-account overlap prevention, and
   cross-account overlap support in pure budget inputs.
4. **Mutation guards and permission tests** — enforce upcoming/current/ended/
   closed rules and owner-private period visibility.

### Phase checks

- two workspaces with conflicting exchange rates cannot affect one another;
- manual override → delete → exchange fallback → Unvalued is covered;
- `15,258,400 VND` at `1 USD = 26,292 VND` produces `580.34 USD`;
- same-account periods reject overlaps; different-account periods allow them;
- funding `900` remains `900` after a leg that predates period creation, while
  a later leg inside the date range is replayed;
- a correction cannot rewrite an existing leg's `created_at`; a replacement leg
  has its own timestamp and membership is tested against that timestamp;
- ended-period funding/date edits and correction/void require explicit
  confirmation; closed-period mutations remain rejected;
- all replay tests use Decimal values and no DB/framework import enters
  `app/budget.py`.

## Phase 11 — Operations and account periods UI

Purpose: replace Tracker with the action-first Operations experience.

### Blocks

1. **Navigation and selection state** — rename Tracker to Operations across
   SPA/API clients; account selector and local selector/account persistence;
   fixed selector order and no history list.
2. **Financial forms** — Spend, Add funds, same-asset Transfer, cross-asset
   exchange with optional fee, and Scan placeholder; all operate without a
   period.
3. **Period lifecycle and cards** — create/edit/close/history account periods,
   funding prefill, `N/A`/`Add period`, and Available today/Remaining/Planned.
4. **Persistent Undo** — selected-account candidate API, server-side creator
   scope, root/child soft void, consumed state, reload behavior, and UI.
5. **Responsive/accessibility tests** — phone/desktop controls, keyboard,
   focus, error/loading states, and English-only copy.

### Phase checks

- selector is `Spend → Add funds → Transfer → Scan` and first open is Spend;
- financial actions work with no period;
- new signed movements and transfer out/in change the right account periods;
- Undo appears in every selector, survives reload, disappears after use, and
  cannot select an older transaction for any account leg of the undone root;
- Operations displays no operation history and Scan says `Coming soon`.

## Phase 12 — Transactions and Plan

Purpose: align history and planning with Operations and account-period rules.

### Blocks

1. **Transactions history behavior** — remove add controls/routes, add Period
   filter and period-leg query, retain details/correction/assignment, and
   replace visible Void with confirmed `× Delete` soft void.
2. **Plan list/details design** — one rule card, nearest overdue plus nearest
   future date, overdue badge, compact selectors, and rule-details occurrence
   history.
3. **Link + Skip contract** — remove Pay/Receive UI/routes; validate semantic
   type, permit actual account/asset differences, return actual amount/asset,
   and retain idempotent recurrence.
4. **Privacy and regressions** — verify period filtering, linking, deletion
   replay, owner-private Plan/period data, and obsolete route absence.

### Phase checks

- Period filter includes qualifying expense, income, transfer, and exchange;
- `× Delete` recalculates balances/periods while the record remains `Deleted`;
- each rule card exposes only permitted occurrence summaries;
- Link works across asset/account only for the allowed semantic type;
- Pay/Receive routes and UI flows are absent.

## Phase 13 — Docker and release verification

Purpose: produce a reproducible, persistent single-container release.

### Blocks

1. **Container build** — non-root Python 3.12 image, minimal used
   dependencies, migration-before-Uvicorn command, and `/health` healthcheck.
2. **Compose persistence** — one app replica, `/data/finapp.db` persistent
   volume, safe environment configuration, no embedded TLS/reverse proxy.
3. **Operational documentation** — README install/run/migrate/test plus
   Docker build/start/backup/restore and data-persistence instructions.
4. **Release acceptance** — clean volume migration, restart persistence,
   browser acceptance at 480×900 and 1280×900, permissions, keyboard/focus,
   English UI, and no horizontal scroll.

### Phase checks

- `docker build -t finapp-v2 .` and `docker compose config` pass;
- fresh volume migrates and `/health` is healthy;
- created data remains after container restart;
- backup/restore instructions are executed successfully on a scratch volume;
- full suite, JS check, diff check, fresh migration, browser acceptance, and
  every specification acceptance criterion pass.

## Completion rule

Do not mark the release complete because an earlier prototype test suite passed.
Completion requires all Phase 8–13 checks, reviewer evidence for every logical
block, and the twelve acceptance criteria in `specs/FinnApp-v2.md`.
