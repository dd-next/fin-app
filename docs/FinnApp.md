# 1. Главная доменная модель

> Исторический черновик. Актуальная спецификация находится в
> `specs/FinnApp-v2.md`.

## Слой 1. Accounts — где находятся деньги

`Account` — одно место хранения одного актива.

Примеры:
- Cash VND;
- Cash USD;
- Vietcombank VND;
- российская карта RUB;
- Bybit USDT;
- Trust Wallet TRX;
- PayPal USD;
- Emergency Fund USD.

Основные поля:
```text
Account
- id
- user_id
- name
- storage_type
- purpose
- asset_id
- institution
- is_virtual
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

Важно разделить тип хранения и назначение:

- `crypto_wallet` отвечает на вопрос «где лежат деньги»;
- `savings` отвечает на вопрос «можно ли их тратить».

Баланс лучше **не редактировать напрямую**. Он рассчитывается из журнала операций:

```text
account_balance = сумма всех движений по счёту
```

При создании счёта начальный баланс оформляется как техническая операция `adjustment`.

---

## Слой 2. Assets — в чём выражены деньги

Нужна отдельная сущность `Asset`, а не просто поле `currency`.

```text
Asset
- id
- code
- name
- kind
- decimals
```

Примеры:

```text
VND — fiat — 0 decimals
USD — fiat — 2 decimals
USDT — crypto — 6 decimals
BTC — crypto — 8 decimals
ETH — crypto — 18 decimals
```

Текущая модель FinApp ограничивает суммы двумя знаками после запятой, что подходит для обычного фиата, но не подходит для криптовалют. Сейчас и SQLAlchemy-модель, и входные схемы рассчитаны на `12,2`.

Для первой версии достаточно сохранить используемый сейчас `Decimal`, но расширить хранение примерно до:

```python
Numeric(38, 18)
```

А допустимое количество знаков валидировать через `Asset.decimals`.

---

# 2. Операция должна состоять из движений по счетам

## Transaction

Описывает смысл события:

```text
Transaction
- id
- user_id
- type
- category_id
- budget_allocation_id
- counterparty
- note
- occurred_at
- local_date
- source
- status
- external_id
- base_amount
- created_at
```

Типы:

```text
expense
income
transfer
adjustment
```

`source`:

```text
manual
imported
scheduled
```

## TransactionLeg

Показывает, как изменился конкретный счёт:

```text
TransactionLeg
- id
- transaction_id
- account_id
- amount
```

Сумма знаковая:

```text
+100 — деньги пришли на счёт
-100 — деньги ушли со счёта
```

Это **минимальный журнал движений**

---

# 3. Как будут выглядеть реальные операции

## Покупка еды наличными

```text
Transaction:
type = expense
category = restaurants
note = "Dinner"

Leg:
Cash VND: -500,000
```

Общий капитал уменьшился на 500 000 VND.

## Снятие наличных с карты

```text
Transaction:
type = transfer

Legs:
Vietcombank VND: -5,000,000
Cash VND:        +5,000,000
```

Общий капитал не изменился. В аналитике расходов операция не показывается.

## Покупка VND за USDT

```text
Transaction:
type = transfer

Legs:
Bank VND:   -2,600,000
Binance USDT: +100
```

Из двух сумм можно вычислить фактический курс:

```text
1 USDT = 26,000 VND
```

Пользователь может поправить обе суммы после импорта.

## Комиссия при покупке USDT

Комиссию лучше оформлять отдельным движением внутри той же транзакции:

```text
Bank VND: -20,000
category: fees
```

Тогда:

- перевод не считается расходом;
- комиссия считается расходом.

## Перевод third person

Если счёт 3rd person не входит в управляемые пользователем счета, это **не внутренний transfer**, а расход:

```text
type = expense
category = family_support
counterparty = "Mother"
Bank RUB: -10,000
```

`transfer` используется только тогда, когда оба счёта принадлежат одному финансовому контуру пользователя.

## Пополнение копилки

Если копилка представлена отдельным резервным счётом:

```text
type = transfer

