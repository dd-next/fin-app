# Finapp mobile — build instructions for a coding agent

You are implementing a mobile finance app from a finished design. The design is the source of
truth, not this prose: every number here was measured from `Finapp Screen.dc.html`.

## Read in this order

1. `spec/01-foundations.md` — color, type, spacing, geometry, safe areas
2. `spec/02-components.md` — every primitive with exact pixel geometry
3. `spec/03-screens.md` — the five sections, stack by stack, with vertical budgets
4. `spec/04-sheets.md` — full catalogue of bottom sheets and confirmations
5. `spec/05-interactions.md` — what every tap does; navigation graph; states
6. `spec/06-content.md` — every user-visible string, verbatim
7. `spec/07-data-model.md` — entities, derived values, open questions
8. `spec/08-acceptance.md` — the checklist your build must pass

Machine-readable: `tokens.css`, `design-tokens.json`.
Final source and visual reference: `Finapp Screen.dc.html`. The portable
overview is `handoff/finapp-design-canvas.html`; `Finapp Mobile Redesign.dc.html`
is only a raw overview canvas that imports the final source.

## Non-negotiables

- **390 × 844 reference frame.** Content area is exactly 700px: 844 − 54 status − 56 tab bar − 34 home indicator.
- **No screen scrolls except the two list screens** (Transactions, Accounts overflow). Operations must fit whole, keyboard open, with the submit button visible.
- **Two surface levels maximum.** Screen background → one surface → controls inside it. A metric inside a card is a row divided by a hairline, never a nested card.
- **One header tier per screen.** Orange kickers (`ACCOUNT`, `LEDGER`, `SETTINGS`) exist only inside sheets, never on a screen.
- **Every interactive target ≥ 44px.** Chips are 36px tall inside a 44px lane.
- **No system `alert()`, `confirm()`, or `prompt()`, and no native `<select>` pickers.** Every choice is a bottom sheet; every destructive action is the branded confirm dialog. See `spec/04-sheets.md`.
- **Operations has no screen header.** The section is already named in the tab bar.
- **Analytics is intentionally a placeholder.** Ship the empty state as drawn; do not invent charts.
- No component libraries, no icon packs, no webfonts. System font stack, one stylesheet, CSS custom properties.

## Definition of done

`spec/08-acceptance.md` passes on a 390×844 viewport with the software keyboard open.
