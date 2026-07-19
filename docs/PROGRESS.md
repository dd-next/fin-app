# FinApp v2 — release progress ledger

This is the active progress file for the new FinApp v2 release. Read
[`specs/FinnApp-v2.md`](specs/FinnApp-v2.md),
[`BUILD_PLAN-v2.md`](BUILD_PLAN-v2.md), and
[`REVIEW_PROTOCOL-v2.md`](REVIEW_PROTOCOL-v2.md) before resuming work.

Status legend: `[ ]` not started · `[~]` in progress · `[x]` completed · `[!]` blocked

## Current release plan

- [x] Phase 8 — Documentation and specification reset
- [x] Phase 9 — Clean release schema
- [x] Phase 10 — Financial correctness
- [x] Phase 11 — Operations and account periods UI
- [x] Phase 12 — Transactions and Plan
- [~] Phase 13 — Docker and release verification

## Starting point — 2026-07-19

- The repository contains a prior Tracker/commitment prototype and its prior
  completion ledger. It is historical evidence only and does not meet this
  release's Operations/account-period/Plan requirements.
- This documentation package defines the new release boundary. No application
  code, migration, database, or runtime behavior is changed by this setup.
- Clarification locked for future implementation: ended-period funding/date
  edits and correction/soft void require explicit confirmation; a closed period
  remains read-only. Phase 10 must test this distinction.
- Before Phase 9, create and verify a timestamped backup of local `finapp.db`.
  Record its path, SHA-256 checksum, and open/restore verification here.

## Phase log

### Phase 8 — Documentation and specification reset (2026-07-19)

- Status: [x]
- Completed: consolidated all active documents under `docs/`, with active and
  historical specifications under `docs/specs/`; root v2 files are
  compatibility pointers and root `specs/` is removed. Defined Main currency,
  Operations/Undo, account periods, revised Transactions/Plan, clean reset,
  Docker delivery, manual acceptance, and the mandatory review protocol.
- Reviewer blocks: authority map → `phase8_authority_review` → APPROVED with no
  findings; specification → `phase8_spec_review` → two P1 findings (ended
  confirmation and exchange neutrality) fixed → `phase8_spec_rereview`
  APPROVED; execution/acceptance → `phase8_execution_review` → restore-proof,
  coverage, fresh-path, and Docker-command findings fixed →
  `phase8_execution_rereview` APPROVED with no unresolved P0–P2.
- Tests: `env -u DATABASE_URL PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m
  pytest -p no:cacheprovider -q` — **81 passed in 7.87s**;
  `node --check app/static/app.js` — passed; `PYTHONDONTWRITEBYTECODE=1
  .venv/bin/python -m compileall -q app tests` — passed; `.venv/bin/pip check`
  — no broken requirements; `git diff --check` — passed.
- Checks: active document targets exist, root `specs/` is absent, no stale
  pre-relocation active paths remain, and the documentation authority map is
  internally consistent.
- Decisions / assumptions: ended-period funding/date edits and financial
  correction/soft void require confirmation; closed periods are read-only.
  Only same-asset internal transfers are required to stay neutral to Total
  capital; cross-asset exchange valuation follows active rates.
- Blocker: none.

### Phase 9 — Clean release schema (2026-07-19)

- Status: [x]
- Completed: created and independently restored the timestamped legacy backup;
  replaced the five-revision prototype history with clean head
  `0001_release_v2`; introduced workspace/manual rates, workspace exchange
  rates, strict `Transaction.origin`, immutable leg timestamps,
  account-specific periods, and persisted Operations Undo state. Removed
  Tracker/commitment/frozen-valuation models, routes, clients, and obsolete
  Plan Pay/Receive; seeded exactly eight release assets and created a clean
  runtime `finapp.db` with zero users.
- Reviewer blocks: backup/reset → `phase9_backup_review` → APPROVED, no P0–P3;
  schema/migration → `phase9_schema_review` → P1 unrestricted origin fixed
  with DB constraint → `phase9_schema_rereview` APPROVED; runtime cleanup →
  `phase9_runtime_cleanup_review` → APPROVED; legacy SPA clients →
  `phase9_legacy_client_review` → P3 stale wording fixed; migration/regression
  tests → `phase9_regression_review` → three P2 coverage gaps fixed →
  `phase9_regression_rereview` APPROVED with all P2 closed.
