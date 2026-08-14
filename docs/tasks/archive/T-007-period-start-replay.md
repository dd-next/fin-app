---
id: T-007
title: Implement atomic period Start-date snapshot replay
status: done
size: M
spec: specs/ACCOUNT_PERIODS-v2.1.md §3, §5, §8; design/MOBILE-BACKEND-GAP-AUDIT.md period start date
blocked-by: [T-002, T-003, T-004]
branch: task/T-007-period-start-replay
base-commit: 1f48429689412f61737fbda5afcfbd78d05d6d23
implementer: Codex
readiness-reviewed-by: /root/t007_readiness_final (Codex same-vendor fallback)
readiness-reviewed-commit: 568d7e1
readiness-verdict: ready
---

## Goal

An owner can select a past-or-today Start date when creating a period or
editing a current period, and every edit atomically rebuilds the exact opening
snapshot and replay partition without changing the posted ledger balance.

## Acceptance

- [x] Creating with an explicit workspace-local Start date in the past or on
      today succeeds, while a future Start date and `end_date < start_date`
      fail before any period row is persisted. The existing create path keeps
      deriving `snapshot_at` and exact `opening_balance`; T-008 owns making an
      omitted Start date default to today. Create also rejects without a row
      when the derived `snapshot_at` is at or after the first workspace-local
      instant following the inclusive `end_date`.
- [x] PATCH evaluates lifecycle state before applying the update: a period
      that is current at the start of the serialized operation may change
      `start_date` alone or together with `end_date`; an already ended or
      manually closed period remains read-only. A selected future Start date,
      null field, or resulting `end_date < start_date` is rejected
      deterministically and leaves every stored period field unchanged.
- [x] A current period may atomically move to a valid resulting-ended range.
      That response uses the strict `< first local instant after end_date`
      ended replay cutoff, the stored row is immediately read-only afterward,
      a leg exactly at the end boundary is excluded, and the account may then
      accept a successor under the T-004 rules. The edit does not invent
      `closed_at` or `closing_balance`.
- [x] A successful Start-date change recomputes `snapshot_at` as the exact
      maximum of the new workspace-local day boundary and every eligible
      predecessor boundary. Eligibility is evaluated at the serialized
      workspace-local today: same account, edited target excluded, and either
      manually closed (`closed_at IS NOT NULL`) or naturally ended
      (`closed_at IS NULL AND end_date < today`). The predecessor boundary is
      `closed_at` for manual close or the first workspace-local instant after
      its inclusive `end_date`; the maximum boundary is selected across all
      such rows. `opening_balance` is then recomputed from posted legs with
      `created_at <= snapshot_at`, using `Decimal` only.
- [x] The canonical window must remain chronological: create and PATCH reject
      atomically with HTTP `422` detail `Period snapshot must precede end
      boundary` when derived `snapshot_at >= period_end_boundary`, where
      `period_end_boundary` is the first workspace-local instant after the
      selected inclusive `end_date`. Equality is rejected because an ended
      window excludes the equality leg while opening would otherwise absorb
      it; a later predecessor boundary is rejected for the same reason. The
      target period and complete ledger remain byte-for-byte unchanged.
- [x] The edit atomically persists the selected dates, recomputed
      `snapshot_at`, and recomputed `opening_balance`. SQLite reserves the
      writer before reading lifecycle state, predecessors, ledger snapshot, or
      successor eligibility; any validation or replay failure rolls back the
      complete update.
- [x] Replaying the new canonical window changes no `Transaction` or
      `TransactionLeg`, creates no movement, and leaves the exact live account
      balance unchanged. For a resulting-current period, `period_movements`
      includes every later posted leg exactly once, excludes legs at the
      snapshot boundary, and `current_period_balance_inputs` still reconciles
      opening plus window to that unchanged live balance. A resulting-ended
      period instead uses its strict historical cutoff and is never passed to
      the current-only reconciliation input.
- [x] Backward and forward Start-date moves cover pre-boundary corrections and
      posted/voided legs without double counting. A leg exactly at the new
      snapshot boundary is represented in opening only; a later leg is replayed
      only; 18-place Decimal values remain exact.
