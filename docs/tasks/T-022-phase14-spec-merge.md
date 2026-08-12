---
id: T-022
title: Merge accepted Phase 14 contracts into the release specification
status: done
size: S
spec: specs/FinnApp-v2.md and all accepted Phase 14 contracts
blocked-by: [T-021]
branch: task/T-022-phase14-spec-merge
base-commit: cdd0df2
implementer: Codex GPT-5
readiness-reviewed-by: owner fast-track exception
readiness-reviewed-commit: cdd0df2
readiness-verdict: ready
---

## Goal

`docs/specs/FinnApp-v2.md` is the concise active authority for the actually
accepted Phase 14 backend contracts, fast-track exclusions, and disposable-data
migration policy that Phase 15 may consume.

## Acceptance

- [x] Replace stale funded/Planned period semantics with optional
  ledger-derived snapshot/reconciliation lifecycle and the two exact policies.
- [x] Record canonical Asset-to-Main manual rates, bound transfer quote/execute,
  financial-date persisted/planned feed, and the mobile Plan-rule adapter.
- [x] Explicitly defer T-015 transaction conversion, T-016 category
  merge/delete, and T-017 account restoration until after Phase 15.
- [x] Record ADR-0010 fresh-schema-only migration gates without weakening
  runtime Decimal, ledger, permission, privacy, or atomicity requirements.
- [x] Do not repeat task histories; make the primary spec self-contained enough
  for Phase 15 and link detailed authorities only where useful.

## Touches

`docs/specs/FinnApp-v2.md`, this task file, backlog/progress state, and the
status line in the now-merged account-period change spec.

## Out of scope

No runtime, test, schema, migration, frontend, or Phase 15 implementation
change. No deferred T-015/T-016/T-017 behavior.

## Verification

```bash
rg -n "funding_amount|Remaining \| Planned|1 Main currency = X Asset|T-015|T-016|T-017|populated" docs/specs/FinnApp-v2.md
git diff --check
```

## Review

### Pass 1

- Reviewer task name/vendor: `/root/t022_review`, Codex GPT-5.6 Terra medium;
  same-vendor fallback because a cross-vendor reviewer was unavailable.
- Reviewed base/head or working-tree manifest: base `cdd0df2`; modified
  backlog and two specs; untracked task file.
- Findings (P0–P3): two P1 authority omissions — add account/posted predicates
  to the canonical period movement set; add cross-asset target quantization and
  exact outgoing/incoming Main-value equality rejection to transfer quoting.
- Resolution: both accepted predicates were added precisely; limited re-review
  required before commit.
- Reviewer checks: inspected the complete docs-only manifest and cross-checked
  every accepted Phase 14 task; `git diff --check` passed.
- Verdict: changes required; corrected and submitted for re-review.

### Pass 2

- Reviewer task name/vendor: `/root/t022_review`, Codex GPT-5.6 Terra medium.
- Reviewed base/head or working-tree manifest: limited final corrections to
  the period membership and bound quote sections.
- Findings (P0–P3): no findings.
- Resolution: none.
- Reviewer checks: re-read both corrections against T-002/T-003/T-013Q;
  requirements are explicit and non-contradictory; `git diff --check` passed.
- Verdict: clean; no open P0–P3.

## Session log

- 2026-08-12 Codex GPT-5: claimed from accepted T-021 commit `cdd0df2`; merging
  accepted contracts and explicit exclusions into the primary authority.
- 2026-08-12 Codex GPT-5: consolidated the accepted contracts, closed two P1
  authority omissions, and passed limited re-review; nothing remains for T-022.
