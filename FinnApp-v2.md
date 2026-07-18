# FinApp v2 — все счета, планирование и ежедневный трекер

## 1. Идея продукта

FinApp — приложение для управления всеми деньгами пользователя в одном месте.

Основные разделы:

```text
Счета → где находятся деньги и сколько их сейчас
Транзакции → что происходило с деньгами
Трекер → сколько можно потратить в текущем периоде
План → какие доходы и расходы ожидаются
Аналитика → сколько пришло, ушло и осталось
```

Приложение должно поддерживать:

- фиатные и криптовалютные счета;
- наличные, карты, банки, кошельки и биржи;
- личные и общие счета;
- ручные и импортированные операции;
- историю всех бюджетных периодов;
- плановые доходы, обязательные расходы и подписки;
- общий баланс и доступную для трат сумму;
- несколько пользователей с разными правами.

Базовый принцип:

> Балансы, расходы и аналитика рассчитываются из единого журнала операций. Они не хранятся как вручную редактируемые итоговые числа.

---

# 2. Пользователи и совместный доступ

## User

```text
User
- id
- username
- password_hash
- display_name
- timezone
- created_at
```

## Workspace

`Workspace` — финансовое пространство одного пользователя, пары или семьи.

```text
Workspace
- id
- name
- base_asset_id
- owner_user_id
- created_at
```

`base_asset_id` определяет валюту, в которой показывается общий итог, например USD или VND.

## WorkspaceMember

```text
WorkspaceMember
- id
- workspace_id
- user_id
- role
- joined_at
```

Роли:

```text
owner       — всё, включая приглашения и права
editor      — просмотр и полное редактирование финансовых данных
contributor — просмотр и добавление трат, без изменения чужих операций
viewer      — только просмотр
```

## Invitation

```text
Invitation
- id
- workspace_id
- invited_by_user_id
- invitee_email
- role
- token
- expires_at
- accepted_at
```

## AccountAccess

По умолчанию участник видит счета рабочего пространства. Отдельный счёт можно ограничить или расшарить конкретному пользователю.

```text
AccountAccess
- id
- account_id
- user_id
- role
- created_at
```

Права на счёт используют те же уровни: `owner`, `editor`, `contributor`, `viewer`.

---

# 3. Активы и счета

## Asset

`Asset` описывает, в чём выражена сумма.

```text
Asset
- id
- code
- name
- kind
- decimals
```

`kind`:

```text
fiat
crypto
```

Примеры:

```text
VND  — fiat  — 0 decimals
USD  — fiat  — 2 decimals
USDT — crypto — 6 decimals
BTC  — crypto — 8 decimals
ETH  — crypto — 18 decimals
```

Все суммы хранятся как `Decimal`. Точность определяется активом.

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
- include_in_total
- is_archived
- created_at
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

`include_in_total = false` исключает счёт из доступной суммы сверху экрана. Это подходит для подушки, накоплений или денег, которые пользователь не хочет учитывать как доступные для трат.

При этом приложение может отдельно показывать:

```text
Общий капитал       — все активные счета
Доступно            — только счета с include_in_total = true
```

Баланс счёта не редактируется напрямую:

```text
account_balance = сумма всех TransactionLeg по счёту
```

Начальный баланс создаётся технической операцией `adjustment`.

## ExchangeRate

Нужен для пересчёта разных активов в базовую валюту рабочего пространства.

```text
ExchangeRate
- id
- base_asset_id
- quote_asset_id
- rate
- source
- captured_at
```

Если актуального курса нет, приложение показывает баланс самого счёта, но помечает, что он не вошёл в общий пересчитанный итог.

---

# 4. Единый журнал операций

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
- created_at
- updated_at
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
imported
planned
```

`status`:

```text
posted      — операция учтена
unassigned  — операция пока не привязана к счёту
pending     — внешняя операция ещё не подтверждена
voided      — операция отменена, но сохранена в истории
```

## TransactionLeg

`TransactionLeg` показывает изменение конкретного счёта.

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
+100 — деньги пришли
-100 — деньги ушли
```