- [x] A same-local-day manually closed predecessor remains the effective
      boundary when later than the selected local-day boundary. Changing the
      successor Start date cannot cross or absorb that accepted predecessor
      window, and the equality leg at the close boundary remains in successor
      opening but outside successor replay.
- [x] Successor/current-period eligibility is checked in the same serialized
      transaction. The endpoint reserves the writer before loading the target,
      so a stale PATCH that waits behind an operation which ended/closed that
      target and accepted a successor must re-read lifecycle state, return
      `409`, and leave both periods and every ledger row unchanged. A PATCH
      that serializes first has the deterministic resulting-current or
      resulting-ended behavior above and never creates a second current row.
- [x] Original date-range overlap with distinct closed/ended history is allowed
      for both Start-date and end-date-only edits, superseding the old all-row
      `ensure_no_overlap` behavior when the resulting canonical window remains
      chronological. A distinct same-account current row is a `409` conflict;
      invalid snapshot chronology returns the `422` above; different accounts
      remain independent.
- [x] Existing valid end-date-only PATCH behavior remains compatible except for
      the explicitly superseded all-history overlap rejection. The obsolete
      legacy assertion that every Start-date change returns `409` is replaced
      only where the accepted v2.1 contract supersedes it.
- [x] Focused tests cover create past/today/future and invalid range; backward,
      forward, and simultaneous Start/end edits; already ended/closed rejection;
      exact timezone and same-day predecessor boundaries; exact ledger and
      replay/reconciliation invariants; rollback; resulting-ended strict cutoff,
      subsequent immutability, and successor creation; historical overlap;
      predecessor equality-at-end and later-than-end mutation-neutral rejection;
      stale-PATCH/successor serialization; different accounts; and no row or
      ledger mutation on rejected input.

## Touches

- `app/periods.py`
- `tests/test_period_start_replay_v2.py`
- `tests/test_periods_v2.py` only for assertions directly superseded by Start
  date replay
- `docs/tasks/T-007-period-start-replay.md`
- `docs/BACKLOG.md` and `docs/PROGRESS.md` for task lifecycle state only

## Out of scope

- Public request/response schema replacement, omitted-Start default wiring,
  `rollover_policy` create/update exposure, allowance dispatch, current/history
  route contract, and lifecycle response cleanup — T-008.
- Removal of `funding_amount`, `remaining`, `planned`, RebaseEvent, and legacy
  confirmation fields — T-009.
- Shared-account owner-private permission redesign — T-010.
- Models, migrations, ledger-operation semantics, UI, Phase 15, or any change
  to stored closed/ended snapshots.

## Verification

```bash
.venv/bin/python -m pytest tests/test_period_start_replay_v2.py -q
.venv/bin/python -m pytest tests/test_periods_v2.py tests/test_period_lifecycle_v2.py -q
.venv/bin/python -m pytest -q
node --check app/static/app.js
git diff --check
git status --short
```

Ordinary database-backed tests use the isolated in-memory fixture. The
serialization test must use a `tmp_path` file-backed SQLite database with the
normal pool and separate request-scoped sessions, matching the accepted T-004
concurrency fixture. It deterministically interleaves an accepted target
lifecycle transition/successor with a waiting stale PATCH and asserts exact
statuses, one persisted current row, unchanged rejected-target fields, and
unchanged ledger rows. Any migration or manual database check must set an
explicit scratch `DATABASE_URL`; `finapp.db` is never used.

## Readiness review

Append-only readiness passes against `specs/ACCOUNT_PERIODS-v2.1.md` §3,
§5, §8 and acceptance scenarios 2, 6–7, 12–13, 16–18; the Period Start
date audit row; ADR-0005; T-002–T-004 accepted contracts; AGENTS; BACKLOG; and
REVIEW_PROTOCOL.

### Pass 1

- Reviewer task name/vendor: `/root/t007_readiness_review`, Codex same-vendor
  fallback; cross-vendor reviewer unavailable in this session.
