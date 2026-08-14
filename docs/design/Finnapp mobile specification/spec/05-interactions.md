# 05 · Interactions

## Tap map

**Accounts** — avatar → Profile · rate warning → Set a rate · account row → Account details ·
ghost row / empty-state button → Add account.

**Transactions** — Filters → Filters · chip → filters the feed in place · row → Transaction
details · swipe "Plan" → Link transaction · swipe "Delete" → Delete confirmation ·
empty-state button → Operations tab.

**Operations** — account card → Switch account · period card (active) → Active period ·
period card (none) → Start period · segment → switches mode, clears focus ·
amount → keyboard (numeric) · note → keyboard (text) · Category / Date / Destination →
Choose sheet · Save → Saved confirmation (blocked while the amount is invalid).

**Plan** — `+` → Add rule · upcoming row → Plan item · rule row → Edit rule ·
empty-state button → Add rule.

**Analytics** — avatar → Profile. Nothing else.

**Everywhere** — tab bar switches section and closes any sheet; scrim tap and `✕` close
the sheet; sheet rows marked as navigable in `spec/04-sheets.md` push the next sheet.

## Sheet graph

```
Account details ──Edit details──> Edit account
              ├──Share──────────> Share
              ├──Reconcile─────> Reconcile
              ├──Full history──> Period history
              ├──Archive───────> confirm Archive
              └──history row───> Transaction details

Transaction details ──Edit──> Edit transaction
                    └─Delete─> confirm Delete

Active period ──Close period──> confirm Close  ──View history──> Period history
Period history ──Close current─> confirm Close  ──Edit────────> Edit period
Start period  ──Start period───> closes, screen flips to "period active"

Categories ──Add category──> Add category
           └─row───────────> Edit category ──Delete category──> confirm
                                           └─Merge into another──> Choose sheet

Plan item ──Link transaction──> Link transaction
          ├─Skip─────────────> mark only this occurrence skipped
          └─Edit rule────────> Edit rule ──Delete rule──> confirm/archive rule

Profile ──Manage categories──> Categories
        ├─Exchange rates────> Set a rate
        └─Log out───────────> confirm Log out
```

A Choose sheet opened from inside another sheet returns to that sheet on selection.
A Choose sheet opened from a form returns to the form.

## State model

| State | Source | Effect |
|---|---|---|
| `tab` | tab bar | which section renders; closes sheets |
| `sheet` | any opener | which sheet or confirmation is on screen; `""` = none |
| `mode` | Operations segments | spend / add / transfer / scan |
| `period` | Close period / Start period | active ↔ none; drives the right-hand card |
| `account` | Switch account | rewrites balance, available today, days left, opening balance and the currency suffix everywhere on the screen |
| `focus` | amount / note tap | opens the keyboard, shows the accent caret, sets the accessory label |
| `filter` | Transactions chips | filters the feed and hides emptied group headers |
| `amount`, `note`, `category`, `date`, `destination` | keyboard and Choose sheets | form values |

## Keyboard rules

- Opens only from the amount field (numeric) or the note field (text).
- Overlays; never resizes or scrolls the screen.
- "Done" clears focus and closes it. Switching segment also clears focus.
- Tapping the amount field starts a fresh entry (the field shows `0` with a caret).
- `⌫` deletes one character; the field never goes below `0`.

## Validation

**Available today is informational, not a spending limit.** Spending above it
remains valid and Save stays enabled; the backend records the expense and the
allowance may become negative or be recalculated. Only malformed, zero, or
otherwise invalid amounts block submit.

## Success

Save always ends in the **Saved** confirmation with a single "Done" button; dismissing it
clears the amount, note and destination and leaves the mode untouched.