Main USD:           -200
Emergency Fund USD: +200
```

Это не расход. Общая сумма денег не изменилась, но доступная для повседневных трат уменьшилась.

---

# 4. Обязательные расходы 

## ScheduleRule

Шаблон регулярного события:

```text
ScheduleRule
- id
- user_id
- direction
- name
- amount
- asset_id
- recurrence
- due_day
- category_id
- default_account_id
- is_required
- is_active
```

Примеры:

```text
Rent — expense — monthly — day 25
Salary — income — monthly — day 5
Netflix — expense — monthly — day 8
```

## ScheduleOccurrence

Конкретное появление события:

```text
ScheduleOccurrence
- id
- schedule_rule_id
- due_date
- planned_amount
- status
- transaction_id
```

Статусы:

```text
planned
paid
received
skipped
overdue
```

Когда пользователь оплачивает аренду, создаётся обычный `expense`, который связывается с соответствующим `ScheduleOccurrence`.

Это позволяет сравнивать:

```text
План аренды: 12,000,000 VND
Фактически: 12,300,000 VND
Отклонение: +300,000 VND
```

Также здесь будет информация про subscription
Пользователь сможет создать ScheduleRule с типом или direction subscription, сумму, тип списания, дата списания, счет списания, то есть когда внес трату, можно потом отменитить, что это оплачено или ScheduleRule сам будет проверять транзакции и по комменту или по категории отмечать, что надо обновить на месяц правило, как-то так

---

# 5. Бюджетирование должно быть отдельным слоем

Счета отвечают за местоположение денег. Бюджет отвечает за их назначение.

## BudgetPeriod

```text
BudgetPeriod
- id
- user_id
- start_date
- end_date
- base_asset_id
- timezone
- status
```

Например:

```text
5 августа — 4 сентября
Базовая валюта: USD
```

## BudgetAllocation - сомневаюсь насчет этого, не пойму ценность

Распределение денег внутри периода:

```text
BudgetAllocation
- id
- budget_period_id
- type
- name
- planned_amount
- schedule_occurrence_id
- goal_id
```

Типы:

```text
required
savings
daily
```

Пример распределения:

```text
Доступно на период:       $2,000

Обязательные расходы:
Rent                        $600
Subscriptions                $80
Internet                     $40

Накопления:
Emergency fund              $250
Tickets                     $150

Daily spending pool:        $880
```

Формула:

```text
daily_pool =
деньги, выделенные на период
− обязательные расходы
− выбранные накопления
```

И уже эти `$880` передаются в существующий алгоритм FinApp:

```text
daily_allowance = daily_pool / remaining_days
```

Текущий модуль `budget.py` можно в основном сохранить. Он уже изолирован от FastAPI и базы данных и принимает обычные значения, поэтому его удобно тестировать и переиспользовать.

Изменится только источник данных:

```text
Было:
Period.total_amount + все expense/income

Станет:
BudgetAllocation(type=daily)
+ операции, отнесённые к daily-бюджету
```

Оплата заранее зарезервированной аренды не должна повторно уменьшать ежедневный бюджет:

```text
До оплаты:
Баланс: 2,000
Аренда зарезервирована: 600
Daily pool: 1,400

После оплаты:
Баланс: 1,400
Аренда больше не ожидается: 0
Daily pool остаётся: 1,400
```

---

# 6. Копилка технически состоит из двух понятий

Технически полезно различать:
- `Account` — где лежат деньги;
- `Goal` — зачем они откладываются.

## Goal

```text
Goal
- id
- user_id
- name
- target_amount
- target_asset_id
- target_date
- linked_account_id
- is_protected
- status
```

Пример:

```text
Emergency fund
Target: $5,000
Current: $1,200
Linked account: Emergency Fund USDT
```

Для MVP можно ввести правило:

> Одна цель связана с одним резервным или виртуальным счётом.

Позже можно позволить одной цели состоять из нескольких активов:

```text
$500 cash
$700 USDT
$300 bank USD
```

Но это не нужно реализовывать сразу.

---

# 7. Основные API-ручки

Использовать префикс:

```text
/api/v1
```

## Accounts

```text
POST   /api/v1/accounts
GET    /api/v1/accounts
GET    /api/v1/accounts/{id}
PATCH  /api/v1/accounts/{id}
POST   /api/v1/accounts/{id}/reconcile
POST   /api/v1/accounts/{id}/archive
```

Создание счёта:

```json
{
  "name": "Cash VND",
  "storage_type": "cash",
  "purpose": "spending",
  "asset_code": "VND",
  "opening_balance": "5000000"
}
```

`opening_balance` внутри сервиса превращается в `adjustment`, а не записывается непосредственно в поле баланса.

## Transactions

Frontend не должен самостоятельно собирать низкоуровневые `TransactionLeg`.

Для него лучше сделать понятные команды:

```text
POST /api/v1/transactions/expense
POST /api/v1/transactions/income
POST /api/v1/transactions/transfer
POST /api/v1/transactions/adjustment