- Tests: `env -u DATABASE_URL PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m
  pytest -p no:cacheprovider -q` — **66 passed**; targeted Phase 9 regression
  set — **18 passed in 2.15s**; `node --check app/static/app.js` — passed;
  `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m compileall -q app tests` —
  passed; `.venv/bin/pip check` — no broken requirements; `env -u DATABASE_URL
  .venv/bin/alembic check` — no new upgrade operations; `git diff --check` —
  passed.
- Checks: backup SHA-256
  `f2441becb810355345dce10370c6c96a8a8373a416f383dc65f96baaa74b748a`;
  source `.backups/finapp-pre-v2-20260719T035114Z.db` and byte-identical
  scratch restore at
  `/private/tmp/finapp-phase9-restore-20260719T035114Z.db` both report
  `PRAGMA integrity_check` — `ok`, legacy head `0005_v2`, 3 users, and 25
  financial transactions. Fresh migration and runtime DB pass integrity at
  `0001_release_v2`, contain the exact release tables/assets and no users;
  application lifespan and `/health` pass; OpenAPI contains no Tracker,
  commitment, Pay, or Receive routes.
- Decisions / assumptions: retained both the SQLite online backup and exact
  original file for recoverability; Git history retains the removed migration
  chain. The Operations placeholder is intentionally transitional and is
  replaced by the functional Phase 11 surface.
- Blocker: none.

### Phase 10 — Financial correctness (2026-07-19)

- Status: [x]
- Completed: manual valuation rates are workspace/Main-pair scoped with manual
  precedence, posted direct-rate fallback, Main-switch isolation, and no
  multi-hop; Main-currency presentation now rounds once with `ROUND_HALF_UP`
  while exact high-precision Decimal arithmetic is preserved through ledger,
  sign, valuation, reconciliation, and aggregate paths.
  Account-specific periods now provide owner-only create/list/read/edit/close,
  snapshot-bound signed replay, Plan cards, lifecycle confirmation, and closed
  record guards across all financial mutation paths.
- Reviewer blocks: rate isolation/manual precedence →
  `phase10_valuation_review` → P2 missing isolation/latest/void/multi-hop/CRUD
  regressions fixed → `phase10_valuation_rereview` APPROVED; money presentation
  → `phase10_money_presentation_review` → P1 ambient Decimal-context truncation
  and P2 weak precision fixture fixed → `phase10_money_presentation_rereview` →
  P1 unary sign truncation fixed → `phase10_money_presentation_final_review`
  APPROVED; account-period replay → `phase10_period_replay_review` → P2
  movement/Plan matrix gaps fixed → `phase10_period_replay_rereview` → P2
  ambiguous Plan-status assertion fixed → `phase10_period_replay_final_review`
  APPROVED; mutation guards/privacy → `phase10_period_guards_review` → P2
  guard-path/privacy matrix gaps fixed → stalled
  `phase10_period_guards_rereview` stopped without accepting a result →
  `phase10_period_guards_final_review` → four residual P2 rollback/permission
  gaps fixed → `phase10_period_guards_closure_review` APPROVED with no P0–P3.
  Phase commit gate → `phase10_commit_gate_review` → APPROVED with no P0–P3
  and no unrelated changes.
- Tests: valuation block targeted suite — **9 passed in 1.62s**; `env -u
  DATABASE_URL PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p
  no:cacheprovider -q tests/test_valuation_v2.py
  tests/test_phase9_ledger_integrity_v2.py tests/test_ledger_v2.py
  tests/test_plan_v2.py` — **24 passed in 3.41s**; compileall,
  `node --check app/static/app.js`, and `git diff --check` — passed; period,
  budget, ledger, and Plan targeted suite — **41 passed in 2.60s**; mutation
  guard targeted suite — **50 passed in 4.55s**; final period suite — **12
  passed in 1.89s**; `env -u DATABASE_URL PYTHONDONTWRITEBYTECODE=1
  .venv/bin/python -m pytest -p no:cacheprovider -q` — **86 passed in 7.59s**;
  `.venv/bin/python -m compileall -q app tests`, `node --check
  app/static/app.js`, `.venv/bin/pip check`, and `git diff --check` — passed.
