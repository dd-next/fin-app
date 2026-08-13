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

## Phase 15 implementation resolutions

These owner-approved fast-track resolutions remove ambiguities between the
exported source, the written handoff, and the accepted Phase 14 API without
changing financial semantics:

- Plan follows `specs/FinnApp-v2.md` §8: one card per rule with only its nearest
  overdue and nearest future occurrence. The older global `UPCOMING` list in
  mobile spec §3.4 is superseded. Plan's screen-header affordance is the accent
  `+`; Accounts and Analytics use the avatar.
- Mobile top chips use the unified `/api/v1/transaction-feed`. The advanced
  Filters sheet uses the existing persisted `/api/v1/transactions` contract;
  while advanced filters are active it shows persisted ledger rows only.
  Selecting a top chip clears advanced filters and returns to the unified feed,
  so Planned is never approximated from one client-side page.
- Account-details `Full history` opens account-filtered Transactions. Period
  history remains reachable from Operations.
- A shared/non-owner account renders one non-actionable `No period` state and
  never requests owner-private period endpoints; the UI must not reveal
  whether its owner has a period.
- The device/browser software keyboard is the shipped input mechanism. The
  250px keyboard drawing is the reference visual-viewport acceptance state,
  not a custom keyboard to implement. Operations must remain usable when the
  real keyboard occupies that budget.
- The accepted persistent Undo contract remains visible on mobile even though
  the exported screen omitted it. When a server candidate exists, a compact
  44×44 Undo affordance occupies the account card's top row without changing
  either 96px card height; account switching remains a separate semantic
  control. Undo uses branded confirmation, then disappears without falling
  back to an older candidate, including after reload.
- Reference browser checks inject 54px top and 34px bottom safe-area test
  variables because desktop headless browsers report zero for `env(safe-area-
  inset-*)`; production CSS continues to use the real environment insets.
- Mobile account archive copy ends after `History is kept.` and never promises
  restoration.

## Tokens

The handoff tokens are supplied in `Finnapp mobile
specification/design-tokens.json` and `tokens.css`. Phase 15 imports only the
tokens the application uses into `app/static/`; raw handoff files are not
runtime dependencies.

T-023 imports only the shell tokens currently used at runtime: background
`#0B0D10`, primary text `#E7EAEE`, idle tab `#6B7482`, accent `#FFA24B`,
hairline `rgba(255,255,255,.07)`, and the 56px tab-bar height. Production safe
areas come from `env(safe-area-inset-top/bottom, 0px)` through
`--mobile-safe-top` and `--mobile-safe-bottom`; browser acceptance may inject
the reference bands with `--test-safe-top: 54px` and
`--test-safe-bottom: 34px`.

At widths up to 640px the authenticated shell occupies the visual viewport
between the top safe area and the bottom tab/safe-area bands. It declares a
`100vh` fallback before `100dvh`, contains horizontal overflow, and makes its
content vertically reachable without allowing the fixed 56px tab bar to cover
it. The desktop shell remains under the pre-existing selectors. Primary tabs
use the frozen order and symbols, expose `aria-current="page"`, and retain the
current URL-backed view switch without adding a data refresh. Mobile uses the
approved system font stack and an inset accent focus ring so keyboard focus is
fully visible inside the clipped tab-bar boundary.

T-024A imports the remaining primitive tokens currently exercised by production
DOM: surface `#151A21` with `rgba(255,255,255,.08)`, field `#101419` with
`rgba(255,255,255,.12)`, neutral control `#232A33`, secondary text `#C9D0D9`,
muted text `#8A93A0`, hint/chevron text `#5F6875`/`#4A525E`, positive/negative
`#6EE7A8`/`#FF7B7B`, accent tint/focus, danger surfaces, and destructive
`#7A2F35` on `#FFD9D9`. These tokens and all `.mobile-*` geometry remain inside
the 640px runtime boundary.