`account_id` может быть пустым. Такая операция:

- видна в Транзакциях и Трекере;
- влияет на бюджет периода и аналитику;
- не влияет на баланс конкретного счёта;
- позже может быть привязана к счёту пользователем.

`asset_id` обязателен всегда, поэтому сумма непривязанной операции остаётся однозначной.

## Category

```text
Category
- id
- workspace_id
- name
- kind
- icon
- color
- is_archived
```

`kind`:

```text
expense
income
both
```

Категорию, комментарий, дату, счёт и связь с планом можно изменить после создания операции.

---

# 5. Примеры операций

## Покупка

```text
Transaction: expense, category = restaurants
Cash VND: -500,000
```

Баланс счёта и общий капитал уменьшаются.

## Внутренний перевод

```text
Transaction: transfer
Vietcombank VND: -5,000,000
Cash VND:        +5,000,000
```

Общий капитал не меняется, операция не считается расходом.

## Обмен USDT на VND

```text
Transaction: exchange
Bybit USDT:      -100
Vietcombank VND: +2,600,000
```

Фактический курс определяется из двух движений. Комиссия оформляется отдельным расходом, связанным через `parent_transaction_id`.

## Перевод другому человеку

Если получатель не является управляемым счётом пользователя, это расход:

```text
Transaction: expense
Bank RUB: -10,000
counterparty: Mother
```

## Перевод в подушку

```text
Transaction: transfer
Main USD:           -200
Emergency Fund USD: +200
```

Общий капитал не меняется. Доступная сумма уменьшается, если Emergency Fund исключён из неё.

---

# 6. Раздел «Счета»

Экран показывает:

- общий капитал в базовой валюте;
- доступную сумму без исключённых счетов;
- счета по группам: наличные, банки, крипто, накопления;
- баланс каждого счёта в его активе;
- последнюю дату обновления подключённого счёта.

Основные действия:

- создать счёт;
- изменить название, тип и назначение;
- исключить или вернуть счёт в доступную сумму;
- скорректировать баланс через `adjustment`;
- открыть историю счёта;
- настроить синхронизацию;
- расшарить счёт;
- архивировать счёт.

---

# 7. Раздел «Транзакции»

Здесь отображается единая история всех операций.

Фильтры:

```text
счёт
период дат
тип операции
категория
источник
статус
автор
```

Действия:

- добавить расход, доход, перевод, обмен или корректировку;
- изменить операцию;
- отменить операцию без физического удаления истории;
- привязать непривязанную операцию к счёту;
- изменить категорию и комментарий импортированной операции;
- связать фактическую операцию с пунктом Плана.

---

# 8. Раздел «План»

План хранит будущие доходы и расходы. Он не меняет реальные балансы, пока не появилась фактическая операция.

## PlanRule

`PlanRule` — разовое или повторяющееся правило.

```text
PlanRule
- id
- workspace_id
- created_by_user_id
- direction
- kind
- name
- amount
- asset_id
- recurrence
- first_due_date
- due_day
- category_id
- default_account_id
- is_required
- is_active
- created_at
```

`direction`:

```text
income
expense
```

`kind`:

```text
income
required_expense
subscription
rent
communication
savings
other
```

`recurrence`:

```text
once
weekly
monthly
yearly
```

## PlanOccurrence

`PlanOccurrence` — конкретное ожидаемое событие на дату.

```text
PlanOccurrence
- id
- plan_rule_id
- due_date
- planned_amount
- status
- transaction_id
- matched_at
```

`status`:

```text
planned
paid
received
skipped
overdue
```

Когда доход получен или расход оплачен, создаётся или привязывается обычная `Transaction`.

Для первой версии сопоставление подтверждает пользователь. Позже приложение может предлагать совпадение по сумме, дате, счёту и категории, но не должно автоматически считать подписку оплаченной только по тексту комментария.

План показывает:

- ожидаемые пополнения;
- обязательные расходы;
- подписки;
- аренду и связь;
- отчисления в накопления;
- просроченные события;
- план и факт по каждому событию.

---

# 9. Раздел «Трекер» и бюджетные периоды