- Checks: conflicting workspaces, manual delete fallback, void fallback,
  Unvalued/no-multi-hop, shared-account valuation isolation, VND regression,
  maximum 38-digit crypto plus smallest unit, direct-rate multiplication,
  aggregate-before-rounding, and exact outgoing sign are covered.
  Snapshot funding, strict leg timestamp membership, same-account overlap,
  cross-account transfer/exchange replay, fee/root void, all signed movement
  types, and open/in-range/account-bound Planned selection are also covered.
  `env -u DATABASE_URL .venv/bin/alembic check` reports no new upgrade
  operations; the phase gate independently passed 20 valuation/period tests,
  OpenAPI boundary, `/health`, budget purity, no-float, and diff checks.
- Decisions / assumptions: calculation helpers use an explicit high-precision
  Decimal context or context-free sign operations; API quantization remains a
  separate final presentation step.
- Blocker: none.

### Phase 11 — Operations and account periods UI (2026-07-19)

- Status: [x]
- Completed: added the persistent per-user Operations account/action selector
  with the exact Spend, Add funds, Transfer, Scan order, keyboard tab behavior,
  safe account fallback, and a no-OCR Scan placeholder. Added action-first
  Spend/Add funds/Transfer/Exchange forms backed by `/api/v1/operations`, with
  category/date/note/fee handling, same-workspace role filtering, generic
  ended-period confirmation, and explicit `operations` origin while legacy
  transaction routes retain `manual` origin. Added owner-private selected
  account period cards and create/edit/close/history UI with ledger-balance
  funding prefill, N/A/Add period behavior, persistent load errors/Retry,
  stale-response rejection, and asset-precision money display. Added
  server-persistent creator/account-scoped Undo with atomic operation cursor
  creation, optimistic candidate claiming, root/fee soft void, multi-leg
  consumption, no older fallback, later-candidate preservation, and a
  reload-safe compact UI control.
  Transaction correction, unassignment, and assignment now reindex the
  creator's Undo cursor atomically: current root accounts advance while every
  removed account is consumed without overwriting a later candidate.
  Completed responsive/accessibility hardening with 44px targets, two-column
  phone selector, roving keyboard focus, labelled alerts/status/busy regions,
  persistent load errors, and guarded non-idempotent financial/period commands
  that cannot be double-submitted.
- Reviewer blocks: navigation/selection → `phase11_navigation_review` →
  APPROVED with no P0–P3; financial forms →
  `phase11_financial_forms_review` → P0 owner-private period disclosure and P2
  client validation/permission-origin coverage gaps fixed →
  `phase11_financial_forms_rereview` APPROVED; period lifecycle/cards →
  `phase11_period_ui_review` → P2 same-account response race/loading-error
  ambiguity and P3 confirmation copy fixed → `phase11_period_ui_rereview` → P1
  missing asset-precision padding fixed → final closure pass APPROVED with no
  P0–P3; Persistent Undo → initial reused review found P1 stale cross-tab
  candidate and fixed it with required expected transaction ID/conditional
  cursor claim; pre-commit review then found P1 correction/assignment cursor
  drift and the missing fresh-review pass → cursor reindex fixed → fresh
  `/root/phase11_financial_forms_review/phase11_undo_fresh_review` APPROVED
  with no P0–P3. Responsive/accessibility/browser → initial reused review
  found P1 missing in-flight guards/accessibly busy states and fixed them →
  fresh `/root/phase11_navigation_review/phase11_accessibility_fresh_review`
  APPROVED with no P0–P3. Final pre-commit review → fresh
  `/root/phase11_navigation_review/phase11_commit_gate_fresh_review` →
  APPROVED with no P0–P3; the complete Phase 11 diff was commit-ready.
