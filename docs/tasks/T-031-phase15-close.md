---
id: T-031
title: Assemble Phase 15 closure evidence
status: backlog
size: S
spec: all Phase 15 authorities and ADR-0011
blocked-by: [T-030B]
branch: task/T-031-phase15-close
base-commit:
implementer:
readiness-reviewed-by: /root/phase15_readiness_review, Codex GPT-5 same-vendor fallback
readiness-reviewed-commit: deb8a5a
readiness-verdict: ready
---

## Goal

Make the repository ready for owner acceptance of Phase 15 without accepting,
archiving, pushing, deploying, or declaring permanent use on the agent's behalf.

## Acceptance

- [ ] T-023, every A/B split through T-030B, and all intervening numbered tasks
      are accepted into local `finapp-v2-develop`; their task logs contain exact
      implementation review and targeted/browser gates.
- [ ] All P0–P2 are closed; each deferred P3 has an explicit disposition.
- [ ] `docs/PROGRESS.md` reports the actual Phase 15 outcome in 2–4 lines, exact
      final gate results, and links to task evidence/ADRs; no stale count is
      copied.
- [ ] `docs/BACKLOG.md`, task front matter and dependencies agree. README is
      updated only if actual run/use instructions changed.
- [ ] If changes after T-030B are docs-only, its full runtime/browser evidence
      is reused and `git diff --check` is rerun; otherwise the affected gate is
      rerun before review.
- [ ] Final state says `awaiting owner acceptance`. The agent does not archive
      tasks, create `v2 phase 15`, push, deploy, or declare permanent financial
      data safe.

## Touches

`docs/PROGRESS.md`, `docs/BACKLOG.md`, Phase 15 task evidence, README only when
needed, and this task file.

## Out of scope

Product/runtime/schema changes; accepting or archiving the phase; phase commit;
push/deploy; starting permanent use.

## Verification

```bash
git diff --check
git status --short
```

Cross-check the exact T-030A/T-030B mobile, desktop, full-suite, JS, dependency,
migration, health and SPA evidence. Rerun affected gates if any non-doc file
changed afterward.

## Review

Append the bounded independent documentation/closure review following the
protocol.

## Session log

- 2026-08-12 Codex GPT-5: closure task specified for batch readiness; not
  claimed.
- 2026-08-12 Codex GPT-5: closure range updated for every split; limited
  independent re-review verdict `ready`.