Трекер сохраняет текущую механику FinApp: доступная сумма делится на оставшиеся дни периода, а траты уменьшают сегодняшний остаток.

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
- opening_plan_occurrence_id
- timezone
- status
- created_at
- closed_at
```

`status`:

```text
upcoming
current
ended
```

Все периоды сохраняются. Завершённый период можно открыть, проверить и исправить с явным подтверждением.

Период может быть создан вручную или при получении ожидаемого дохода:

1. В Плане есть ожидаемое пополнение и следующие обязательные траты.
2. Пользователь отмечает пополнение как полученное или связывает его с импортированной операцией.
3. Приложение предлагает период от даты пополнения до даты следующего ожидаемого дохода.
4. Пользователь подтверждает сумму периода и обязательные резервы.
5. Трекер рассчитывает ежедневный лимит.

## BudgetCommitment

`BudgetCommitment` резервирует часть денег периода под обязательный расход или накопление.

```text
BudgetCommitment
- id
- budget_period_id
- type
- plan_occurrence_id
- goal_id
- name
- planned_amount
- status
```

`type`:

```text
required_expense
savings
```

`status`:

```text
reserved
fulfilled
cancelled
```

Отдельная сущность полезна, потому что фиксирует, какая часть денег периода уже предназначена для обязательств. Сам ежедневный пул отдельной записью хранить не нужно — он рассчитывается:

```text
daily_pool =
funding_amount
− активные обязательные резервы
− запланированные накопления
```

Оплата уже зарезервированной аренды не уменьшает ежедневный пул второй раз. Фактическая транзакция связывается с соответствующим `BudgetCommitment` через `PlanOccurrence`.

Трекер показывает:

- даты периода;
- сумму периода;
- обязательные резервы;
- доступный ежедневный пул;
- сколько можно потратить сегодня;
- сколько потрачено сегодня;
- остаток до конца периода;
- прогноз ежедневного лимита после новой траты;
- список операций периода.

---

# 10. Накопления

## Goal

```text
Goal
- id
- workspace_id
- owner_user_id
- name
- target_amount
- target_asset_id
- target_date
- linked_account_id
- is_protected
- status
- created_at
```

Для первой версии одна цель связана с одним резервным или виртуальным счётом.

Пополнение цели — внутренний перевод, а не расход. Если связанный счёт исключён из доступной суммы, деньги перестают учитываться как доступные для повседневных трат.

---

# 11. Синхронизация криптосчетов

Синхронизация добавляется после появления стабильного журнала операций.

## IntegrationConnection

```text
IntegrationConnection
- id
- account_id
- provider
- network
- public_address
- encrypted_readonly_credentials
- sync_interval_minutes
- last_synced_at
- next_sync_at
- status
- created_at
```

## ImportedOperation

```text
ImportedOperation
- id
- integration_connection_id
- external_id
- raw_data
- detected_type
- confirmation_status
- transaction_id
- detected_at
```

`confirmation_status`:

```text
pending
confirmed
failed
```

Процесс:

1. Пользователь добавляет публичный адрес кошелька.
2. Планировщик, например раз в 5 минут, запрашивает новые операции.
3. Новая внешняя операция сохраняется один раз по `connection + external_id`.
4. Подтверждённая операция создаёт `Transaction` и движения по счёту.
5. Пользователь может изменить категорию, комментарий и связь с Планом.
6. Неоднозначные операции попадают в список «Нужно разобрать».

Правила безопасности:

- никогда не запрашивать seed phrase или private key;
- для бирж принимать только read-only credentials;
- повторный импорт не создаёт дубликаты;
- сетевую комиссию учитывать отдельно;
- неподтверждённую blockchain-операцию не включать в финальный баланс;
- для периодического запуска достаточно cron, отдельная очередь задач не нужна.

---

# 12. Раздел «Аналитика»

На первом этапе раздел остаётся заглушкой. Детальную аналитику нужно проектировать после стабилизации счетов, операций, планов и периодов.

Будущие отчёты:

- доходы и расходы за неделю, месяц или произвольный период;
- расходы по категориям и счетам;
- денежный поток;
- изменение общего капитала;
- план против факта;
- прогресс накоплений;
- фильтры по пользователю и общему пространству.

Внутренние переводы не считаются доходом или расходом. Для исторической аналитики используется курс на дату операции.

---

# 13. API

Все новые маршруты используют префикс:

```text
/api/v1
```

## Авторизация и доступ

```text
POST   /api/v1/auth/register
POST   /api/v1/auth/login
POST   /api/v1/auth/logout
GET    /api/v1/auth/me