- Tests: navigation targeted suite — **4 passed**; financial forms targeted
  suite — **27 passed in 3.03s**; post-review privacy, role, period, manual
  origin, and frontend suite — **24 passed in 3.33s**; independent re-review —
  **29 passed**; period UI targeted suite — **22 passed in 2.86s**; independent
  period closure suite — **17 passed in 1.94s**; `node --check
  app/static/app.js` and `git diff --check` — passed after all three completed
  blocks. Undo targeted suite — **37 passed in 4.50s**; independent Undo
  closure suite — **41 passed**; compileall, OpenAPI GET/POST Undo generation,
  `node --check app/static/app.js`, and `git diff --check` — passed. Final
  frontend/Operations/Undo/period targeted suite — **30 passed in 4.53s**;
  independent accessibility closure suite — **33 passed in 4.68s**; JavaScript
  syntax, diff, and forbidden-copy scan passed. Phase gate `env -u DATABASE_URL
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider -q`
  — **102 passed in 11.01s**; `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m
  compileall -q app tests`, `.venv/bin/pip check`, `node --check
  app/static/app.js`, and `git diff --check` — passed/no broken requirements;
  `env -u DATABASE_URL .venv/bin/alembic check` — no new upgrade operations.
  Post-fix Undo correction/assignment targeted suite — **34 passed in
  6.24s**; fresh accessibility reviewer — **35 independent tests** plus
  OpenAPI, JavaScript, diff, and forbidden-copy/history audits passed. The
  fresh final reviewer independently ran the full suite — **102 passed in
  11.36s** — plus JavaScript, compileall, pip, diff, existing/fresh-schema
  Alembic, database integrity/eight-asset seed, and 47-path OpenAPI boundary
  checks; all passed.
- Checks: no Operations history or Tracker/commitment residue; invalid or
  unavailable local storage does not break navigation; shared-user mutation
  responses preserve generic period wording and hidden accounts return 404.
  Shared accounts make no period API call; request generations prevent stale
  A→B→A and same-account responses from replacing newer period state.
  Undo guards rejected ended/closed changes without consuming state; repeated
  candidate reads, stale-tab rejection, multi-account consume, root/fee void,
  creator separation, role downgrade, and later-cursor preservation are
  covered.
  Correction destination replacement, removed-account consumption,
  unassignment, reassignment, and post-correction Undo/no-fallback are covered.
  Scratch browser verification used migrated DB
  `/private/tmp/finapp-phase11.igfb2w/verify.db` and `/health` returned 200.
  At 1440×900 the body/view had no overflow; at 480×900 body width remained
  480px, the selector rendered as two 219.5px columns, and selector/submit
  controls were 44px. Real UI checks covered funding prefill/replacement,
  N/A/current cards, validation alert, keyboard ArrowRight/End focus,
  Spend/Add funds/Transfer, candidate reload/Undo, both transfer accounts,
  period history, Scan/Coming soon, desktop/phone screenshots, and an empty
  browser error log. The temporary viewport was reset and browser session
  closed.
- Decisions / assumptions: Operations confirmation copy is intentionally
  generic for every account so the browser cannot disclose owner-private
  period state.
- Blocker: none.

### Phase 12 — Transactions and Plan (2026-07-19)

- Status: [x]
- Completed: Block 1 aligns Transactions with its history-only boundary:
  removed public transaction-creation routes and SPA controls; creation now
  occurs through Operations only. Added the owner-private Period filter with
  strict posted-leg snapshot/date membership for expense, income, transfer,
  and exchange. Replaced the public Void contract with confirmed compact
  `× Delete`, external `Deleted` status/`deleted_at`, and global Deleted
  history while deleted movements no longer belong to periods. Retained
  assignment and correction, and added read-only/redacted details for every
  visible record. Account/Period filters synchronize, and Delete has a
  duplicate-submit guard, disabled controls, and `aria-busy` state.
- Completed: Block 2 replaces the global Plan occurrence lists with one card
  per rule. Each card shows at most the overdue occurrence closest to today
  (with an `N overdue` badge when several are overdue) and the nearest future
  occurrence; completed, skipped, remaining overdue, and other future
  occurrences moved to a per-rule details dialog with a compact
  all/open/completed/skipped `Show` filter. The old `Upcoming income` and
  global future lists, `plan-status-filter`, and the separate rules section
  are removed; compact Open/Completed counters stay, and the open details
  dialog re-renders after every data refresh.