GET  /api/v1/transactions
GET  /api/v1/transactions/{id}
PATCH /api/v1/transactions/{id}
POST /api/v1/transactions/{id}/void
```

Расход:

```json
{
  "account_id": 12,
  "amount": "500000",
  "category_id": 4,
  "budget_allocation_id": 18,
  "occurred_at": "2026-07-17T19:30:00+07:00",
  "note": "Dinner"
}
```

Перевод с конвертацией:

```json
{
  "from_account_id": 3,
  "from_amount": "100",
  "to_account_id": 7,
  "to_amount": "2550000",
  "occurred_at": "2026-07-17T15:00:00+07:00",
  "note": "USDT cash out",
  "fee": {
    "account_id": 3,
    "amount": "1.5",
    "category_id": 9
  }
}
```

Backend сам создаёт необходимые движения.

## Categories

```text
POST   /api/v1/categories
GET    /api/v1/categories
PATCH  /api/v1/categories/{id}
POST   /api/v1/categories/{id}/archive
```

Для начала достаточно 8–12 категорий и пользовательских категорий.

## Planning

```text
POST /api/v1/schedules
GET  /api/v1/schedules
GET  /api/v1/schedules/upcoming

POST /api/v1/schedule-occurrences/{id}/pay
POST /api/v1/schedule-occurrences/{id}/skip
```

## Budget

```text
POST /api/v1/budget-periods/preview
POST /api/v1/budget-periods
GET  /api/v1/budget-periods/current
GET  /api/v1/budget/today
POST /api/v1/budget/recalculate
```

`preview` особенно полезен:

```json
{
  "period_start": "2026-08-05",
  "period_end": "2026-09-04",
  "available": "2000",
  "required": "720",
  "savings": "400",
  "daily_pool": "880",
  "daily_allowance": "28.39"
}
```

## Goals

```text
POST  /api/v1/goals
GET   /api/v1/goals
PATCH /api/v1/goals/{id}
POST  /api/v1/goals/{id}/fund
POST  /api/v1/goals/{id}/withdraw
```

`fund` фактически создаёт перевод на связанный резервный счёт.

## Dashboard и аналитика

```text
GET /api/v1/dashboard
GET /api/v1/analytics/spending
GET /api/v1/analytics/cash-flow
GET /api/v1/analytics/net-worth
GET /api/v1/analytics/plan-vs-actual
```

---

# 8. Как должна выглядеть навигация

Оптимально оставить четыре нижние кнопки.

## Home

Главный экран:

```text
Сегодня можно потратить
720,000 VND

Потрачено
310,000 VND

Осталось
410,000 VND
```

Здесь же максимально быстрый ввод:

```text
Сумма → категория → счёт → сохранить
```

Приложение запоминает последний счёт и часто используемые категории.

## Accounts

```text
Всего: $6,420

Cash
- Cash VND
- Cash USD

Banks
- Vietcombank
- T-Bank

Crypto
- Binance USDT
- Trust Wallet TRX