POST   /api/v1/workspaces
GET    /api/v1/workspaces
GET    /api/v1/workspaces/{id}
PATCH  /api/v1/workspaces/{id}

POST   /api/v1/workspaces/{id}/invitations
GET    /api/v1/workspaces/{id}/members
PATCH  /api/v1/workspaces/{id}/members/{user_id}
DELETE /api/v1/workspaces/{id}/members/{user_id}
POST   /api/v1/invitations/{token}/accept
```

## Активы и курсы

```text
GET  /api/v1/assets
GET  /api/v1/exchange-rates
POST /api/v1/exchange-rates
```

## Счета

```text
POST   /api/v1/accounts
GET    /api/v1/accounts
GET    /api/v1/accounts/summary
GET    /api/v1/accounts/{id}
PATCH  /api/v1/accounts/{id}
POST   /api/v1/accounts/{id}/reconcile
POST   /api/v1/accounts/{id}/archive

GET    /api/v1/accounts/{id}/access
POST   /api/v1/accounts/{id}/access
PATCH  /api/v1/accounts/{id}/access/{user_id}
DELETE /api/v1/accounts/{id}/access/{user_id}
```

`GET /accounts/summary` возвращает общий капитал, доступную сумму и разбивку по активам.

## Транзакции

```text
POST  /api/v1/transactions/expense
POST  /api/v1/transactions/income
POST  /api/v1/transactions/transfer
POST  /api/v1/transactions/exchange
POST  /api/v1/transactions/adjustment

GET   /api/v1/transactions
GET   /api/v1/transactions/{id}
PATCH /api/v1/transactions/{id}
POST  /api/v1/transactions/{id}/void
POST  /api/v1/transactions/{id}/assign-account
POST  /api/v1/transactions/{id}/link-plan
```

Фильтры `GET /transactions`:

```text
account_id
date_from
date_to
type
category_id
source
status
created_by_user_id
```

Frontend передаёт понятные поля операции. Backend сам формирует необходимые `TransactionLeg`.

## Категории

```text
POST  /api/v1/categories
GET   /api/v1/categories
PATCH /api/v1/categories/{id}
POST  /api/v1/categories/{id}/archive
```

## План

```text
POST   /api/v1/plan-rules
GET    /api/v1/plan-rules
PATCH  /api/v1/plan-rules/{id}
POST   /api/v1/plan-rules/{id}/archive

GET  /api/v1/plan-occurrences
POST /api/v1/plan-occurrences/{id}/pay
POST /api/v1/plan-occurrences/{id}/receive
POST /api/v1/plan-occurrences/{id}/skip
POST /api/v1/plan-occurrences/{id}/link-transaction
```

## Трекер и периоды

```text
POST  /api/v1/budget-periods/preview
POST  /api/v1/budget-periods
GET   /api/v1/budget-periods
GET   /api/v1/budget-periods/current
GET   /api/v1/budget-periods/{id}
PATCH /api/v1/budget-periods/{id}
POST  /api/v1/budget-periods/{id}/close

POST   /api/v1/budget-periods/{id}/commitments
PATCH  /api/v1/budget-commitments/{id}
DELETE /api/v1/budget-commitments/{id}

GET /api/v1/tracker/today
GET /api/v1/tracker/preview?pending={amount}
```

## Цели

```text
POST  /api/v1/goals
GET   /api/v1/goals
PATCH /api/v1/goals/{id}
POST  /api/v1/goals/{id}/fund
POST  /api/v1/goals/{id}/withdraw
```

## Интеграции

```text
POST   /api/v1/integrations
GET    /api/v1/integrations
PATCH  /api/v1/integrations/{id}
DELETE /api/v1/integrations/{id}
POST   /api/v1/integrations/{id}/sync