- Completed: Block 3 aligns Link with its semantic contract: Link validates
  semantic type only (income→income, expense kinds→expense,
  reserve_transfer→transfer) and accepts different actual accounts and assets;
  the rule-asset equality check is removed on both server and SPA. Linked
  responses now return `actual_amount` plus new `actual_asset`, and the SPA
  formats actuals with the actual asset. Foreign transactions are
  indistinguishable from missing ones on both link routes (identical 404
  status and detail, before and after occurrence resolution), and recurrence
  materialization stays untouched and idempotent.
- Completed: Block 4 adds cross-cutting privacy/regression coverage in
  `tests/test_phase12_privacy_v2.py`: deleting a linked transfer replays both
  affected account periods and reopens the occurrence with cleared actual
  amount/asset; linking never moves a transaction between periods; a shared
  account editor sees the transaction but receives 404 on every Plan surface
  (reads, skip, link routes) with the redacted detail; OpenAPI exposes exactly
  `skip`/`link-transaction` occurrence actions and
  `delete`/`assign-account`/`link-plan` transaction actions, with no Pay,
  Receive, Void, Tracker, or creation routes.
- Reviewer blocks: Transactions history behavior → fresh
  `/root/phase11_navigation_review/phase12_transactions_review` → P1 deleted
  period membership and inaccessible read-only details, plus P2 conflicting
  filters, Delete re-entry, and boundary/privacy coverage gaps → all fixed →
  re-review APPROVED with no P0–P3. Pre-commit fresh reviewer
  `phase12_block1_commit_review` independently re-verified the complete
  Block 1 diff (boundary, privacy, delete replay, UI guards, OpenAPI, full
  suite, JS check) → APPROVED with no P0–P3. Plan list/details design → fresh
  `phase12_plan_cards_review` verified card boundary (nearest overdue latest
  date, nearest future earliest date), badge, details-only history,
  stale-dialog refresh, removed-id/XSS/accessibility checks → APPROVED with no
  P0–P3 (one non-blocking P3 observation on label/badge redundancy recorded).
  Link + Skip contract → fresh `phase12_link_contract_review` → P2
  reverse-route foreign-transaction 404-detail oracle and two P3 coverage gaps
  (already-linked 409 branch, reverse-route detail equality) → fixed →
  `phase12_link_contract_rereview` APPROVED with one residual P3
  resolved-occurrence oracle → occurrence workspace check reordered before
  `require_open_occurrence` with resolved foreign/missing equality test →
  `phase12_link_contract_final_review` APPROVED with no findings. Privacy and
  regressions → fresh `phase12_privacy_regressions_review` traced deletion
  replay, occurrence reopen, membership stability, shared-editor Plan
  blindness, and the OpenAPI whitelist against app code, and confirmed the
  combined Phase 12 suites satisfy every build-plan phase check → APPROVED
  with no P0–P2 (two non-blocking P3 notes recorded, no change required).
  Phase commit gate → fresh `phase12_commit_gate_review` independently re-ran
  the full gate commands, verified the combined `92d685f..HEAD` diff contains
  only Phase 12 work, confirmed all five build-plan phase checks are
  code/test-evidenced, and validated this ledger entry against reality →
  APPROVED (commit-ready) with one P3 dead `AdjustmentIn` schema → removed
  (its only consumer, the adjustment creation route, left in Block 1); full
  suite re-run green after removal.
- Tests: initial Block 1 targeted suite — **42 passed in 6.50s**; post-review
  expanded Transactions/ledger/Operations/Undo/period/frontend/sharing suite —
  **46 passed in 7.25s**; reviewer independent expanded suite — **63 passed in
  10.17s**. `node --check app/static/app.js`, compileall, OpenAPI boundary, and
  `git diff --check` passed. Block 2 targeted suite
  (`tests/test_frontend_v2.py tests/test_plan_v2.py`) — **11 passed in
  0.87s**; full suite after Block 2 — **106 passed in 12.20s**; reviewer
  independently re-ran frontend tests, `node --check`, and `git diff --check`
  — passed. Block 3 targeted suite (`tests/test_plan_v2.py
  tests/test_frontend_v2.py`) — **13 passed in 1.24s**; post-fix
  `tests/test_plan_v2.py` — **6 passed in 1.23s**; full suite after Block 3 —
  **108 passed in 11.61s**; both re-reviewers independently re-ran the plan
  suite and full suite — passed; `node --check app/static/app.js` and
  `git diff --check` — passed. Block 4 targeted suite
  (`tests/test_phase12_privacy_v2.py`) — **3 passed in 0.74s**; full suite
  after Block 4 — **111 passed in 12.17s**; reviewer independently re-ran the
  Block 4 suite — **3 passed in 0.77s**. Phase gate: `env -u DATABASE_URL
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider -q`
  — **111 passed in 11.73s**; `node --check app/static/app.js`,
  `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m compileall -q app tests`,
  `.venv/bin/pip check`, and `git diff --check` — passed/no broken
  requirements; `env -u DATABASE_URL .venv/bin/alembic check` — no new upgrade
  operations.
