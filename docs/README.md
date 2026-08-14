# FinApp — active documentation

This directory is the single source of truth for FinApp. Active and historical
specifications sit together under [`specs/`](specs/); the active files below
override every historical document.

## Read in this order

Every session, before touching code — this is the whole default context:

1. [`../AGENTS.md`](../AGENTS.md) — the working agreement and the session
   protocol. `../CLAUDE.md` is a symlink to it.
2. [`PROGRESS.md`](PROGRESS.md) — what is true right now.
3. The one task file in [`tasks/`](tasks/) you are working on.

Read further only when the task needs it:

- [`BACKLOG.md`](BACKLOG.md) — ordered upcoming work. Read when choosing what
  to do next, which is the owner's call, not an agent's.
- [`specs/FinnApp-v2.md`](specs/FinnApp-v2.md) — product and technical
  requirements, active release authority.
- [`specs/ACCOUNT_PERIODS-v2.1.md`](specs/ACCOUNT_PERIODS-v2.1.md) — accepted
  detailed period fixtures; its Phase 14 result is merged into the primary
  specification above.
- [`design/MOBILE-BACKEND-GAP-AUDIT.md`](design/MOBILE-BACKEND-GAP-AUDIT.md) —
  required backend changes for the frozen mobile design; Phase 14 planning
  authority alongside the period specification.
- [`DECISIONS.md`](DECISIONS.md) — why things are the way they are, one ADR per
  decision in [`decisions/`](decisions/).
- [`REVIEW_PROTOCOL-v2.md`](REVIEW_PROTOCOL-v2.md) — the mandatory independent
  reviewer process for every logical block.
- [`BUILD_PLAN-v2.md`](BUILD_PLAN-v2.md) — phase order and gates.
- [`design/DESIGN-NOTES.md`](design/DESIGN-NOTES.md) — design truth in words,
  and where the material that is not in git lives.
- [`specs/MANUAL_TEST_CASES-v2.md`](specs/MANUAL_TEST_CASES-v2.md) — release
  acceptance scenarios.
- [`history/`](history/) — closed evidence. Archive, never appended to.

## Layout

```text
docs/
  README.md      you are here
  PROGRESS.md    current state, replaced as reality changes
  BACKLOG.md     ordered upcoming work, owner-controlled
  DECISIONS.md   index of durable decisions
  tasks/         one file per unit of work; TEMPLATE.md is the shape
    archive/     closed tasks
  decisions/     ADR-NNNN-*.md
  design/        design truth an agent can act on
  history/       closed phase evidence
  specs/         active and historical specifications
```

## Authority rules

- If code, an old document, or a prior progress entry conflicts with these
  documents, this directory wins.
- Within this directory: `specs/FinnApp-v2.md` is the consolidated authority
  for Phase 15. Detailed accepted specs and ADRs may explain it but cannot
  silently override it; a new conflict requires an explicit accepted decision.
- Do not infer an unlisted requirement from the old Tracker or
  `BudgetCommitment` design.
- Amend this documentation first when a genuinely new product decision is
  needed, and record the reason as an ADR in `decisions/`.
- The UI is English-only even though implementation discussion may be Russian.