- Reviewed task-file commit: `4d7c332`.
- Findings (verbatim, P0–P3):

  > Read-only readiness review of commit `4d7c332839c0ece7f8a240d6a6e6d7d29e05d071`.
  >
  > P0: None.
  >
  > P1 — Resulting-ended edits are not defined consistently. Acceptance allows a period that is current at the start of the serialized PATCH to change `end_date` together with `start_date`, rejecting only future Start, nulls, and `end_date < start_date` (`docs/tasks/T-007-period-start-replay.md:29-34`). Therefore a valid edit may move `end_date` before workspace today and make the period ended. But the replay invariant is then stated unconditionally through `current_period_balance_inputs` and live-balance reconciliation (`docs/tasks/T-007-period-start-replay.md:45-50`), although the accepted T-003 contract and §6.1 define that input only for a current period, while an ended period uses the strict `< period_end_boundary` historical window. “Existing end-date-only PATCH behavior remains compatible” (`docs/tasks/T-007-period-start-replay.md:65-67`) also leaves this transition implicitly allowed. Before readiness, specify that such an edit either (preferably, consistent with §8) succeeds atomically, returns an ended/read-only period, uses strict ended replay cutoff, and permits a successor, or is explicitly rejected. Add focused tests for the chosen result, subsequent immutability, boundary equality, and successor eligibility.
  >
  > P1 — Successor-conflict semantics can currently pass vacuously and conflict with the historical-overlap requirement. The task says an “accepted distinct same-account current successor” must not be crossed (`docs/tasks/T-007-period-start-replay.md:60-64`), but the edited target must itself be current at the serialized lifecycle read (`docs/tasks/T-007-period-start-replay.md:29-31`); under the accepted one-current-period invariant, those rows cannot coexist through a valid sequential API history. Define the observable serialized race/order instead: for example, a stale PATCH that began before another operation ended/closed the target and accepted a successor must reserve the writer, re-read the target and competing rows, reject without mutation, and never revive the predecessor beside the successor; conversely, a PATCH that serializes first has deterministic resulting-current or resulting-ended behavior. Also clarify that original date-range overlap with closed/ended history is allowed for both Start-date and end-date-only edits, superseding the current all-row `ensure_no_overlap` behavior at `app/periods.py:615-621`; otherwise “existing behavior remains compatible” can preserve the obsolete historical-overlap rejection contrary to `docs/tasks/T-007-period-start-replay.md:61` and §5 lines 129–136.
  >
  > P2 — The predecessor set is not precise enough for a financial-boundary operation. “Every eligible same-account closed/naturally-ended predecessor” (`docs/tasks/T-007-period-start-replay.md:35-39`) does not define eligibility at the serialized workspace date or distinguish a predecessor from a later accepted row. State the exact query invariant inherited from T-004: same account, target excluded, manually closed (`closed_at != null`) or naturally ended at the serialized workspace-local today (`closed_at == null` and `end_date < today`), with boundary `closed_at` or first local instant after `end_date`, and select the maximum against the selected Start boundary. This makes multiple-history, same-day, and successor-conflict fixtures objectively reviewable.
  >
  > P2 — The required SQLite serialization has no adequate verification path. The task requires `BEGIN IMMEDIATE`-equivalent reservation before lifecycle, predecessor, ledger, and successor reads (`docs/tasks/T-007-period-start-replay.md:40-44`), but its focused list names only generic “successor conflict” (`docs/tasks/T-007-period-start-replay.md:68-72`) and then says all DB-backed tests use the in-memory fixture (`docs/tasks/T-007-period-start-replay.md:105`). The standard fixture uses one `StaticPool` in-memory connection (`tests/conftest.py:19-23`) and cannot prove multi-connection writer serialization. Require a `tmp_path` file-backed SQLite fixture with separate request sessions, like the accepted T-004 concurrency fixture, and an interleaved PATCH/successor test asserting deterministic statuses, one current row, unchanged rejected target fields, and unchanged ledger rows.
  >
  > P3: None.
  >
  > The T-008/T-009 boundary is otherwise sound: omitted-Start schema wiring, policy exposure/dispatch, final public response shape, and removed legacy fields remain explicitly deferred without blocking T-007’s internal replay work. Dependencies T-002–T-004 are accepted; scope remains M. `git diff --check 4d7c332^ 4d7c332` passed. No tests were needed for this documentation-only review. No files were edited and no branch was switched.
  >
  > Verdict: **NOT READY**.
