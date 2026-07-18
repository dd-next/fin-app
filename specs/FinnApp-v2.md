# FinApp v2 — основная спецификация

Статус: **активная и обязательная для линии разработки FinApp v2**.

Этот документ заменяет продуктовые ограничения `SPEC.md` и его addenda. Старые
спецификации остаются историей реализованных версий. При любом конфликте этот
документ имеет приоритет.

## 1. Идея и граница первого релиза

FinApp v2 — web-приложение для управления всеми счетами пользователя,
операциями, ожидаемыми доходами и расходами, а также ежедневным бюджетом.

Основная навигация:

```text
Accounts     → где находятся деньги
Transactions → что происходило с деньгами
Tracker      → сколько можно потратить в текущем периоде
Plan         → какие доходы и расходы ожидаются
Analytics    → заглушка будущих отчётов
```

В первый релиз входят:

- открытая регистрация и личное финансовое пространство;
- фиатные и криптовалютные активы;
- наличные, банковские, карточные, электронные, биржевые и криптосчета;
- расходы, доходы, переводы, обмены и корректировки;
- непривязанные к счёту операции;
- общий капитал и доступная для трат сумма;
- расшаривание отдельных счетов с разными правами;
- категории;
- ожидаемые доходы, обязательные расходы, подписки и переводы в резерв;
- история всех периодов и существующая механика ежедневного бюджета.

Не входят в первый релиз:

- crypto/blockchain sync и биржевые API;
- внешние провайдеры курсов;
- банковские API;
- полноценная аналитика;
- XLSX и Google Sheets;
- Telegram Mini App;
- savings goals как отдельная сущность;
- category limits и budget pools.

Базовый принцип:

> Балансы и финансовые итоги рассчитываются из единого журнала движений. Они
> не хранятся как вручную редактируемые агрегаты.

---

# 2. Пользователь и финансовое пространство

## User

```text
User
- id
- username
- normalized_username
- display_name
- password_hash
- timezone
- is_active
- created_at
- updated_at
```

Регистрация открытая. После регистрации пользователь получает личный
`Workspace` и становится его владельцем.

## AuthSession

```text
AuthSession
- id
- user_id
- token_hash
- created_at
- expires_at
- last_seen_at
- revoked_at
```

Сессия хранится на сервере, а клиент получает opaque HttpOnly cookie.

## Workspace

`Workspace` — личный финансовый контур пользователя. План, Трекер, категории и
периоды принадлежат ему.

```text
Workspace
- id
- owner_user_id
- name
- base_asset_id
- timezone
- created_at
- archived_at
```

В первом релизе shared workspace не нужен. Совместный доступ предоставляется к
отдельным счетам.

---

# 3. Активы и точность

## Asset

```text
Asset
- id
- code
- name
- kind
- decimals
- is_active
```

`kind`:

```text
fiat
crypto
```

Стартовый справочник:

```text
VND  — fiat   — 0
USD  — fiat   — 2
RUB  — fiat   — 2
EUR  — fiat   — 2
USDT — crypto — 6
BTC  — crypto — 8
ETH  — crypto — 18
TRX  — crypto — 6
```

Правила:

- суммы и курсы всегда `Decimal`, никогда `float`;
- хранилище поддерживает до 38 цифр и до 18 знаков после запятой;
- входная сумма не может иметь больше знаков, чем `Asset.decimals`;
- отображение и округление используют точность конкретного актива.

---

# 4. Счета

## Account

`Account` — одно место хранения одного актива.

```text
Account
- id
- workspace_id
- owner_user_id
- name
- storage_type
- purpose
- asset_id
- institution
- include_in_available
- created_at
- updated_at
- archived_at
```

`storage_type`:

```text
cash
bank
card
e_wallet
crypto_wallet
exchange
virtual
```

`purpose`:

```text
spending
reserve
savings
investment
```

Примеры:

- Cash VND;
- Vietcombank VND;
- T-Bank RUB;
- Bybit USDT;
- Trust Wallet TRX;
- Emergency Fund USD.

Баланс:

```text
account_balance = sum(posted TransactionLeg.amount for account)
```

Начальная сумма создаётся как `adjustment`. Сверка баланса также создаёт
корректирующую операцию; прямого изменения balance нет.

Два итога:

```text
Net worth → все активные видимые счета с известной оценкой
Available → только счета с include_in_available = true
```

