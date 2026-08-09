# ADR-0004 — Every logical block is reviewed by a different agent

Status: accepted · 2026-07-19 · extended 2026-08-08

## Context

An agent that writes a change is a poor judge of whether the change meets the
requirement it was given. Self-review reliably confirms the author's own
misreading of a spec.

## Decision

Every written logical block gets a fresh, read-only reviewer agent that is not
the author, following [`REVIEW_PROTOCOL-v2.md`](../REVIEW_PROTOCOL-v2.md).
Findings are fixed before the next block, and a re-review runs when the fixes
changed behavior or coverage.

Extension, 2026-08-08: when two vendors are available, the reviewer should be
the *other* one — Codex reviews Claude Code and vice versa. Two instances of
the same model share the same blind spots; two vendors do not.

## Consequences

- Review cost is real and is paid per block, not per phase.
- The protocol scales by block risk: schema, domain, and money blocks get the
  full protocol; documentation and UI-copy blocks get a lightweight pass.
- Reviewer task name, findings, and resolution are recorded in the task file,
  which makes an unreviewed block visible rather than merely undocumented.
- The reviewer remains read-only. The implementer records the returned output
  verbatim with reviewer vendor and reviewed range; detailed evidence is not
  duplicated in `PROGRESS.md`.
