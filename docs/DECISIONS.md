# FinApp — decision log

One file per decision in [`decisions/`](decisions/). A decision belongs here
when reversing it would cost real work: storage shape, financial semantics,
process, or a deliberate exclusion.

Add an entry when a decision is made, not when the code lands. If a task's
`Session log` contains a sentence starting "we decided", that sentence belongs
here instead.

Status: `accepted` · `superseded by ADR-NNNN`

| ADR | Decision | Status |
|-----|----------|--------|
| [0001](decisions/ADR-0001-clean-v2-reset.md) | v2 starts from a clean database and a new Alembic history | accepted |
| [0002](decisions/ADR-0002-manual-valuation-rates.md) | Valuation uses workspace-scoped manual rates only | accepted |
| [0003](decisions/ADR-0003-no-background-infrastructure.md) | No queue, worker, scheduler, or cache — derive on read | accepted |
| [0004](decisions/ADR-0004-independent-reviewer.md) | Every logical block is reviewed by a different agent | accepted |
| [0005](decisions/ADR-0005-periods-are-optional-and-ledger-derived.md) | Periods are optional and derive from the ledger, not from a funded amount | accepted |
| [0006](decisions/ADR-0006-repo-is-the-shared-agent-memory.md) | The repository is the only shared memory between agents | accepted |
| [0007](decisions/ADR-0007-mobile-design-is-frozen-and-backend-first.md) | Freeze the mobile design, synchronize backend in Phase 14, then implement mobile in Phase 15 | accepted |
| [0008](decisions/ADR-0008-canonical-manual-rate-direction.md) | Store manual valuation rates canonically in Asset-to-Main direction | accepted |
| [0009](decisions/ADR-0009-bound-transfer-quotes.md) | Persist exact five-minute Transfer quotes bound to canonical manual rates | accepted |
