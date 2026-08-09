# ADR-0003 — No queue, worker, scheduler, or cache; derive on read

Status: accepted · 2026-07-19 · reaffirmed by `specs/ACCOUNT_PERIODS-v2.1.md` §2

## Context

Day boundaries, daily allowance, and period expiry all look like jobs that want
a scheduler. Adding one would bring a broker, a worker process, and a second
deployment unit into a single-replica SQLite application.

## Decision

Redis, Celery, Prometheus, queues, and background workers are excluded. Every
time-dependent result — day rollover, natural period expiry, daily allowance —
is derived deterministically during a synchronous read.

There is no lazy finalization step. A naturally ended period is recognised by
comparing the workspace-local date to `end_date` at read time; it is never
written to by a background process.

## Consequences

- Deployment stays one container plus one volume.
- Correctness cannot depend on a job having run. Any calculation that would
  need "the job ran at midnight" must be reformulated as a pure function of
  stored data and the current time.
- A naturally ended period carries `closed_at=null` and `closing_balance=null`
  rather than a value invented at a boundary nobody observed — see
  [ADR-0005](ADR-0005-periods-are-optional-and-ledger-derived.md).