GET  /api/v1/imported-operations
POST /api/v1/imported-operations/{id}/classify
POST /api/v1/imported-operations/{id}/ignore
```

## Аналитика — после стабилизации модели

```text
GET /api/v1/analytics/cash-flow
GET /api/v1/analytics/spending
GET /api/v1/analytics/net-worth
GET /api/v1/analytics/plan-vs-actual
```

---

# 14. Навигация

Основные разделы:

## Счета

Общий капитал, доступная сумма, список счетов и быстрые действия со счетами.

## Транзакции

Вся история, фильтры, редактирование и разбор импортированных операций.

## Трекер

Текущий период, сумма на сегодня, быстрый ввод траты и история периодов.

## План

Ожидаемые доходы, обязательные расходы, подписки, накопления и запуск нового периода после пополнения.

## Аналитика

Сначала заглушка, затем отчёты после согласования модели данных.

Настройки, профиль, пользователи и права находятся в отдельном меню, а не в основной навигации.

---

# 15. Порядок развития

## Этап 1. Пользователи и финансовое пространство

- пользователи и авторизация;
- личные и общие workspace;
- роли и приглашения;
- категории и базовые активы.

## Этап 2. Счета и журнал операций

- счета;
- движения по счетам;
- расходы, доходы, переводы, обмены и корректировки;
- общий и доступный баланс;
- непривязанные операции;
- разделы Счета и Транзакции.

## Этап 3. Совместный доступ

- доступ к отдельным счетам;
- права owner, editor, contributor и viewer;
- отображение автора операции;
- проверка доступа во всех API.

## Этап 4. План и Трекер

- ожидаемые доходы и расходы;
- подписки;
- обязательные резервы;
- запуск периода после дохода;
- сохранение истории периодов;
- ежедневный бюджет без двойного списания обязательных расходов.

## Этап 5. Криптосинхронизация

- публичные адреса;
- периодическая синхронизация;
- защита от дубликатов;
- подтверждения и комиссии;
- разбор и классификация операций.

## Этап 6. Аналитика

- согласование метрик;
- фильтры;
- cash flow;
- net worth;
- план против факта;
- накопления.

---

# 16. Главные правила системы

1. Баланс счёта всегда рассчитывается из движений.
2. Изменение баланса оформляется операцией, а не прямой записью нового числа.
3. Внутренний перевод не считается расходом или доходом.
4. Перевод другому человеку считается расходом.
5. Перевод в накопления не считается расходом.
6. Исключённый счёт не входит в доступную сумму, но остаётся частью общего капитала.
7. Непривязанная операция влияет на Трекер, но не влияет на баланс счёта.
8. Все бюджетные периоды сохраняются.
9. Оплата зарезервированного расхода не уменьшает ежедневный пул второй раз.
10. Отмена или редактирование операции полностью пересчитывает производные суммы.
11. Повторный импорт внешней операции не создаёт дубликат.
12. Неподтверждённая blockchain-операция не меняет финальный баланс.
13. Суммы хранятся без потери точности, включая криптоактивы.
14. Дата операции хранится вместе с UTC-временем и локальной финансовой датой.
15. Пользователь получает только те данные и действия, которые разрешены его ролью.

---

# Итоговая модель

```text
User + Workspace → кто управляет данными
Asset + Account → где и в чём находятся деньги
Transaction + TransactionLeg → как деньги перемещались
Category → на что пришлись доходы и расходы
PlanRule + PlanOccurrence → что ожидается
BudgetPeriod + BudgetCommitment → сколько можно тратить сейчас
Goal → зачем откладываются деньги
IntegrationConnection + ImportedOperation → откуда приходят внешние операции
Analytics → что происходило с финансами
```

Эта модель сохраняет текущую механику ежедневного бюджета, но превращает FinApp в приложение для всех счетов, совместного доступа, планирования и последующей автоматической синхронизации.