Резервный счёт остаётся частью капитала, но может не входить в Available.

---

# 5. Расшаривание счёта

## AccountAccess

```text
AccountAccess
- id
- account_id
- user_id
- role
- created_at
```

Роли:

```text
owner       — все операции, настройки счёта и управление доступом
editor      — просмотр, операции и редактирование счёта
contributor — просмотр и добавление расходов
viewer      — только просмотр
```

## AccountInvitation

```text
AccountInvitation
- id
- account_id
- created_by_user_id
- role
- token_hash
- created_at
- expires_at
- accepted_at
- accepted_by_user_id
```

Процесс:

1. Владелец выбирает роль и создаёт одноразовую ссылку.
2. Получатель входит или регистрируется.
3. Принятие ссылки создаёт `AccountAccess`.
4. Повторно использовать или принять просроченную ссылку нельзя.

Приглашённый пользователь видит только расшаренный счёт и связанные с ним
движения. План, Трекер, другие счета и агрегаты владельца не раскрываются.

Для multi-account операции права проверяются на каждом счёте. Если пользователь
видит только часть операции, недоступные движения скрываются, а ответ содержит
`has_hidden_legs = true`. Изменить или отменить такую операцию нельзя без прав
редактирования на все её счета.

---

# 6. Единый журнал операций

## Transaction

`Transaction` описывает смысл финансового события.

```text
Transaction
- id
- workspace_id
- created_by_user_id
- type
- category_id
- budget_period_id
- plan_occurrence_id
- parent_transaction_id
- counterparty
- note
- occurred_at
- local_date
- source
- status
- external_id
- base_amount
- base_rate
- rate_source
- created_at
- updated_at
- voided_at
```

`type`:

```text
expense
income
transfer
exchange
adjustment
```

`source`:

```text
manual
planned
```

`status`:

```text
posted
unassigned
voided
```

`base_amount` — зафиксированный эквивалент в базовом активе периода. Он нужен
только когда операция влияет на Трекер. Последующее изменение текущего курса не
переписывает историю периода.

## TransactionLeg

```text
TransactionLeg
- id
- transaction_id
- account_id
- asset_id
- amount
```

Сумма знаковая:

```text
+100 → деньги пришли
-100 → деньги ушли
```

`account_id` может быть пустым у расхода или дохода. Такая операция:

- видна владельцу в Transactions и Tracker;
- влияет на бюджет, если связана с периодом;
- не влияет на баланс конкретного счёта;
- позже может быть привязана к счёту с тем же активом.

Публичный API не удаляет posted-транзакции физически. Отмена переводит их в
`voided`, после чего все производные суммы пересчитываются.

## Category

```text
Category
- id
- workspace_id
- name
- normalized_name
- kind
- icon
- color
- created_at
- archived_at
```

`kind`: `expense`, `income` или `both`. Использованная категория архивируется,
а не удаляется.

---

# 7. Реальные операции

## Расход

```text
Transaction: expense
Cash VND: -500,000
```

## Доход

```text
Transaction: income
Vietcombank VND: +21,033,600
```

## Внутренний перевод

```text
Transaction: transfer
Vietcombank VND: -5,000,000
Cash VND:        +5,000,000
```

Перевод не считается расходом и не меняет общий капитал.

## Обмен активов

```text
Transaction: exchange
Bybit USDT:      -800
Vietcombank VND: +21,033,600
```

Фактический курс:

```text
1 USDT = 26,292 VND
```

Пользователь вводит обе реальные суммы. Backend рассчитывает и сохраняет курс.

## Комиссия

Комиссия создаётся отдельным `expense`, связанным с обменом через
`parent_transaction_id`. Поэтому обмен не является расходом, а комиссия является.

## Перевод другому человеку

Если второй счёт не принадлежит тому же финансовому контуру, операция является
расходом с `counterparty`, а не внутренним transfer.

## Перевод в резерв

```text
Transaction: transfer
Main USD:           -200
Emergency Fund USD: +200
```

Капитал не меняется. Available уменьшается, если резервный счёт исключён.

---

# 8. Курсы и оценка капитала

## ExchangeRate

```text
ExchangeRate
- id
- source_transaction_id
- base_asset_id
- quote_asset_id
- rate
- captured_at
```

Правила первого релиза:

