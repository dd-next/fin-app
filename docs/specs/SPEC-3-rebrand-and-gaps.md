# SPEC-3 (v2) — Rebrand first, then features, then UI, then test cases

> Historical specification for the earlier product generation. The active v2
> specification is [`FinnApp-v2.md`](FinnApp-v2.md). All
> instructions below are archival and must not be executed.

Addendum to `SPEC.md` (as amended in PROGRESS.md). Conventions in `CLAUDE.md`
still apply. Phases 1–8 are done. Read PROGRESS.md first: the budget math was
reworked (daily base + carry-over + overspend rebase). Do not regress it.

**Priority is strict.** Do the phases below IN ORDER — most important first,
cosmetic last — and commit + update PROGRESS.md after each one, so that if the
session ends at any point, another agent can resume from PROGRESS.md with the
important work already done and nothing half-broken.

Current UI facts (so you don't re-implement what exists): expenses can already
be deleted via an ✕ control in the list; settings currently live in a
`<details>` dropdown; expense list is inline on the main screen.

**UI language: English ONLY.** Any Russian strings currently in the UI must be
replaced. All new UI copy is English.

---

## Phase 9 — FULL REBRAND (do this first, before anything else)

The project must contain ZERO references to the original app, in any language
or spelling: `tzlvt`, `Tzlvt`, `тяжеловато`, `Тяжеловато`, `tyazhelovato`,
`fuckgrechka`, `grechka` — in code, comments, docstrings, filenames, docs,
config, and test assertions.

New neutral name: **FinApp** (display "FinApp"; machine name `finapp`).

Required changes (then grep to catch the rest):
1. `app/db.py` + `alembic.ini` + `.env.example`: default DB
   `sqlite+aiosqlite:///./finapp.db`; Postgres example DB name `finapp`.
2. `app/main.py`: `FastAPI(title="FinApp")`.
3. `app/export.py`: `FILENAME = "finapp-export.xlsx"`; update the
   content-disposition assertion in `tests/test_export.py` and the download
   name in `app/static/app.js`.
4. `app/static/index.html`: `<title>FinApp — daily budget</title>`.
5. Comments/docstrings in `app/budget.py`, `app/static/app.js`,
   `app/static/style.css`, tests: replace phrasing like "the original app
   (Tzlvt)" with neutral wording ("the reference behavior").
6. `README.md`: retitle to "FinApp — minimalist daily-budget tracker", fix the
   DB filename mention.
7. `.claude/skills/verify/SKILL.md`: replace `tzlvt.db` with `finapp.db`.
8. Historical docs (`SPEC.md`, `SPEC-2-*.md`, `PROGRESS.md`): scrub mentions
   there too (reword; don't delete the documents).
9. **Existing data:** on startup, if `./finapp.db` does not exist and the old
   DB file does, rename it with one `os.replace` in `app/db.py` before engine
   creation (SQLite default URL only). Keep the old filename ONLY as a
   rename-source constant with a comment that it exists solely for migration —
   or skip the code entirely and document a manual `mv` in README. Choose one,
   record it in PROGRESS.md.

Acceptance: `grep -ri "tzlvt\|тяжелов\|grechka" .` (excluding `.git`) returns
nothing — or only the single migration constant if that route was chosen.
All existing tests green. Commit.

## Phase 10 — Income operations (±) + undo

### 10.1 Signed operations: income (top-ups)
Money can be ADDED mid-period, not only spent.

- Data model: generalize "expense" to **operation**. Keep the existing
  table/columns but add `kind: 'expense' | 'income'` via an Alembic migration
  (server default `'expense'` so existing rows stay valid). Amount stays
  positive; `kind` carries the sign.
- Budget math (`app/budget.py`): an income on day D increases the money pool
  from day D onward — feed signed amounts into the existing replay (expense
  = `+amount` spent, income = `-amount` spent). Carry-over / rebase semantics
  from PROGRESS.md keep working; income added today raises today's number
  immediately.
- API:
  - `POST /operations` body `{amount, kind, comment?}`; keep `POST /expenses`
    as a thin alias or drop it — record the choice in PROGRESS.md.
  - `GET /operations` → newest first, each with `kind`.
  - `DELETE /operations/{id}` — both kinds.
- Frontend: a **segmented toggle** next to the amount input with two states,
  `Expense | Income` (this is the UI switch between the two entry modes).
  Default Expense. Income mode is visually distinct (green accent). Submitting
  posts the right `kind`. Income rows in lists render green with a `+` prefix.
- Export/Sheets: add a "Type" column (expense/income); running balance must be
  correct with both kinds.
- Tests: unit — income today raises today's number; income after an overspent
  day; deleting an income recomputes correctly. API — /operations round-trip
  for both kinds.

### 10.2 Undo last operation
- After an operation is added, show an inline undo control:
  "‹ Undo {amount}" until the next action/refresh. It deletes that operation
  via the existing DELETE endpoint (targeting the just-created id) and
  refreshes. No new backend endpoint.

Commit at the end of the phase (10.1 and 10.2 may be separate commits).

## Phase 11 — Next-day savings decision ("Nice!" screen)

Reference behavior (from the original app): if the user open the app on a new
day and YESTERDAY ended with money left over, show a full-screen prompt before
the main screen:

> **Nice!**
> Yesterday you saved {saved}. Decide what to do with it.
>
> **Spend it all today** — {today_base + saved} instead of {today_base} today
> **Increase the daily budget** — {new_daily} instead of {today_base} per day

Semantics:
- "Spend it all today" = current default carry-over behavior (the leftover
  rolls onto today). Choosing it just acknowledges the prompt; numbers don't
  change from the current math.
- "Increase the daily budget" = re-spread: remaining money is redistributed
  evenly across the remaining days (a voluntary rebase, same mechanism as the
  overspend rebase but user-triggered), and the carry-over resets.

Implementation requirements:
- The decision must persist and affect the replay math deterministically.
  Suggested design: a `rebase_event(date)` record (new table or an operation
  kind `'rebase'` with amount 0 — pick one, record it); the replay in
  `budget.py` treats a rebase event on day D as "rebase the daily base to
  remaining/(days from D) and reset carry". Everything stays derived from
  stored records — no hidden state.
- Prompt visibility: the backend decides. `GET /savings-prompt` returns either
  `{show: false}` or `{show: true, saved, spend_today_value, increase_daily_value}`.
  Show when: a new calendar day has started since the last recorded
  acknowledgment AND yesterday ended with a positive leftover. Store the
  acknowledgment (e.g. `last_prompt_ack` date on the period or a small table)
  when either option is chosen via `POST /savings-decision {choice:
  "spend_today" | "increase_daily"}`.
- Frontend: on load, call `/savings-prompt` first; if `show`, render the
  full-screen prompt (big friendly headline, two option buttons with their
  computed numbers) before the main screen. Both choices call the decision
  endpoint and proceed to the main screen.
- Tests: unit — a rebase event mid-period produces the expected new daily
  base and resets carry; API — prompt appears exactly once per qualifying day,
  each choice persists and changes (or preserves) the numbers as specified.

## Phase 12 — UI restructure (English-only, navigation, buttons)

Consult the **frontend-design** skill before this phase. Buttons and
navigation must look deliberate and modern: consistent sizing and spacing,
clear hover/active/focus states, adequate tap targets (≥44px), one accent
color, no default-browser look.

1. **English-only sweep:** replace every non-English UI string.
2. **Expenses History as a separate view:** remove the inline list from the
   main screen. Add a clearly styled button **"Expenses History"** that opens
   a dedicated view (single-page section toggle is fine) listing ALL
   operations, newest first: amount (income green with `+`), optional comment,
   and a human timestamp ("Today, 13:10" style, English). Include a Back
   control. The ✕ delete stays on rows in this view.
   - **The "Export .xlsx" button moves INTO this history view** (it is no
     longer on the main screen).
3. **Budget Settings as a separate view:** replace the `<details>` dropdown
   with a styled button **"Budget Settings"** opening a dedicated view/modal
   with the period form (amount, start, end, Save/Cancel), plus:
   - live per-day preview under the amount while typing: "{amount/days} per
     day" (client-side, updates on input);
   - header summary on the main screen: "{total} for {N} days" with the
     settings affordance (the Budget Settings button or a gear) next to it.
4. **Spent-out state:** when `remaining_money <= 0` for the whole period, the
   main number area shows a big red **"Spent"** instead of numbers plus a link
   "Change amount and dates" opening Budget Settings. Adding an income must
   recover from this state.
5. Keep the layout responsive (narrow phone + wide desktop).

Out of scope: custom on-screen numeric keypad (native `inputmode="decimal"`
is fine), motivational quotes, version/credits footer.

## Phase 13 — Manual test cases + final pass

Create **`MANUAL_TEST_CASES.md`** in the repo root, written in **Russian**,
for a human to verify the app by hand. Derive it from the ACTUAL code after
phases 9–12 (real button labels, real endpoints, real behaviors).

Format per case:

    ### TC-NN — <короткое название>
    Предусловия: <состояние приложения/БД>
    Шаги: 1. … 2. … 3. …
    Ожидаемый результат: <что должно быть видно/происходить>

Must cover at least:
1. Первый запуск: пустое состояние, установка периода, шапка "{total} for {N} days".
2. Добавление траты: сегодняшний лимит падает, live-превью при вводе суммы.
3. Перерасход дня: ребейз "new daily budget · was X".
4. Пополнение: переключатель Expense|Income, зелёная запись, лимит вырос.
5. Undo: "‹ Undo {amount}" удаляет последнюю операцию, цифры возвращаются.
6. Экран "Nice!": накопить остаток за вчера, открыть на новый день, проверить
   оба варианта (Spend it all today / Increase the daily budget) и что промпт
   показывается ровно один раз.
7. Expenses History: кнопка открывает список, зелёные пополнения, метки
   времени, удаление ✕ с пересчётом, кнопка Export .xlsx внутри истории.
8. Budget Settings: кнопка открывает форму, live "{X} per day" при вводе,
   изменение суммы/сроков пересчитывает всё.
9. Состояние "Spent": потратить всё, увидеть состояние, восстановиться
   пополнением.
10. Экспорт .xlsx: скачивается под именем finapp-export.xlsx, обе вкладки,
    колонка Type, running balance корректен с пополнениями.
11. БД: старый файл подхватывается/мигрирует как описано в README; свежая
    установка создаёт `finapp.db`.
12. `/health` отвечает `{"status":"ok"}`.
13. (если включён Sheets) ручной `POST /sheets/sync` и авто-синк после операции.
14. Адаптивность: узкий (телефон) и широкий (десктоп) вьюпорт.
15. UI полностью на английском (ни одной русской строки).

Also in this phase: README updated (new name, new features, migration note),
full test suite run, acceptance criteria re-checked.

---

## Resumability reminder

After EVERY phase: tests green → PROGRESS.md updated (checkbox, 2–4 lines,
test counts, decisions) → git commit. Add Phase 9–13 checkboxes to PROGRESS.md
at the start. If blocked, write it under "Blocked" in PROGRESS.md, commit, and
stop cleanly.
