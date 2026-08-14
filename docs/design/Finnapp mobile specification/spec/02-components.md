# 02 · Components

Each primitive below is used everywhere it applies. Do not create variants.

## Screen header — 44px
`display:flex; align-items:center; justify-content:space-between; padding:0 16px`,
hairline underline. Left: section name, 17/600. Right: **exactly one** affordance in a
44×44 target. Accounts / Plan / Analytics use the avatar (30×30, radius 15, `#232A33`,
1px `rgba(255,255,255,.1)`, 10px accent dot inside). Transactions uses the text button
"Filters" + count badge (min-width 18, height 18, radius 9, accent fill, 11/700).
Plan uses a 32×32 accent `+` tile, radius 10.

**Operations has no header.** It starts straight into content at `padding:8px 16px 0`.

## List row — 64px
`height:64; display:flex; align-items:center; gap:12; border-bottom:1px hairline`.
Leading 28×28 tinted icon tile (radius 8) → title 15/600 + meta 13/400 muted stacked with
3px gap → trailing value 15/600 tabular → optional `›` in `#4A525E`.
The whole row is the tap target. Never put buttons inside a row.

Ghost row (56px): dashed 28×28 tile, no divider, muted label — used for "New account".

## Group header — 24px
11/600, `.1em`, uppercase, muted. Optional right-aligned count 11/400 muted.
Used for date groups in Transactions and type groups in Accounts.

## Metric strip
One surface, hairline vertical divider, no nested cards.
Accounts: 72px, two columns (`Total capital`, `Available`), each `padding:14px 16px`,
label 11/500 muted over value 20/600 (Available is accent).
Plan: 64px, two columns (`Open items`, `Completed`), `padding:12px 14px`.

## Operations cards — 96px each, gap 10
Two equal cards, `box-sizing:border-box`, `padding:10px 14px 12px`,
`justify-content:space-between`.
- **Left — account.** Top line 26px: account title 15/600 + `⌄`. Bottom: label "Balance"
  11/500 muted, value 22/600 + currency suffix 11/500 muted. Opens the account switcher.
- **Right — period, active.** Top line 26px: 6px `#6EE7A8` dot + "Period · 15d" 13/500
  `#C9D0D9`, `›` right. Bottom: "Available today" + value 22/600 accent + currency.
  Opens period details.
- **Right — no period.** Same 96px box, dashed border `rgba(255,255,255,.16)`, transparent
  fill. Top line: grey dot + "No period". Bottom: 36px accent-tint button "+ Start period".
  **The card must not change height between states.**

## Segmented control — 44px
Surface fill, radius 12, `padding:3`, `gap:2`. Segments are equal flex children,
radius 9, 13/600. Active: `#232A33` fill, `#E7EAEE`. Idle: transparent, muted.
Switching a segment must not change the height of the form below it.

## Chip lane — 44px lane / 36px chip
`display:flex; gap:8; padding:0 16; overflow:hidden` (horizontal scroll on device, no wrap).
Chip: `padding:0 14`, radius 6, 13/600. Active: accent fill, `#0B0D10`.
Idle: transparent, 1px `rgba(255,255,255,.12)`, `#9AA3B0`.

## Field (form) — 44px, radius 12
`background:#101419`, 1px `rgba(255,255,255,.12)`, `padding:0 14`.
Select-like fields show value left, `⌄` right, and open a **Choose sheet** — never a
native picker. Focused text fields raise the border to `rgba(255,162,75,.55)` and show an
accent caret. Category + Date share one 44px row, `flex:6` and `flex:4`, gap 8.

## Field (sheet) — 44px, radius 10
Same fill, but label 13/500 muted on the left and value 15/500 on the right with `⌄`.

## Amount field — 60px, radius 12
Value 28/600 tabular with accent caret; currency suffix 15/500 muted, pinned right.
Error state: border `rgba(255,123,123,.6)`, value `#FF7B7B`, plus a 20px message line
12/500 `#FF7B7B` directly under it, and the submit button goes to `#3A2A2C` / `#8A6B6E`
and stops responding.

## Buttons
- Primary submit: 50px, radius 12, accent fill, 16/700 `#0B0D10`, full width.
- Sheet primary: 48px, radius 10, accent fill, 16/700; sits in the sheet footer, right.
- Sheet secondary: 48px, `padding:0 18`, radius 10, 1px `rgba(255,255,255,.12)`, `#C9D0D9`.
- Inline action (inside a sheet): 44px, `padding:0 16`, radius 10, `#232A33`, 15/600.
- Destructive inline action: `rgba(255,123,123,.1)` fill, `rgba(255,123,123,.3)` border, `#FF7B7B`.
- Destructive confirm: `#7A2F35` fill, `#FFD9D9` label.

## Bottom sheet
`position:absolute; left:0; right:0; bottom:0; max-height:88%`, background `#151A21`,
top corners radius 20, 1px top border `rgba(255,255,255,.1)`. Scrim `rgba(0,0,0,.62)`
covers the whole frame and dismisses on tap.

Structure top to bottom:
1. Grabber lane 18px — 36×4 pill `rgba(255,255,255,.22)`.
2. Header 44px, `padding:0 16` — kicker 11/700 mono accent over title 20/600; 44×44 close
   target on the right holding a 30×30 `#232A33` tile with `✕`.
3. Body `padding:8px 16px 0`, `gap:8`, in this order when present: fields → toggle →
   hint → action buttons → list title → rows → second list title → second rows.
4. Footer `padding:16`, secondary left, primary right (primary is `flex:1`).
5. 34px bottom safe band.

Rows inside a sheet are 48px with a top hairline; tappable rows carry `cursor:pointer`.

## Confirmation dialog
Not a sheet. `left:16; right:16; bottom:34`, background `#1B2028`, 1px
`rgba(255,255,255,.1)`, radius 18, `padding:20px 18px 16px`, `gap:14`.
Title 17/600, body 14/400 1.5 muted (`text-wrap:pretty`), then two 48px buttons at
`gap:8`: "Cancel" outlined, then the action. Success dialogs drop Cancel and use one
accent button.

**This replaces every `alert()` / `confirm()` in the product.**

## Keyboard — 250px
`position:absolute; bottom:0`, background `#1B1E24`, 1px top border,
`padding:0 6px 34px`.
- Accessory bar 40px: context label 12/500 `#6B7482` left; "Done" button right —
  32px tall, `padding:0 14`, radius 8, `#2A2F37`, 14/600 accent.
- Key grid: `padding:7px 0 0`, row gap 5, key gap 6, keys radius 6, `#3A3F48`,
  24/400 white. Backspace and space use `#2A2F37`; multi-character keys drop to 15px.
- Numeric layout: `1 2 3 / 4 5 6 / 7 8 9 / , 0 ⌫`. Text layout: qwerty rows + full-width space.

The keyboard overlays the screen; it never pushes layout. See the clearance budget in
`spec/03-screens.md`.

## Tab bar — 56px
Five equal items, icon 17/400 over label 10/500, `gap:3`. Active accent, idle `#6B7482`.
Order: Accounts ▤ · Transactions ⇄ · Operations ◎ · Plan ◇ · Analytics ϟ.
Switching tabs always closes any open sheet.