- курс создаётся только из posted-операции `exchange`;
- сохраняются прямое и обратное направление пары;
- текущий итог использует последний прямой или обратный курс к выбранному
  базовому активу;
- цепочки через третий актив не строятся;
- void или исправление обмена исключает или заменяет его курс;
- актив без курса показывается отдельной строкой `Unvalued` и не входит в
  пересчитанный итог.

Если расход или доход в другой валюте должен попасть в Трекер:

1. Backend использует последний известный курс пары.
2. Если его нет, UI просит эквивалент в базовом активе периода.
3. Получившийся `base_amount` фиксируется на транзакции.

---

# 9. План

План хранит будущие события и не меняет реальные балансы до появления
фактической транзакции.

## PlanRule

```text
PlanRule
- id
- workspace_id
- created_by_user_id
- kind
- name
- amount
- asset_id
- recurrence
- first_due_date
- category_id
- default_from_account_id
- default_to_account_id
- is_required
- is_active
- created_at
- updated_at
```

`kind`:

```text
income
required_expense
subscription
reserve_transfer
other_expense
```

`recurrence`:

```text
once
weekly
monthly
yearly
```

`first_due_date` является якорем повторения. Для отсутствующего числа в коротком
месяце используется последний день месяца.

## PlanOccurrence

```text
PlanOccurrence
- id
- plan_rule_id
- due_date
- planned_amount
- status
- transaction_id
- matched_at
- created_at
```

`status`:

```text
planned
completed
skipped
overdue
```

События материализуются идемпотентно на 12 месяцев вперёд при создании,
изменении или чтении правила. Уникальность: `plan_rule_id + due_date`.

Факт всегда подтверждается пользователем:

- `pay` или `receive` создаёт обычную транзакцию;
- `link` связывает уже существующую транзакцию;
- `skip` пропускает occurrence;
- одно событие нельзя выполнить дважды.

После получения планового дохода приложение предлагает новый период от даты
получения до дня перед следующим ожидаемым доходом. Если следующего дохода нет,
пользователь обязан выбрать end date. Создание требует подтверждения.

---

# 10. Трекер и периоды

## BudgetPeriod

```text
BudgetPeriod
- id
- workspace_id
- created_by_user_id
- start_date
- end_date
- base_asset_id
- funding_amount
- opening_transaction_id
- opening_plan_occurrence_id
- prompt_ack_date
- created_at
- closed_at
```

Статус `upcoming`, `current` или `ended` рассчитывается по датам и timezone.
Периоды одного workspace не пересекаются и сохраняются навсегда.
Новая операция в естественно завершённом периоде требует явного подтверждения;
явно закрытый период новые операции не принимает. Подтверждённые исправления
истории допустимы, но границы периода нельзя изменить так, чтобы связанные
операции или snapshots обязательств оказались вне него.

`opening_transaction_id` не участвует в replay второй раз: её сумма уже
представлена в `funding_amount`.

## BudgetCommitment

```text
BudgetCommitment
- id
- budget_period_id
- plan_occurrence_id
- type
- name
- planned_amount
- status
- created_at
- updated_at
```

`type`:

```text
required_expense
reserve_transfer
```

`status`:

```text
reserved
fulfilled
cancelled
```

Эффективная сумма обязательства:

```text
reserved  → planned_amount
fulfilled → фактический base_amount связанной транзакции
cancelled → 0
```

Формула стартового ежедневного пула:

```text
daily_pool = funding_amount - sum(effective commitments)
```

Связанная фактическая транзакция исключается из обычных daily expenses. Поэтому
равная плану аренда не уменьшает дневной бюджет второй раз; отклонение от плана
увеличивает или уменьшает доступный пул на точную разницу.

## RebaseEvent

```text
RebaseEvent
- id
- budget_period_id
- day
- reason
- created_at
```

`app/budget.py` остаётся чистым модулем и сохраняет существующую механику:

- сумма делится на календарные дни включительно;
- трата сегодня уменьшает сегодняшний остаток 1:1;
- неиспользованный остаток переносится;
- перерасход пересчитывает базу следующих дней;
- отрицательные значения не обрезаются в API;
- live preview показывает результат ещё не сохранённой траты;
- next-day prompt позволяет оставить перенос на сегодня или распределить его;
- edit/void всегда вызывает полный детерминированный replay.

Точность отображения Трекера соответствует `base_asset_id` периода.

---

# 11. Права и видимость

Матрица действий со счётом:

