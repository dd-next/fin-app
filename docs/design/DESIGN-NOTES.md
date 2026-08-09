# FinApp — design notes

The written half of the design: everything an agent needs to build a screen
correctly without opening a design tool.

Why this file exists: a `claude.ai/design` project is reachable by Claude Code
and not by Codex, and a chat link is reachable by neither in the next session.
See [ADR-0006](../decisions/ADR-0006-repo-is-the-shared-agent-memory.md).

## Status

**The mobile design is supplied and frozen for implementation planning.** It
must not be altered to hide a missing backend capability. Backend gaps are
listed in [`MOBILE-BACKEND-GAP-AUDIT.md`](MOBILE-BACKEND-GAP-AUDIT.md) and are
implemented in Phase 14 before the mobile UI begins in Phase 15.

Desktop remains supported but has no replacement design yet. Reuse a mobile
change on desktop when it is naturally responsive; otherwise preserve the
current desktop behavior until a desktop specification exists.

## Rules

- A task never says "match the design". It names a token, a rule written in
  this file, or a state described in the task file.
- Design material becomes usable only once it is referenced from this file.
  Anything not listed here is not part of the design.
- When a screen is implemented, the same commit records the tokens it
  introduced and adds a line to the change log below.
- The rendered app is the check. Verify with the `verify` skill against a
  scratch database, never against `finapp.db`.
- UI copy is English only.

## Where things go

| What | Where | In git |
|------|-------|--------|
| Tokens the app actually uses | `app/static/` stylesheet | yes |
| Decisions, states, rules | this file | yes |
| Final source screen | `Finnapp mobile specification/Finapp Screen.dc.html` | yes |
| Portable canvas | `Finnapp mobile specification/handoff/finapp-design-canvas.html` | yes |
| Written specification | `Finnapp mobile specification/spec/01-foundations.md` … `08-acceptance.md` | yes |
| Machine-readable source | `Finnapp mobile specification/tokens.css`, `design-tokens.json` | yes |
| Overview canvas | `Finnapp mobile specification/Finapp Mobile Redesign.dc.html` | raw reference |
| Early canvases, standalone duplicates, uploads | `Finnapp mobile specification/` | raw material, not committed |

The source screen owns visible geometry, states, and interaction intent. The
portable canvas catalogues the same material. Written specs and tokens make
the handoff searchable and testable. If they appear to conflict, inspect the
source screen and record the resolution here or in an ADR; never silently
choose an early canvas.

`Finapp Mobile Redesign.dc.html` is an overview canvas that imports
`Finapp Screen.dc.html`. It is not a competing source. `Finapp Mobile
Screens.dc.html`, `Finapp Density Spec.dc.html`, the other `.dc.html` canvases,
standalone duplicates, `.thumbnail`, and `uploads/` are earlier/raw material.

## Backend truths the design must respect

Phase 14 reconciles these backend truths with the frozen mobile design. Until
its tasks close, a mismatch blocks implementation rather than authorising an
agent to change the design:

- an account balance always exists;
- a period is optional, and having none is a normal state — not an empty state
  to apologise for;
- `available_today` exists only while a period is current;
- Funding and Planned no longer exist anywhere in the period surface;
- the backend supports exactly two rollover policies; Start/Edit period uses a
  checkbox, checked by default for `redistribute_remaining_days` and unchecked
  for `carry_next_day`;
- closing a period permits starting another one immediately.

## Owner-approved corrections after the source export

These rules supersede the older behavior visible in `Finapp Screen.dc.html`
without changing its geometry. Phase 15 applies them when implementing the UI:

- Available today is informational; exceeding it never disables Save or causes
  backend rejection.
- Plan item has three same-row actions: Edit rule, Skip, Link transaction. Skip
  affects one occurrence; Delete rule archives the rule, retains linked
  transactions, and prevents future items from being generated or selected.
- Plan account copy is dynamic: To account for Expected income, From account
  for expense kinds.
- Owner remains visible but disabled as `Coming soon`; ownership transfer is
  deferred until after the mobile redesign.
- logout uses the existing server-side username/password session model; remove
  the incorrect local-data/invite-only claim.
- rates are manual only; Auto remains a disabled `Coming soon` placeholder.

## Tokens

The handoff tokens are supplied in `Finnapp mobile
specification/design-tokens.json` and `tokens.css`. Phase 15 imports only the
tokens the application uses into `app/static/`; raw handoff files are not
runtime dependencies.

## Change log

One line per landed design change: date, what changed, why.

- 2026-08-09 — registered the frozen mobile source hierarchy and linked the
  backend gap audit; no design asset changed.