- Resolution: acceptance now defines resulting-ended replay/immutability and
  successor behavior; replaces the vacuous successor bullet with an observable
  serialized stale-PATCH ordering; explicitly permits historical overlap;
  defines the exact predecessor query; and requires a file-backed multi-session
  concurrency fixture. All P1–P2 findings are addressed in the task contract.
- Verdict: not ready; re-review required after the documentation changes.

### Pass 2

- Reviewer task name/vendor: `/root/t007_readiness_rereview`, Codex same-vendor
  fallback; cross-vendor reviewer unavailable in this session.
- Reviewed task-file commit: `adb9236`.
- Findings (verbatim, P0–P3):

  > Read-only readiness re-review of commit `adb923666450b6f6a19fd9451a110d7421b854b5`.
  >
  > P0: None.
  >
  > P1 — Resulting-ended replay is still ambiguous when an eligible predecessor boundary is at or after the edited period’s resulting end boundary. The task requires `snapshot_at` to be the maximum of the selected Start boundary and every eligible predecessor boundary (`docs/tasks/T-007-period-start-replay.md:41-50`), permits a current period to become ended (`docs/tasks/T-007-period-start-replay.md:35-40`), and broadly permits historical overlap (`docs/tasks/T-007-period-start-replay.md:80-83`). In an accepted API history, a same-day successor can therefore be edited backward so its latest predecessor closed after the first local instant following the selected `end_date`. The required result would store `opening_balance` from a timestamp later than the strict ended replay cutoff, making the canonical window empty or chronologically inverted while still calling the range “valid.” The same ambiguity exists for create because past Start/range success is stated without a predecessor-boundary qualification (`docs/tasks/T-007-period-start-replay.md:24-28`). Before readiness, define whether `snapshot_at >= period_end_boundary` is rejected atomically (the safer interpretation of “cannot cross or absorb” at lines 68–72) or explicitly accepted with coherent historical semantics, and require a focused same-account predecessor fixture covering equality and later-than-end boundaries plus mutation-neutral rejection if rejected.
  >
  > P2: None.
  >
  > P3: None.
  >
  > The prior findings are otherwise closed:
  >
  > - resulting-ended strict cutoff, subsequent read-only state, null close fields, and successor eligibility are explicit;
  > - stale PATCH ordering now requires writer reservation before target load, lifecycle re-read, `409`, and no mutation;
  > - historical overlap behavior explicitly supersedes the old all-row guard for Start- and end-only edits;
  > - predecessor eligibility and boundary selection are exact;
  > - file-backed SQLite verification requires normal pooling, separate request sessions, deterministic interleaving, and persisted-state/ledger assertions.
  >
  > T-008/T-009 boundaries remain sound, dependencies are accepted, and the task remains feasible at size M after resolving the boundary chronology. `git diff --check 4d7c332 adb9236` passed. No tests were needed for this documentation-only review. No files were edited and no branch was switched; HEAD remained `adb9236` on `finapp-v2-develop`.
  >
  > Verdict: **NOT READY**.
- Resolution: create and PATCH now reject `snapshot_at >=
  period_end_boundary` atomically; equality and later-than-end predecessor
  fixtures must prove period/ledger mutation neutrality.
- Verdict: not ready; final readiness re-review required.

### Pass 3

- Reviewer task name/vendor: `/root/t007_readiness_final`, Codex same-vendor
  fallback; cross-vendor reviewer unavailable in this session.