```text
Action                         owner editor contributor viewer
View account and its legs       yes    yes      yes       yes
Add expense                     yes    yes      yes       no
Add income                      yes    yes      no        no
Transfer or exchange            yes    yes*     no        no
Edit or void transaction        yes    yes*     no        no
Edit account metadata           yes    yes      no        no
Reconcile/archive account       yes    no       no        no
Manage access                   yes    no       no        no
```

`yes*` требует edit-доступ на каждый счёт операции.

Дополнительно:

- unassigned-транзакцию видят её создатель и владелец workspace;
- contributor обязан выбрать расшаренный счёт и может создать только expense;
- категории workspace доступны shared-пользователю для выбора, но изменять их
  может только владелец workspace;
- shared-расход автоматически связывается с текущим периодом владельца, если
  дата входит в него, но сам Трекер приглашённому не показывается.

---

# 12. HTTP API

Префикс: `/api/v1`. JSON везде. `/health` остаётся публичным.

## Auth и workspace

```text
POST  /api/v1/auth/register
POST  /api/v1/auth/login
POST  /api/v1/auth/logout
GET   /api/v1/auth/me

GET   /api/v1/workspaces
GET   /api/v1/workspaces/{id}
PATCH /api/v1/workspaces/{id}
```

## Assets и категории

```text
GET   /api/v1/assets
POST  /api/v1/assets

GET   /api/v1/workspaces/{workspace_id}/categories
POST  /api/v1/workspaces/{workspace_id}/categories
PATCH /api/v1/workspaces/{workspace_id}/categories/{id}
POST  /api/v1/workspaces/{workspace_id}/categories/{id}/archive
```

## Accounts и доступ

```text
POST   /api/v1/accounts
GET    /api/v1/accounts
GET    /api/v1/accounts/summary
GET    /api/v1/accounts/{id}
PATCH  /api/v1/accounts/{id}
POST   /api/v1/accounts/{id}/reconcile
POST   /api/v1/accounts/{id}/archive

GET    /api/v1/accounts/{id}/access
POST   /api/v1/accounts/{id}/invitations
POST   /api/v1/account-invitations/{token}/accept
PATCH  /api/v1/accounts/{id}/access/{user_id}
DELETE /api/v1/accounts/{id}/access/{user_id}
```

`GET /accounts` возвращает owned и shared-счета текущего пользователя.
`GET /accounts/summary` агрегирует только видимые счета и отдельно возвращает
`unvalued` по активам.

## Transactions

```text
POST /api/v1/transactions/expense
POST /api/v1/transactions/income
POST /api/v1/transactions/transfer
POST /api/v1/transactions/exchange
POST /api/v1/transactions/adjustment

GET   /api/v1/transactions
GET   /api/v1/transactions/{id}
PATCH /api/v1/transactions/{id}
POST  /api/v1/transactions/{id}/void
POST  /api/v1/transactions/{id}/assign-account
POST  /api/v1/transactions/{id}/link-plan

GET /api/v1/exchange-rates
```

Фильтры списка:

```text
workspace_id
account_id
date_from
date_to
type
category_id
source
status
created_by_user_id
cursor
limit
```

Frontend отправляет команды предметной области, а не собирает legs вручную.

## Plan

```text
POST  /api/v1/workspaces/{workspace_id}/plan-rules
GET   /api/v1/workspaces/{workspace_id}/plan-rules
PATCH /api/v1/workspaces/{workspace_id}/plan-rules/{id}
POST  /api/v1/workspaces/{workspace_id}/plan-rules/{id}/archive

GET  /api/v1/workspaces/{workspace_id}/plan-occurrences
POST /api/v1/workspaces/{workspace_id}/plan-occurrences/{id}/pay
POST /api/v1/workspaces/{workspace_id}/plan-occurrences/{id}/receive
POST /api/v1/workspaces/{workspace_id}/plan-occurrences/{id}/skip
POST /api/v1/workspaces/{workspace_id}/plan-occurrences/{id}/link-transaction
```

## Tracker

