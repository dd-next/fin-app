# 08 · Acceptance checklist

Run at 390 × 844. Every box must be checked before the build is considered done.

## Layout

- [ ] Content area measures exactly 700px between the status bar and the tab bar.
- [ ] No screen scrolls except the Transactions feed and a long Accounts list.
- [ ] Operations fits whole with no scrollbar in all four modes.
- [ ] With the keyboard open on Transfer, the submit button is fully visible with ≥ 80px of clearance.
- [ ] Both Operations cards are 96px tall in the "period active" and "no period" states.
- [ ] Switching a segment does not change the height of anything above it.
- [ ] No surface is nested more than two levels deep.
- [ ] No screen shows an orange kicker; Operations shows no header.

## Targets and text

- [ ] Every tappable element is ≥ 44px in its smallest dimension (chips: 36px chip inside a 44px lane).
- [ ] No text below 10px; body copy is ≥ 13px.
- [ ] Every monetary value is tabular and never wraps; long names truncate with an ellipsis.
- [ ] Currency codes render as a separate muted suffix.

## Behaviour

- [ ] No `alert()`, `confirm()`, `prompt()`, or native `<select>` anywhere in the build.
- [ ] Every destructive action goes through the confirmation dialog and names its consequence.
- [ ] Every Save ends in the Saved dialog with a single "Done" button.
- [ ] Transactions chips filter the feed and hide group headers that empty out.
- [ ] Choosing a different account rewrites balance, available today, days left, opening balance and the currency suffix.
- [ ] Close period flips the right-hand card to "No period"; Start period flips it back.
- [ ] A Choose sheet opened from inside a sheet returns to that sheet, not to the screen.
- [ ] Switching tabs closes any open sheet.
- [ ] Spending above Available today remains valid; Save stays enabled and the
      recalculated allowance may be negative.
- [ ] Start/Edit period exposes the rollover checkbox, checked by default for
      `redistribute_remaining_days`.
- [ ] Plan item shows Edit rule, Skip, and Link transaction in one action row;
      Skip affects only that occurrence.
- [ ] Delete rule archives the rule without deleting linked transactions.
- [ ] Expected income labels its account field To account; expense kinds label
      it From account.
- [ ] Owner and Auto rate are visible as disabled Coming soon options.

## Content

- [ ] Every string matches `spec/06-content.md` exactly.
- [ ] Analytics ships the placeholder, with no charts added.
- [ ] Scan ships the placeholder, with no OCR.

## Motion and access

- [ ] Sheets animate ≤ 180ms and are fully readable in the first frame.
- [ ] `prefers-reduced-motion: reduce` removes all transforms without hiding content.
- [ ] Contrast: body text ≥ 4.5:1, muted meta ≥ 3:1 against its surface.