The shared primitive contract uses one-surface Accounts and Plan metric strips
(72px and 64px), 44px screen/group controls, 64px whole-button account rows,
56px ghost rows, 96px account/period cards in both active and absent states,
and a 44px four-way segmented control. The no-period card keeps a 44px semantic
Start target around its 36px visual button. Form, sheet, amount/error, chip,
and primary/secondary/inline/destructive classes expose the frozen component
geometry without introducing overlays or changing workflows; later owning
tasks compose them and remove interim native controls.

Money presentation remains string based: existing asset precision feeds
separate escaped value and muted currency-code spans with tabular, non-wrapping
numerals. No float conversion is introduced. Long row text truncates, and the
compact Operations balance is updated from the selected account while its
desktop-only legacy controls remain unchanged. Shared/non-owner period privacy
continues to rely on the accepted owner guard and generic `No period` state.

T-024B adds one mobile overlay root and controller outside the inert application
content. It owns a stack of sheets and confirmations, records the root and
immediate openers, traps focus in the active panel, restores focus on pop/close,
and closes the full stack when a primary tab changes. Scrim, close, Escape and
Cancel only dismiss; confirmed asynchronous actions are guarded so they run at
most once. Callers construct option and copy nodes from already-authorized data;
the controller performs no API or financial work.

The production exercise is the Operations account field: mobile opens a Choose
sheet while desktop retains the existing native select and its unchanged event
path. Choose options expose the current value and reject disabled entries. The
same controller supports cancel+accent, cancel+destructive and one-button Saved
confirmations. Overlay motion is 180ms and becomes transform-free under reduced
motion. While an overlay is active, the fixed tab bar is raised above the scrim
so a physical tab tap can close the stack; the sheet safe band and confirmation
bottom clearance grow by the tab-bar height so options/actions remain reachable.

T-025A composes the mobile Accounts surface from the accepted summary contract:
one 72px capital strip, the conditional 44px missing-rate entry point, and
exact `CASH`, `BANK`, `CRYPTO` groups with 64px rows and a 56px New account row.
Cash storage maps to CASH; crypto assets and crypto/exchange storage map to
CRYPTO; every other visible account maps to BANK. Values remain summary-derived
and money keeps separate non-wrapping value/code spans. Account details,
Add/Edit, Reconcile, Archive, recent history and account-filtered Full history
reuse accepted APIs and one overlay stack; denied actions are absent. Archive
ends at `History is kept.` and exposes no restore control. Desktop keeps its
existing cards and dialogs.

## Change log

One line per landed design change: date, what changed, why.

- 2026-08-09 — registered the frozen mobile source hierarchy and linked the
  backend gap audit; no design asset changed.
- 2026-08-12 — recorded the Phase 15 fast-track resolutions for Plan, unified
  versus advanced Transactions filters, history navigation, shared periods,
  software-keyboard/Undo acceptance, safe-area measurement, and archive copy.
- 2026-08-12 — imported the minimal runtime shell tokens, safe-area geometry,
  and accessible five-tab mobile navigation for T-023 while preserving the
  desktop shell and existing view-loading behavior.
- 2026-08-12 — imported the T-024A mobile primitive tokens and production DOM
  contracts for headers, rows, metric strips, Operations cards and controls,
  fields, buttons, truncation, and precision-safe money presentation while
  preserving the accepted desktop and financial workflows.
- 2026-08-13 — added the single accessible T-024B mobile overlay stack, Choose
  and confirmation contracts, physical tab-close path, reduced-motion behavior,
  and desktop-preserving Operations account integration.
- 2026-08-13 — composed T-025A mobile Accounts, summary-only group/value rules,
  account lifecycle sheets, Saved/error states and filtered history while
  retaining desktop dialogs and the accepted backend contract.
- 2026-08-13 — composed T-028 mobile Plan as bounded rule cards with nearest
  occurrences, adapter-backed rule/item/link sheets and archive consequences;
  shipped the exact data-free Analytics placeholder and retained desktop Plan.