Savings
- Emergency Fund
- Travel
```

## Plan

- ожидаемые доходы с датой пополнения;
- ближайшие обязательные расходы и подписки;
- копилки;
- текущий бюджетный период;
- план накоплений.

## Analytics - не делать пока полностью, сделать как заглушку

- расходы по категориям;
- денежный поток;
- накопления;
- изменение общего капитала;
- план против факта.

`Settings` лучше не занимать нижнюю кнопку — разместить в профиле или меню Accounts.

---

# 9. Синхронизация криптокошельков - на подумать

Это действительно логичная вторая большая версия, но только после появления нормального ledger.

## Дополнительные сущности

```text
IntegrationConnection
- id
- user_id
- provider
- type
- account_id
- public_address
- encrypted_credentials
- last_synced_at
- status
```

```text
ImportedTransaction
- id
- integration_id
- external_id
- raw_data
- detected_type
- status
- transaction_id
```

Статусы импорта:

```text
unclassified
classified
ignored
duplicate
```

Процесс:

1. Пользователь добавляет публичный адрес.
2. Сервис получает историю транзакций.
3. Каждая внешняя операция импортируется один раз.
4. Знакомые собственные адреса распознаются как внутренний перевод.
5. Неизвестные операции попадают в Inbox.
6. Пользователь выбирает:
    - расход
    - доход
    - перевод между своими счетами
    - обмен активов
    - игнорировать
7. Комиссия сети сохраняется отдельно.

Критические правила:

- никогда не запрашивать seed phrase или private key;
- для бирж использовать только read-only credentials;
- добавить уникальное ограничение на `integration_id + external_id`;
- повторная синхронизация не должна создавать дубликаты;
- неподтверждённые blockchain-транзакции хранить отдельно от финальных.

---

# 10. Архитектура без overengineering

**Модульный монолит**:

```text
app/
  api/
    routes/
      accounts.py
      transactions.py
      categories.py
      planning.py
      budget.py
      goals.py
      analytics.py
      integrations.py
  models/
    user.py
    asset.py
    account.py
    transaction.py
    planning.py
    goal.py
    integration.py
  schemas/
    accounts.py
    transactions.py
    planning.py
  services/
    ledger.py
    budgeting.py
    schedules.py
    analytics.py
    imports.py
  domain/
    budget.py
    money.py
    rules.py
  db/
    session.py
```

Текущий `main.py` уже объединяет роуты, SQL-запросы, бюджетную оркестрацию, экспорт и синхронизацию Sheets. Для текущего размера это нормально, но при добавлении счетов и планирования его лучше разнести по модулям.

`budget.py` стоит оставить чистым доменным модулем без SQLAlchemy и FastAPI.

---

# 11. Этапы

## Этап 1. Accounts и ledger

- `Asset`;
- `Account`;
- `Category`;
- `Transaction`;
- `TransactionLeg`;
- расходы;
- доходы;
- переводы;
- корректировка баланса;
- экран Accounts;
- быстрый ввод с Home.

## Этап 2. Планирование

- регулярные расходы и доходы;
- копилки;
- бюджетные allocations;
- автоматический расчёт daily pool;
- предупреждение о перерасходе;
- прогноз до следующего дохода.

## Этап 3. Crypto sync

- публичные адреса;
- импорт транзакций;
- Inbox для классификации;
- распознавание внутренних переводов;
- комиссии;
- повторная безопасная синхронизация.

## Этап 4. Аналитика

- траты по категориям;
- расходы по счетам и валютам;
- cash flow;
- net worth;
- план против факта;
- прогресс накоплений.

Базовую аналитику можно добавить раньше, но серьёзные отчёты имеет смысл строить только после стабилизации структуры операций.

---

# 12. Главные технические инварианты

Их нужно сразу закрепить тестами:

1. Перевод между считами не меняет общий капитал (кроме потери на конвертации и комиссии за обмен сервису)
2. Перевод между считами не попадает в расходы.
3. Перевод другому человеку считается расходом.
4. Перевод в копилку не считается расходом.
5. Оплата заранее зарезервированной аренды не уменьшает daily pool второй раз.
6. Повторный импорт blockchain-транзакции не создаёт дубликат.
7. Отмена операции полностью восстанавливает соответствующие балансы.
8. Историческая аналитика использует курс на момент операции.
9. BTC и токены не теряют точность.
10. Операция около полуночи попадает в правильный локальный день.

Последнее важно для номадов. Сейчас FinApp использует локальные `datetime.now()` и `date.today()`. Для одного пользователя на одном устройстве это работает, но для путешествий и нескольких пользователей лучше хранить timezone-aware UTC-время плюс локальную дату операции.

---

# Итоговая техническая формулировка продукта

> FinApp — персональная multi-asset система управления финансами, которая ведёт единый журнал движений между пользовательскими счетами, отделяет внутренние переводы от реальных доходов и расходов, распределяет средства между обязательствами, накоплениями и ежедневным бюджетом и позволяет подключать внешние источники операций через безопасный импорт.

Самая правильная основа здесь:

```text
Accounts → где деньги
Transactions → как они перемещались
Categories → на что они ушли
Planning → для чего они предназначены
Integrations → откуда автоматически получать операции
Analytics → что происходило с финансами
```

Это достаточно серьёзная модель, чтобы позже подключить криптокошельки, аналитику и нескольких пользователей, но всё ещё обычный FastAPI-монолит без лишней инфраструктуры.
