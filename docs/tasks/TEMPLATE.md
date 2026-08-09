---
id: T-NNN
title: <imperative, one line>
status: backlog       # backlog | todo | in-progress | review | done
size: S               # S | M | L — an L task must be split before it starts
spec: specs/<file>.md §N
blocked-by: []
branch: task/T-NNN-<slug>
base-commit:
implementer:
readiness-reviewed-by:
readiness-reviewed-commit:
readiness-verdict:
---

## Goal

One sentence: what must be true when this task is done.

Before the repository owner commits the `backlog` to `todo` promotion, a
separate read-only agent reviews this task definition against the named specs.
Record that reviewer's identity, the earlier commit containing the reviewed
task file, and `ready` or `not-ready` in the front matter. At initial claim the
implementer branches from the accepted integration `HEAD` containing that
promotion, then records the resolved hash as `base-commit` in the first task
commit; the promotion commit never tries to contain its own hash.

## Acceptance

Each line must be checkable by a command, a test, or a file inspection. If a
line needs judgement to evaluate, rewrite it.

- [ ] …
- [ ] …

## Touches

Files and modules expected to change. A change outside this list is a signal to
stop and split the task, not to widen it.

## Out of scope

State explicitly what this task must not do, so the agent does not drift into
the next task.

## Verification

Exact commands the implementing agent must run and paste results for. Commands
that touch a database must set an explicit scratch `DATABASE_URL`; unsetting
the variable is not a scratch-database strategy.

```bash
```

## Review

Append-only review passes. A different read-only agent returns the review; the
implementer records it verbatim following
[`../REVIEW_PROTOCOL-v2.md`](../REVIEW_PROTOCOL-v2.md).

### Pass <N>

- Reviewer task name/vendor:
- Reviewed base/head or working-tree manifest:
- Findings (verbatim, P0–P3):
- Resolution:
- Reviewer checks:
- Verdict:

## Session log

Append-only. Every session that touches this task adds one entry before it
ends. Date · agent · what landed · what is left · open questions.

- YYYY-MM-DD <agent>: …
