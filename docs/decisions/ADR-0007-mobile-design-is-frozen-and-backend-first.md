# ADR-0007 — The mobile design is frozen and backend synchronization comes first

Status: accepted · 2026-08-09

## Context

The mobile redesign was produced after the shipped backend. It is a complete
390×844 interaction and visual handoff, but it includes flows that the current
API cannot yet drive and omits some existing desktop/backend capabilities.
Changing the design to match implementation accidents would erase the intended
product behavior; deleting omitted backend features would regress desktop.

## Decision

The final mobile design is frozen. `Finapp Screen.dc.html` is its source screen,
the written `spec/01–08` files and tokens are the testable handoff, and
`handoff/finapp-design-canvas.html` is the portable overview. Earlier canvases,
standalone duplicates, and uploads are raw material.

Phase 14 changes backend contracts required by the design and resolves every
gap in `design/MOBILE-BACKEND-GAP-AUDIT.md`. Phase 15 implements the mobile UI
only after Phase 14 closes. Mobile implementation must not fake missing
financial values or silently reinterpret a backend mismatch.

The backend may remain a superset of the mobile design. Existing capabilities
that the 390×844 handoff does not show remain available to desktop until a
separate desktop specification replaces them. When a responsive change works
for both sizes, it may be shared; when desktop needs its own design, preserve
the current desktop behavior.

The design directory committed set contains the final source, written specs,
tokens, support runtime, and portable handoff. `uploads/`, early `.dc.html`
canvases, duplicate standalone exports, and generated thumbnails are not
acceptance authority and are excluded from the intended Git set.

The owner later approved bounded corrections to the source export without
changing its geometry. Start/Edit period gains a rollover checkbox; it is
checked by default and selects `redistribute_remaining_days`, while unchecked
selects `carry_next_day`. The other approved corrections are recorded in
`design/DESIGN-NOTES.md` and the written mobile specification.

## Consequences

- Phase 14 is broader than the account-period rewrite because manual-rate
  direction, transfers, feed projection, correction, category/account
  lifecycle, and the Plan adapter also need backend work.
- External automatic rates and Owner transfer are explicitly deferred;
  authentication retains the shipped username/password server-session model.
- Phase 15 has a stable visual target and a backend contract that can support
  it without design-time hard-coded financial state.
- Desktop is regression-tested during Phase 15 even though it is not visually
  redesigned.