- Checks: scratch-database browser verification used migrated DB
  `phase12/verify.db` (fresh `alembic upgrade head` to `0001_release_v2`);
  `/health` returned `{"status":"ok"}`. Real UI checks at desktop and ~721px
  widths covered: one card per rule with nearest overdue (latest overdue date)
  plus `2 overdue` badge and nearest future occurrence; Show details dialog
  with full history and all/open/completed/skipped filter; Link dialog
  end-to-end (occurrence preselected, eligible transaction listed, submit) —
  Completed counter moved 0→1, the card re-rendered with the remaining single
  overdue row and no badge, and the completed occurrence showed
  `Planned 500.00 USD · actual 450.00 USD`; browser console had no errors.
  OpenAPI has 42 paths; Transactions exposes list, detail/correction,
  assignment, and Delete only. Legacy creation and Void paths/copy are absent;
  the public status enum is `posted|unassigned|deleted`. Tests cover pre-period,
  out-of-range, exact timestamp boundary, shared/foreign period privacy, all
  required financial types, soft-delete replay, and global Deleted history.
- Decisions / assumptions: `voided` and `voided_at` remain internal persistence
  names only; the active public contract uses `deleted` and `deleted_at`.
- Blocker: none.

### Phase 13 — Docker and release verification (2026-07-19)

- Status: [~]
- Completed: Block 1 adds the single-container release image. `Dockerfile`
  builds a non-root (`uid 10001 finapp`) `python:3.12-slim` container, installs
  only runtime dependencies, copies just `alembic.ini`, `alembic/`, and `app/`,
  sets `DATABASE_URL=sqlite+aiosqlite:////data/finapp.db`, owns `/data` for the
  volume, declares `VOLUME ["/data"]`, uses a `/health` urllib HEALTHCHECK, and
  runs `alembic upgrade head && exec uvicorn ...` so migration failure blocks
  startup. Test-only dependencies (`pytest`, `pytest-asyncio`, `httpx`) moved
  from `requirements.txt` to a new `requirements-dev.txt` that includes
  `-r requirements.txt`; `.dockerignore` keeps the database, backups, venv,
  git, tests, and docs out of the build context.
- Reviewer blocks: container build → fresh `phase13_container_build_review`
  verified non-root/3.12, minimal-used-deps (every requirement imported by
  `app/` or alembic), migration-before-uvicorn with failure blocking startup,
  `/health` healthcheck semantics, `/data` volume ownership, and
  `.dockerignore`/COPY scope → APPROVED with no findings.
- Tests: `docker build -t finapp-v2 .` — succeeded; fresh named-volume
  `docker run` — migration reached `0001_release_v2`, `/health` returned
  `{"status":"ok"}`, container healthcheck `healthy`, `id`=`uid 10001(finapp)`,
  `/data/finapp.db` owned by `finapp`; unwritable-`DATABASE_URL` run —
  `state=exited exit=1` with alembic `OperationalError`, uvicorn never started;
  host `env -u DATABASE_URL PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest
  -p no:cacheprovider -q` — **111 passed in 13.21s**; `.venv/bin/pip check` —
  no broken requirements.
- Checks: image runs as the non-root `finapp` user; migration precedes Uvicorn
  and its failure prevents startup; `/health` is the healthcheck; SQLite is at
  `/data/finapp.db` on a persistent volume.