- Reviewed task-file commit: `568d7e1`.
- Findings (verbatim, P0–P3):

  > Read-only final readiness re-review of commit `568d7e1b72a0317220f2f81bb075b1f817743323`.
  >
  > P0: None.
  >
  > P1: None.
  >
  > P2: None.
  >
  > P3: None.
  >
  > The Pass-2 P1 is closed. Create and PATCH now deterministically reject derived `snapshot_at >= period_end_boundary` with HTTP `422` detail `Period snapshot must precede end boundary`. Equality and later-than-end predecessor cases are explicitly required as mutation-neutral fixtures covering the target period and complete ledger.
  >
  > Earlier findings remain closed:
  >
  > - resulting-ended edits have strict historical cutoff, immediate immutability, null close snapshots, and successor eligibility;
  > - predecessor eligibility and maximum-boundary selection are exact;
  > - stale PATCH ordering requires writer reservation before target loading and lifecycle re-read;
  > - historical overlap is allowed only when the canonical window remains chronological;
  > - the obsolete all-history overlap guard is explicitly superseded;
  > - the concurrency gate requires a `tmp_path` file-backed SQLite database, normal pooling, separate request-scoped sessions, deterministic interleaving, exact statuses, one current row, and persisted period/ledger invariants.
  >
  > The scope remains feasible at size M. T-008 correctly retains omitted-Start schema wiring, rollover-policy exposure, allowance/API response synchronization, and lifecycle surface work. T-009 retains removal of legacy funding/remaining/planned contracts. Dependencies T-002–T-004 are accepted.
  >
  > `git diff --check adb9236 568d7e1` passed. No tests were required for this documentation-only readiness review.
  >
  > No files were edited and no branch was switched; HEAD remained `568d7e1` on `finapp-v2-develop`.
  >
  > Verdict: **READY**.
- Resolution: no further changes required; every readiness P0–P2 is closed.
- Verdict: ready.

## Review

Append-only implementation review passes. A different read-only agent returns
the review; the implementer records it verbatim following
[`../REVIEW_PROTOCOL-v2.md`](../../REVIEW_PROTOCOL-v2.md).

### Pass 1

- Reviewer task name/vendor: `/root/t007_start_replay_review`, Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed base/head or working-tree manifest: base/HEAD `e573478`; modified
  `app/periods.py`, directly inspected untracked
  `tests/test_period_start_replay_v2.py`, and modified
  `tests/test_periods_v2.py`.
- Findings (verbatim, P0–P3):

  > Read-only implementation review of base/HEAD `e573478` with manifest `M app/periods.py; M tests/test_periods_v2.py; ?? tests/test_period_start_replay_v2.py` (untracked file inspected directly).
  >
  > P0: None.
  >
  > P1: None.
  >
  > P2 — The focused suite does not cover several explicit T-007 acceptance branches, so regressions in the new guard paths can pass. `tests/test_period_start_replay_v2.py` has only six tests and never sends a future `start_date` to a still-current target, never sends `start_date: null`, never proves an end-date-only edit may overlap closed/ended history, and never exercises `ensure_no_other_current_period` with a distinct same-account current row or proves PATCH independence for another account. The legacy future-PATCH assertions at `tests/test_periods_v2.py:891-905` run only after that target was changed to `ended`, so they receive lifecycle `409` rather than testing the new future-date `422`; the stale test at `tests/test_period_start_replay_v2.py:430-500` likewise rejects a now-closed target before the distinct-current guard. These are required by `docs/tasks/T-007-period-start-replay.md` acceptance bullets 2, 10-11, and 13. Add focused mutation-neutral assertions for current-target future/null rejection, end-only historical overlap success, and same-account distinct-current/different-account PATCH behavior.
  >
  > P3 — The file-backed stale-PATCH test uses `asyncio.sleep(0.05)` (`tests/test_period_start_replay_v2.py:470`) and the authenticated request can block first while `require_user` writes/commits `AuthSession.last_seen_at`, before reaching the handler’s `BEGIN IMMEDIATE`. The code itself does place `BEGIN IMMEDIATE` as the first handler DB statement at `app/periods.py:604`, and the eventual lifecycle re-read is correct, but the fixture does not specifically prove that lock acquisition point. Prefer a deterministic hook/event at handler entry or otherwise document that this test proves end-state serialization while code inspection proves lock placement.
  >
  > Additional evidence run: focused new suite `6 passed`; period/lifecycle regressions `24 passed`; full suite `159 passed`; `node --check app/static/app.js` passed; `git diff --check` passed. No files were edited and no branch was switched; HEAD remained `e573478` on `task/T-007-period-start-replay`.
  >
  > Verdict: **CHANGES REQUIRED** (P2 coverage gap).
