---
id: T-007
title: Implement atomic period Start-date snapshot replay
status: backlog
size: M
spec: specs/ACCOUNT_PERIODS-v2.1.md §3, §5, §8; design/MOBILE-BACKEND-GAP-AUDIT.md period start date
blocked-by: [T-002, T-003, T-004]
branch: task/T-007-period-start-replay
base-commit:
implementer:
readiness-reviewed-by:
readiness-reviewed-commit:
readiness-verdict:
---

## Goal

An owner can select a past-or-today Start date when creating a period or
editing a current period, and every edit atomically rebuilds the exact opening
snapshot and replay partition without changing the posted ledger balance.

## Acceptance

- [ ] Creating with an explicit workspace-local Start date in the past or on
      today succeeds, while a future Start date and `end_date < start_date`
      fail before any period row is persisted. The existing create path keeps
      deriving `snapshot_at` and exact `opening_balance`; T-008 owns making an
      omitted Start date default to today.
- [ ] PATCH evaluates lifecycle state before applying the update: a period
      that is current at the start of the serialized operation may change
      `start_date` alone or together with `end_date`; an already ended or
      manually closed period remains read-only. A selected future Start date,
      null field, or resulting `end_date < start_date` is rejected
      deterministically and leaves every stored period field unchanged.
- [ ] A current period may atomically move to a valid resulting-ended range.
      That response uses the strict `< first local instant after end_date`
      ended replay cutoff, the stored row is immediately read-only afterward,
      a leg exactly at the end boundary is excluded, and the account may then
      accept a successor under the T-004 rules. The edit does not invent
      `closed_at` or `closing_balance`.
- [ ] A successful Start-date change recomputes `snapshot_at` as the exact
      maximum of the new workspace-local day boundary and every eligible
      predecessor boundary. Eligibility is evaluated at the serialized
      workspace-local today: same account, edited target excluded, and either
      manually closed (`closed_at IS NOT NULL`) or naturally ended
      (`closed_at IS NULL AND end_date < today`). The predecessor boundary is
      `closed_at` for manual close or the first workspace-local instant after
      its inclusive `end_date`; the maximum boundary is selected across all
      such rows. `opening_balance` is then recomputed from posted legs with
      `created_at <= snapshot_at`, using `Decimal` only.
- [ ] The edit atomically persists the selected dates, recomputed
      `snapshot_at`, and recomputed `opening_balance`. SQLite reserves the
      writer before reading lifecycle state, predecessors, ledger snapshot, or
      successor eligibility; any validation or replay failure rolls back the
      complete update.
- [ ] Replaying the new canonical window changes no `Transaction` or
      `TransactionLeg`, creates no movement, and leaves the exact live account
      balance unchanged. For a resulting-current period, `period_movements`
      includes every later posted leg exactly once, excludes legs at the
      snapshot boundary, and `current_period_balance_inputs` still reconciles
      opening plus window to that unchanged live balance. A resulting-ended
      period instead uses its strict historical cutoff and is never passed to
      the current-only reconciliation input.
- [ ] Backward and forward Start-date moves cover pre-boundary corrections and
      posted/voided legs without double counting. A leg exactly at the new
      snapshot boundary is represented in opening only; a later leg is replayed
      only; 18-place Decimal values remain exact.
- [ ] A same-local-day manually closed predecessor remains the effective
      boundary when later than the selected local-day boundary. Changing the
      successor Start date cannot cross or absorb that accepted predecessor
      window, and the equality leg at the close boundary remains in successor
      opening but outside successor replay.
- [ ] Successor/current-period eligibility is checked in the same serialized
      transaction. The endpoint reserves the writer before loading the target,
      so a stale PATCH that waits behind an operation which ended/closed that
      target and accepted a successor must re-read lifecycle state, return
      `409`, and leave both periods and every ledger row unchanged. A PATCH
      that serializes first has the deterministic resulting-current or
      resulting-ended behavior above and never creates a second current row.
- [ ] Original date-range overlap with distinct closed/ended history is allowed
      for both Start-date and end-date-only edits, superseding the old all-row
      `ensure_no_overlap` behavior. A distinct same-account current row is a
      conflict; different accounts remain independent.
- [ ] Existing valid end-date-only PATCH behavior remains compatible except for
      the explicitly superseded all-history overlap rejection. The obsolete
      legacy assertion that every Start-date change returns `409` is replaced
      only where the accepted v2.1 contract supersedes it.
- [ ] Focused tests cover create past/today/future and invalid range; backward,
      forward, and simultaneous Start/end edits; already ended/closed rejection;
      exact timezone and same-day predecessor boundaries; exact ledger and
      replay/reconciliation invariants; rollback; resulting-ended strict cutoff,
      subsequent immutability, and successor creation; historical overlap;
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

## Review

Append-only implementation review passes. A different read-only agent returns
the review; the implementer records it verbatim following
[`../REVIEW_PROTOCOL-v2.md`](../REVIEW_PROTOCOL-v2.md).

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