- Decisions / assumptions: `COOKIE_SECURE` stays unset in the image because the
  container serves plain HTTP and TLS/reverse proxy are external per spec §11.
- Completed: Block 2 adds `compose.yaml` with a single `app` service
  (`deploy.replicas: 1`), a named `finapp-data` volume mounted at `/data`,
  `DATABASE_URL=sqlite+aiosqlite:////data/finapp.db`, an overridable
  `COOKIE_SECURE` defaulting to `false`, `restart: unless-stopped`, a `/health`
  healthcheck, and no TLS/reverse-proxy or extra services.
- Reviewer blocks: compose persistence → fresh
  `phase13_compose_persistence_review` verified one replica, absolute-path
  named-volume storage, safe overridable env, absence of forbidden services,
  and that the DB cannot land on an anonymous volume or image layer → APPROVED
  with no findings.
- Tests: `docker compose config` — renders one `app` service, replicas 1, named
  volume `finapp-data`→`/data`, correct `DATABASE_URL`/`COOKIE_SECURE`,
  healthcheck present; `docker compose up -d` on a clean volume — container
  reached `healthy`, `/health` returned `{"status":"ok"}`; registered a user,
  `docker compose restart`, then login returned HTTP 200 → data persisted
  across restart; `docker compose down` removed container/network but retained
  volume `fin_app_finapp-data`.
- Checks: exactly one replica; SQLite persists on the named volume at
  `/data/finapp.db`; fresh volume migrates and `/health` is healthy; created
  data survives a container restart; no embedded TLS/reverse proxy.
- Decisions / assumptions: host port `8000` is published for an external TLS
  terminator; the compose healthcheck intentionally mirrors the image's.
- Completed: Block 3 rewrites `README.md` as release documentation: a product
  summary, local install/run/migrate/test with the runtime vs
  `requirements-dev.txt` split, and a Docker section covering build, Compose
  start/status/stop, persistent-volume behavior, and executable backup and
  restore procedures. Restore was corrected to remove SQLite sidecar files,
  copy the backup, and `chown 10001:10001` so the non-root app can write; a
  note explains the `fin_app_` volume prefix. Stale prototype/"being reset"
  wording is removed.
- Reviewer blocks: operational documentation → fresh
  `phase13_readme_review` verified every command/claim against the repo, the
  requirements split, Compose semantics, backup/restore soundness, the restore
  ownership fix (UID 10001, sidecar coverage), and removal of prototype
  wording → APPROVED with one P3 volume-name-prefix note → closed by adding the
  project-name/volume-prefix explanation to the README.
- Tests: executed the README backup and restore procedures verbatim on the live
  Compose stack — backup produced a 356352-byte file
  (SHA-256 `4be17264e9f35c458983ce930889c9d0e3c424a81285049861decc3cf946e0c4`);
  added a post-backup user, ran restore, and confirmed the post-backup user was
  rolled back (login `401`) while the pre-backup user logged in `200` and could
  write (`auth_session` INSERT succeeded), proving correct ownership after the
  `chown` fix.
- Checks: README documents install, run, migrate, test, Docker build/start,
  persistent-volume behavior, backup, and restore; a container restart and a
  down/up cycle preserve data (Block 2 evidence); backup/restore verified on a
  scratch volume.
- Decisions / assumptions: backup/restore use `busybox` with the full volume
  name `fin_app_finapp-data`; the restore must re-own `finapp.db` to UID 10001.
- Blocker: none.

## Required phase-entry template

Copy this structure for every phase. Do not mark a phase complete without every
line being evidenced.

```md
### Phase N — <name> (YYYY-MM-DD)

- Status: [~] / [x] / [!]
- Completed: <2–4 concise implementation facts>
- Reviewer blocks: <block → reviewer task name → findings → resolution>
- Tests: `<exact command>` — <exact pass/fail result>
- Checks: <migration/browser/Docker/link/diff evidence required by the phase>
- Decisions / assumptions: <only decisions not already specified>
- Blocker (if any): <cause and attempted fixes>
```

## Historical note

Git history preserves the earlier root-level implementation ledger. The current
root-level `PROGRESS.md` is only a compatibility pointer and must not be used to
skip the phases above.