```text
POST  /api/v1/workspaces/{workspace_id}/budget-periods/preview
POST  /api/v1/workspaces/{workspace_id}/budget-periods
GET   /api/v1/workspaces/{workspace_id}/budget-periods
GET   /api/v1/workspaces/{workspace_id}/budget-periods/current
GET   /api/v1/workspaces/{workspace_id}/budget-periods/{id}
PATCH /api/v1/workspaces/{workspace_id}/budget-periods/{id}
POST  /api/v1/workspaces/{workspace_id}/budget-periods/{id}/close

POST   /api/v1/workspaces/{workspace_id}/budget-periods/{id}/commitments
PATCH  /api/v1/workspaces/{workspace_id}/budget-commitments/{id}
DELETE /api/v1/workspaces/{workspace_id}/budget-commitments/{id}

GET  /api/v1/workspaces/{workspace_id}/tracker/today
GET  /api/v1/workspaces/{workspace_id}/tracker/preview?pending={amount}
GET  /api/v1/workspaces/{workspace_id}/tracker/savings-prompt
POST /api/v1/workspaces/{workspace_id}/tracker/savings-decision
```

Mutation responses возвращают обновлённые производные итоги. Ошибки доступа:
`401` без сессии, `403` при известном объекте без нужного действия, `404` для
недоступных чужих объектов, чтобы не раскрывать их существование.

---

# 13. Frontend

Одна responsive SPA без build step. UI полностью English.

## Accounts

- Net worth и Available;
- unvalued assets;
- группировка Cash, Banks, Crypto, Savings;
- создание, редактирование, reconcile, archive;
- история счёта и sharing.

## Transactions

- общий список и фильтры;
- формы expense, income, transfer, exchange, adjustment;
- category, account, date, comment, counterparty;
- edit, void, assign account и link to Plan;
- понятное отображение redacted legs.

## Tracker

- текущий и исторические периоды;
- today allowance, spent, remaining, commitments;
- quick expense и live preview;
- proposal после income;
- next-day savings decision;
- ended-period correction confirmation.

## Plan

- upcoming income;
- required expenses;
- subscriptions;
- reserve transfers;
- overdue;
- plan-vs-actual и действия pay/receive/skip/link.

## Analytics

Только стабильная заглушка `Coming soon`. API аналитики в первый релиз не входит.

Settings, profile и logout находятся в отдельном меню. Основные tap targets не
меньше 44px. Обязательны phone и desktop layouts.

---

# 14. Главные инварианты

1. Баланс счёта равен сумме posted legs.
2. Void полностью исключает движения и производные курсы.
3. Внутренний transfer не меняет общий капитал и не считается расходом.
4. Exchange использует обе фактические суммы и не считается расходом.
5. Комиссия является отдельным expense.
6. Перевод третьему лицу является expense.
7. Резервный transfer не является expense.
8. Unassigned-операция не меняет account balance.
9. Available исключает защищённые счета, Net worth — нет.
10. Исторический base amount не меняется из-за нового курса.
11. Актив без курса не попадает в пересчитанный итог и явно показывается.
12. Shared user не получает План, Трекер или чужие balances.
13. Права проверяются на всех legs multi-account операции.
14. Все периоды сохраняются и не пересекаются.
15. Opening income не учитывается в периоде дважды.
16. Fulfilled commitment заменяет плановую сумму фактической без двойного расхода.
17. Полный replay после edit/void даёт тот же результат, что расчёт с нуля.
18. Повторная генерация occurrences не создаёт дубликаты.
19. UTC-время и local financial date хранятся отдельно.
20. Точность актива не теряется ни в DB, ни в API.

---

# 15. Критерии готовности первого релиза

1. Пользователь регистрируется, входит и получает личный workspace.
2. Можно создать счета разных типов и активов с точным opening balance.
3. Expense, income, transfer, exchange и adjustment дают правильные balances.
4. Net worth, Available и unvalued assets вычисляются правильно.
5. Операции фильтруются, исправляются, void-ятся и позднее привязываются к счёту.
6. Счёт расшаривается по одноразовой ссылке с соблюдением четырёх ролей.
7. Приглашённый не видит никакие другие финансовые данные владельца.
8. План поддерживает все виды и recurrence из раздела 9.
9. Полученный доход предлагает период, но требует подтверждения.
10. Трекер сохраняет текущую daily-budget механику и историю.
11. Обязательный расход не уменьшает daily pool дважды.
12. Analytics отображается как заглушка.
13. Свежая БД создаётся через Alembic без внешних сервисов.
14. Полный pytest, JS syntax check и scratch-browser проверки проходят.
15. README позволяет установить, запустить и протестировать приложение в
    нескольких командах.