- Resolution: added mutation-neutral current-target future/null assertions,
  end-only historical-overlap success, direct distinct-current guard coverage,
  and cross-account PATCH independence. Replaced the timing sleep with an
  awaitable reserve helper and events that pause after auth, observe the exact
  writer-reservation attempt, and release it only after the accepted lifecycle
  transition/successor is staged. Updated focused result: `7 passed`; legacy
  period/lifecycle result remains `24 passed`; diff-check passed.
- Verdict: changes required; behavior/coverage changed, so fresh re-review is
  required.

### Pass 2

- Reviewer task name/vendor: `/root/t007_start_replay_rereview`, Codex
  same-vendor fallback; cross-vendor reviewer unavailable in this session.
- Reviewed base/head or working-tree manifest: base/HEAD `e573478`; modified
  `app/periods.py`, modified task file, directly inspected untracked focused
  test module, and bounded legacy assertion update.
- Findings (verbatim, P0–P3):

  > Read-only re-review of base/HEAD `e573478` with manifest `M app/periods.py; M docs/tasks/T-007-period-start-replay.md; M tests/test_periods_v2.py; ?? tests/test_period_start_replay_v2.py` (untracked file inspected directly).
  >
  > P0: None.
  >
  > P1: None.
  >
  > P2: None.
  >
  > P3: None.
  >
  > Pass-1 findings are closed:
  >
  > - Current-target future and null Start mutations return deterministic mutation-neutral `422` responses.
  > - End-only PATCH succeeds across accepted closed history while preserving the replay snapshot.
  > - A distinct same-account current row returns `409`; a different account remains independent.
  > - `reserve_period_writer()` is the first PATCH handler database action, before target, lifecycle, predecessor, ledger, or successor reads.
  > - The file-backed concurrency test now pauses deterministically after authentication at the exact reservation helper, observes the blocked `BEGIN IMMEDIATE` attempt behind a staged close/successor transaction without timing sleeps, and proves the stale request re-reads the closed target and cannot revive it.
  >
  > The broader T-007 invariants remain satisfied: exact `Decimal` snapshot replay; posted-ledger derivation; future/range/canonical chronology validation; target exclusion and precise closed/naturally-ended predecessor selection; equality-boundary partitioning; resulting-ended strict cutoff and immutability; historical overlap; rollback and ledger mutation neutrality; one-current-period protection; cross-account isolation; and no T-008/T-009 scope drift.
  >
  > Additional evidence run:
  >
  > - `pytest tests/test_period_start_replay_v2.py -q` — `7 passed`
  > - `pytest tests/test_periods_v2.py tests/test_period_lifecycle_v2.py -q` — `24 passed`
  > - Full `pytest -q` — `160 passed`
  > - `node --check app/static/app.js` — passed
  > - `git diff --check` — passed
  >
  > No files were edited and no branch was switched. HEAD remained `e573478` on `task/T-007-period-start-replay`.
  >
  > Verdict: **APPROVED**.
- Resolution: no further changes required; Pass-1 P2 and P3 are closed.
- Reviewer checks: focused `7 passed`; period/lifecycle `24 passed`; full
  `160 passed`; JS syntax and diff-check passed.
- Verdict: approved; no P0–P3 findings.

### Pass 3 — final task review

- Reviewer task name/vendor: `/root/t007_final_task_review`, Codex same-vendor
  fallback; cross-vendor reviewer unavailable in this session.
- Reviewed base/head or working-tree manifest: complete clean task range
  `1f48429689412f61737fbda5afcfbd78d05d6d23..d2df4d542941771e2b83f217236608308a1ce36c`.
