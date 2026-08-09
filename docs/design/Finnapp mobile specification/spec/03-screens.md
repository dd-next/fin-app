# 03 · Screens

Content area = 700px on every screen. Budgets below are measured from the top of the
content area (y = 54 in the frame).

## 3.1 Accounts

Stack: header 44 → `padding:12px 16px 0` → capital strip 72 → [rate warning: +12 gap, 44] →
list `margin-top:12` → group header 24 + rows 64 … → ghost row 56.

| Block | px | Running |
|---|---|---|
| Header | 44 | 44 |
| Gap | 12 | 56 |
| Capital strip (Total capital · Available) | 72 | 128 |
| Gap + rate warning | 12 + 44 | 184 |
| Gap | 12 | 196 |
| List area | 504 | 700 |

504px of list = 7 rows plus two group headers, or 6 rows + ghost row + two headers.

- The capital strip is one surface with a hairline divider — **not** two cards.
- Rate warning is a 44px banner, radius 10, `rgba(232,184,114,.07)` on
  `rgba(232,184,114,.3)`: `!` 13/700, text 13/500 truncating, `›`. Opens **Set a rate**.
  Hidden when every asset has a rate.
- Accounts are grouped by storage type (CASH, BANK, CRYPTO) with the account count on the right.
- Trailing column: balance 15/600 over an 11/400 sub-line ("Not valued" / "protected").
- Whole row opens **Account details**. Ghost row opens **Add account**.

Empty state: 52×52 surface tile with ▤, "Add your first account" 17/600,
one line of 13/400 muted, then a 44px accent button "Add account".

## 3.2 Transactions

Stack: header 44 (title + "Filters" + count badge) → chip lane 44 → list `padding:0 16`.

| Block | px |
|---|---|
| Header | 44 |
| Chip lane | 44 |
| List area | 612 |

612px = 2 group headers (48) + 8 rows (512), 52px spare.

- Chips: All · Income · Expense · Transfer · Planned. They **filter the feed for real**;
  a group header disappears when its group empties.
- Rows: direction glyph tile (↑ positive tint / ↓ negative tint / ± neutral),
  title, meta "You", status pill (Planned accent, Deleted negative) next to the meta —
  never on its own line — and the signed amount.
- Swipe left reveals two 64px full-height actions: "Plan" (`#232A33`) and
  "Delete" (`#7A2F35` / `#FFD9D9`). The row body shifts by −112px.
- Tapping a row opens **Transaction details**.

Empty state: ⇄ tile, "No transactions yet", one line of copy, accent button
"Open Operations" that switches tabs.

## 3.3 Operations — the tight one

No header. Container `padding:8px 16px 0`.

| Block | Margin | px | Running from content top |
|---|---|---|---|
| Container top padding | | 8 | 8 |
| Account card + period card (96, gap 10) | | 96 | 104 |
| Segmented control | 12 | 44 | 160 |
| *(Transfer only)* destination field | 10 | 44 | 214 |
| Amount field | 10 | 60 | 274 / 220 |
| *(Error only)* message line | 0 | 20 | +20 |
| Category + Date row | 8 | 44 | 326 / 272 |
| Note field | 8 | 44 | 378 / 324 |
| Submit | 12 | 50 | **440 / 386** |

In frame coordinates the submit button ends at **y = 494** (Transfer) or **y = 440**.
The keyboard occupies the bottom 250px, i.e. it starts at **y = 594**.

**Clearance: 100px on Transfer, 154px elsewhere, 80px on Transfer with a validation error.**
This is the constraint the whole screen is built around — if you change a height, re-run this table.

- Both top cards are locked to 96px. The "no period" state must not grow the card.
- Scan mode replaces the form with a centred placeholder ("Coming soon", "Scan is reserved
  for a later release. No OCR is performed."). The two cards and the segmented control stay.
- Submit label follows the mode: "Save spending" / "Add funds" / "Save transfer".
- Category default follows the mode: Groceries / Salary / Uncategorized.

## 3.4 Plan

Stack: header 44 (title + accent `+`) → `padding:12px 16px 0` → strip 64 →
list `margin-top:12` → "UPCOMING · next 30 days" 24 → 3 rows → "RULES · 1 active" 24
(`margin-top:8`) → 2 rows.

Upcoming rows carry a status pill: `planned` and `required` accent, `overdue` negative.
Tapping an upcoming row opens **Plan item**; tapping a rule opens **Edit rule**.

Empty state: ◇ tile, "Plan what comes next", one line, accent button "Add rule".

## 3.5 Analytics

Intentionally unbuilt. Header 44 + avatar, then a centred placeholder: ⚡ tile,
"Coming soon", "Income, spending, and trends arrive once the core ledger is stable."
Ship exactly this. Do not add charts, ranges, or filters.
