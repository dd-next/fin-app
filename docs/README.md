# FinApp v2 — active documentation

This directory is the single source of truth for the next FinApp v2 release.
Active and historical specifications are kept together under `docs/specs/`;
the active release files below override every historical document.

Read documents in this order before changing application code:

1. [`specs/FinnApp-v2.md`](specs/FinnApp-v2.md) — product and technical
   requirements.
2. [`BUILD_PLAN-v2.md`](BUILD_PLAN-v2.md) — mandatory phase order and gates.
3. [`REVIEW_PROTOCOL-v2.md`](REVIEW_PROTOCOL-v2.md) — required independent
   reviewer-subagent process for every logical implementation block.
4. [`PROGRESS.md`](PROGRESS.md) — current checkpoint and evidence log.
5. [`specs/MANUAL_TEST_CASES-v2.md`](specs/MANUAL_TEST_CASES-v2.md) — release
   acceptance scenarios.

## Status

The codebase currently contains an earlier Tracker/commitment implementation.
That implementation is a starting point, not proof that this release is done.
The target release is the one described in this directory: **Operations**,
account-specific periods, workspace-scoped manual valuation rates, the revised
Plan flow, and Docker delivery.

## Authority rules

- If code, an old document, or a prior progress entry conflicts with these
  documents, this directory wins.
- Do not infer an unlisted requirement from the old Tracker or
  `BudgetCommitment` design.
- Amend this documentation first when a genuinely new product decision is
  needed; record the reason in `PROGRESS.md`.
- The UI is English-only even though implementation documentation may be
  Russian.
