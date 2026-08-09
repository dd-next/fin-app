# 01 · Foundations

## Frame

| Band | Height | Notes |
|---|---|---|
| Status bar | 54 | Time left, Dynamic Island centre, indicators right |
| **Content area** | **700** | Everything below lives here |
| Tab bar | 56 | 1px hairline on top, background `--bg` |
| Home indicator | 34 | 134×5 pill, `rgba(255,255,255,.35)` |

Device: 390 × 844, radius 34, background `#0B0D10`, `overflow:hidden`, `position:relative`
(sheets, confirms and the keyboard are absolutely positioned against it).

On a real device replace the fixed bands with `env(safe-area-inset-top/bottom)`;
the 700px content budget is measured **after** both insets.

## Color

Two surface levels only.

| Role | Value | Used for |
|---|---|---|
| Screen background | `#0B0D10` | body, tab bar |
| Surface | `#151A21` + border `rgba(255,255,255,.08)` | capital strip, ops cards, plan strip, sheets, empty-state icon tile |
| Field | `#101419` + border `rgba(255,255,255,.12)` | inputs, selects, amount field |
| Neutral control | `#232A33` | secondary actions, avatar, close button, swipe "Plan" |
| Dialog | `#1B2028` + border `rgba(255,255,255,.1)` | confirmations |
| Keyboard | `#1B1E24`; keys `#3A3F48`; backspace/space `#2A2F37` | |
| Hairline | `rgba(255,255,255,.07)` | row dividers, header underline, column dividers |
| Scrim | `rgba(0,0,0,.62)` | behind any sheet; tap dismisses |

Text: `#E7EAEE` primary · `#C9D0D9` secondary · `#8A93A0` muted · `#5F6875` hint ·
`#4A525E` chevron · `#6B7482` idle tab.

Semantics: accent `#FFA24B` on `#0B0D10` · positive `#6EE7A8` · negative `#FF7B7B` ·
warning `#E8B872` · destructive fill `#7A2F35` on `#FFD9D9`.

Accent is reserved for: active tab, Available today, primary buttons, kickers, badges,
selection checkmarks, focus borders. Never for decoration.

## Type

System stack: `-apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif`.
Kickers only use `ui-monospace, Menlo, monospace`.

| Size / weight | Where |
|---|---|
| 28 / 600, `-.02em`, tabular | amount input |
| 22 / 600, 1.1, `-.01em`, tabular | card values (Balance, Available today) |
| 20 / 600 | sheet title |
| 17 / 600 | screen title, confirm title, empty-state title |
| 16 / 700 | primary submit |
| 15 / 600 | row title, account balance, action buttons, sheet buttons |
| 15 / 500 | field value, control label, "Filters" |
| 14 / 400, 1.5 | confirm body |
| 13 / 600 | chips, segments, swipe actions |
| 13 / 400 | row meta, hints (1.5 for hints) |
| 12 / 500 | keyboard accessory label |
| 11 / 700 mono, `.12em`, upper | sheet kicker |
| 11 / 600, `.1em`, upper | list group headers |
| 11 / 500 | card labels ("Balance", "Available today") |
| 11 / 400 | currency suffix, `⌄` chevron |
| 10 / 500 | tab labels |

Every monetary value uses `font-variant-numeric: tabular-nums` and `white-space: nowrap`.
Long text truncates with ellipsis; it never wraps inside a row.

## Spacing and geometry

Screen horizontal padding: **16**. Row gutter inside a row: **12**. Control gap: **8**.
Ops card gap: **10**.

| Element | Height | Radius |
|---|---|---|
| Screen header | 44 | — |
| List row | 64 | — |
| Ghost row ("New account") | 56 | — |
| Group header | 24 | — |
| Control / field / chip lane | 44 | 10 (sheet) · 12 (form) |
| Chip | 36 | 6 |
| Amount field | 60 | 12 |
| Primary submit | 50 | 12 |
| Sheet button | 48 | 10 (12 in account switcher) |
| Operations card | 96 | 16 |
| Capital strip (Accounts) | 72 | 16 |
| Plan strip | 64 | 16 |
| Leading row icon | 28 | 8 |
| Sheet list icon | 34 | 11 |
| Keyboard | 250 | — |

## Motion

Sheets: transform 180ms ease-out. Scrim: opacity 120ms. Nothing else animates.
All content is legible in the first frame and under `prefers-reduced-motion: reduce`.