- Findings (verbatim, P0–P3):

  > Read-only final review of `1f48429689412f61737fbda5afcfbd78d05d6d23..d2df4d542941771e2b83f217236608308a1ce36c`.
  >
  > P0: None.
  >
  > P1: None.
  >
  > P2: None.
  >
  > P3: None.
  >
  > All readiness and implementation findings are closed. Branch/base/implementer/status invariants are correct; the implementation is bounded to T‑007, reserves the writer before mutable period reads, preserves exact Decimal snapshot/replay semantics and ledger mutation neutrality, and covers chronology, resulting-ended, predecessor, historical-overlap, cross-account, rollback, and deterministic stale-PATCH concurrency behavior. No T‑008/T‑009 scope drift found.
  >
  > Independent gates:
  >
  > - Focused suite: `7 passed`
  > - Period/lifecycle regression: `24 passed`
  > - Full suite: `160 passed`
  > - `node --check app/static/app.js`: passed
  > - Range `git diff --check`: passed
  > - Worktree: clean
  > - HEAD remained `d2df4d5` on `task/T-007-period-start-replay`
  >
  > No files were edited and no branch was switched.
  >
  > Verdict: **APPROVED FOR LOCAL ACCEPTANCE**.
- Resolution: none required.
- Reviewer checks: complete clean range, focused/regression/full suites, JS,
  range diff-check, and clean worktree.
- Verdict: approved for local acceptance; no P0–P3 findings.

## Session log

Append-only. Every session that touches this task adds one entry before it
ends. Date · agent · what landed · what is left · open questions.

- 2026-08-09 Codex: drafted bounded T-007 Start-date replay after local T-006
  acceptance; readiness, promotion, claim, implementation, and review remain.
  Public period API/schema synchronization remains explicitly deferred to
  T-008; no open question.
- 2026-08-09 Codex: readiness Pass 1 returned two P1 and two P2 findings; the
  task now defines resulting-ended behavior, stale-PATCH serialization,
  historical overlap, exact predecessor eligibility, and a file-backed
  concurrency test. Readiness re-review, promotion, and implementation remain.
- 2026-08-09 Codex: readiness Pass 2 returned one P1 chronology gap; the task
  now rejects derived snapshot boundaries at or after the selected period end
  boundary for create and PATCH, with mutation-neutral equality/later tests.
  Final readiness re-review, promotion, and implementation remain.
- 2026-08-09 Codex: readiness Pass 3 approved T-007 with no P0–P3 findings;
  readiness evidence is complete. Owner promotion, exact branch claim, and
  implementation remain; no open question.
- 2026-08-09 Codex: owner promoted T-007 at `1f48429`; exact branch
  `task/T-007-period-start-replay` was atomically claimed from that promotion
  HEAD and records the full base hash above. Implementation and block review
  remain; no open question.
- 2026-08-09 Codex: implemented atomic Start-date replay and received one P2
  coverage finding plus a P3 concurrency-fixture concern. Added all missing
  focused branches and deterministic post-auth lock events. Focused gate is
  now `7 passed`; period/lifecycle regressions `24 passed`; fresh re-review
  remains; no open question.
- 2026-08-09 Codex: fresh block re-review approved the complete manifest with
  no P0–P3 findings after closure. Independent evidence includes focused
  `7 passed`, regression `24 passed`, full `160 passed`, JS syntax, and
  diff-check. Local gate repetition and task commit remain; no open question.
- 2026-08-09 Codex: repeated the complete local gate after recording approval:
  full pytest `160 passed`; `node --check app/static/app.js` and
  `git diff --check` passed. The reviewed logical block is ready for its
  task-level implementation commit; final clean-range review remains.
- 2026-08-09 Codex: committed the approved implementation as `439ca04` and
  moved T-007 to review. Final clean-range review and local owner acceptance
  remain; no open question.
- 2026-08-09 Codex: final clean-range review approved
  `1f48429..d2df4d5` with no P0–P3 findings. Independent gate: focused
  `7 passed`, period/lifecycle `24 passed`, full `160 passed`, JS syntax,
  range diff-check, and clean worktree. T-007 awaits local owner acceptance.
- 2026-08-09 repository owner (delegated one-session authority): accepted and
  fast-forward integrated `7dd358c` into `finapp-v2-develop`; no push was
  performed. T-007 is done; T-008 is the next ordered task and still requires
  its own task file and independent readiness review before claim.
