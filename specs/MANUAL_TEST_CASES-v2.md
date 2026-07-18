# Ручная проверка FinApp v2

Документ проверяет первый релиз из `specs/FinnApp-v2.md`. Шаги описаны
по фактическому интерфейсу: UI приложения полностью на английском.

## Подготовка

Для отдельной тестовой БД:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=sqlite+aiosqlite:////tmp/finapp-v2-manual.db
alembic upgrade head
uvicorn app.main:app --reload
```

Открыть `http://127.0.0.1:8000`. Не использовать рабочую `finapp.db` для
ручных тестовых данных.

## MT-01 — Регистрация, сессия и пустые состояния

1. Открыть приложение без сессии.
2. Нажать `Create account`, указать username, display name и пароль не короче
   10 символов.
3. Проверить разделы `Accounts`, `Transactions`, `Tracker`, `Plan`, `Analytics`.
4. Перезагрузить страницу, затем выполнить `Log out` и снова `Log in`.

Ожидается: после регистрации создан личный workspace; cookie-сессия переживает
перезагрузку; после logout финансовые данные недоступны; пустые разделы дают
понятное следующее действие. `Analytics` стабильно показывает `Coming soon`.

## MT-02 — Счета, точность и итоги

1. В `Accounts` нажать `＋ Add account`.
2. Создать `Main USD` с opening balance `1000.25`, purpose `Spending` и
   включённым `Include this account in Available`.
3. Создать `Emergency USD` с opening balance `300`, purpose `Reserve` и
   выключенным `Include this account in Available`.
4. Создать `BTC Wallet` с opening balance `0.12345678`.
5. Попробовать создать BTC-счёт с девятым знаком после запятой.
6. Открыть `Main USD`, выполнить `Reconcile` до `990.25`, затем изменить имя.

Ожидается: `Total capital` включает оба USD-счёта, `Available` исключает Emergency;
BTC без курса находится в предупреждении `Not included in totals`; лишняя
точность отклонена; reconcile создаёт adjustment, а не переписывает историю.

## MT-03 — Реальные операции и журнал

1. В `Transactions` через `＋ Add transaction` создать:
   - expense `40` с Main USD;
   - income `200` на Main USD;
   - transfer `100` Main USD → Emergency USD;
   - exchange из USD в BTC с двумя фактическими суммами;
   - adjustment на счёте владельца.
2. Создать expense без account, выбрав только asset, затем нажать `Assign`.
3. Отфильтровать список по account, type, date, category и status.
4. Нажать `Edit`, изменить amount/comment/date; другую операцию `Void`.

Ожидается: expense уменьшает баланс, income увеличивает; transfer и exchange
не меняют общий капитал; exchange создаёт текущий прямой/обратный курс;
unassigned не меняет счёт до `Assign`; edit и void полностью пересчитывают
balances и derived rates; posted-операция не удаляется физически.

## MT-04 — Категории

1. Открыть profile menu → `Categories`.
2. Создать expense-категорию `Groceries` и income-категорию `Salary`.
3. Проверить их в соответствующих transaction/Plan forms.
4. Переименовать категорию и затем архивировать.

Ожидается: тип категории ограничивает выбор; имя уникально внутри workspace;
архивная категория исчезает из новых форм, но остаётся в старых операциях.

## MT-05 — Sharing и четыре роли

Для каждой роли создать отдельный invite через account details → `Share`:

| Роль | Просмотр | Expense | Income | Edit/Void | Account edit | Reconcile/Share |
|---|---:|---:|---:|---:|---:|---:|
| Viewer | да | нет | нет | нет | нет | нет |
| Contributor | да | да | нет | нет | нет | нет |
| Editor | да | да | да | да, если доступны все legs | да | нет |
| Owner | да | да | да | да | да | да |

1. Открыть каждую одноразовую invite-ссылку в отдельной сессии и принять её.
2. Повторно открыть уже принятую ссылку.
3. У editor создать transfer между двумя доступными ему счетами, затем
   попробовать transfer на скрытый счёт владельца.
4. У приглашённого открыть Accounts, Transactions, Plan и Tracker.

Ожидается: повторная/просроченная ссылка не работает; видны только shared
accounts и доступные legs, скрытые legs помечены; агрегаты владельца, Plan,
Tracker, `budget_period_id`, Plan links и frozen valuation не раскрываются.

## MT-06 — Plan rules и recurrence

1. В `Plan` нажать `＋ Add rule` и создать по одному правилу:
   expected income, required expense, subscription, reserve transfer и other
   expense.
2. Проверить `Once`, `Weekly`, `Monthly`, `Yearly`; для monthly использовать
   31-е число, для yearly — 29 февраля.
3. Перезагрузить список несколько раз, затем изменить сумму/дату правила.
4. Для occurrence проверить `Pay`/`Receive`, `Skip` и `Link` с существующей
   posted transaction. Попробовать исполнить occurrence повторно.
5. Архивировать правило.

Ожидается: 12-месячный горизонт не создаёт дубликаты; короткий месяц получает
последний допустимый день, leap-day восстанавливается в високосный год;
completed показывает planned vs actual; повторное исполнение отклонено;
архивирование сохраняет завершённую историю и пропускает открытые occurrences.

## MT-07 — Income proposal и явное создание периода

1. Создать monthly income с due date сегодня и `Receive` его.
2. В открывшемся `Confirm income period` проверить start, suggested end,
   funding и `Commitments snapshot`.
3. Нажать `Cancel`: реальный income должен сохраниться, периода быть не должно.
4. Снова открыть proposal через
   `POST /api/v1/workspaces/{workspace_id}/budget-periods/preview`, затем
   `Confirm period`.
5. Повторить с `Once` income, после которого нет следующего income.

Ожидается: monthly proposal заканчивается за день до следующего income;
создание требует подтверждения; для one-time income end date обязателен и
выбирается пользователем; пересекающийся период получает HTTP 409.

## MT-08 — Commitments plan-vs-actual без двойного списания

1. До подтверждения периода добавить required expense `Rent 250` и reserve
   transfer `Emergency 100`, попадающие в его даты.
2. Создать период с funding `1200`.
3. Убедиться: начальный daily pool равен `1200 - 250 - 100`.
4. Оплатить Rent фактически на `260`, reserve transfer на `90`.
5. Открыть Tracker и Transactions, затем void Rent transaction.

Ожидается: commitments показывают план и факт; daily pool равен
`1200 - 260 - 90`; связанные факты не находятся одновременно в `spent_total`;
после void Rent снова `reserved 250`, occurrence снова planned/overdue.

## MT-09 — Daily replay, quick expense и carry decision

1. Создать период со вчера на 10 дней, funding `1000`, без commitments.
2. Вчерашним числом добавить expense `40`.
3. Сегодня открыть Tracker: budget today должен быть `160` (base 100 + carry 60).
4. В `Quick expense` ввести `30`, не сохраняя, и проверить live preview `130`.
5. Добавить трату и проверить уменьшение сегодня ровно на 30.
6. В prompt выбрать `Keep for today`; в новом тестовом периоде выбрать
   `Spread across remaining days`.
7. Создать перерасход вчера и проверить автоматический rebase следующих дней.

Ожидается: значения не обрезаются при минусе; carry переносится; voluntary
redistribution создаёт устойчивый rebase, prompt больше не показывается в этот
день; edit/void дают тот же результат, что полный replay с нуля.

## MT-10 — Frozen multi-asset valuation

1. Создать USD- и BTC-счета и exchange, задающий курс BTC/USD.
2. Создать USD budget period и BTC expense внутри периода.
3. Если курса нет, в появившемся запросе указать USD equivalent.
4. Создать второй exchange с другим курсом.
5. Сравнить transaction `base_amount` и Tracker до/после нового курса.

Ожидается: Tracker использует зафиксированный base amount и точность USD;
новый текущий курс меняет live Net worth, но не исторический период.

## MT-11 — История и ended-period correction

1. Создать завершённый и текущий непересекающиеся периоды.
2. В `Period history` переключаться между ними; нажать `View transactions`.
3. Изменить операцию завершённого периода и подтвердить предупреждение.
4. Повторить с `Void`.
5. Нажать `Close period` у текущего периода.

Ожидается: история не удаляется; без отдельного подтверждения ended correction
получает HTTP 409; после подтверждения исторические totals пересчитаны; закрытый
период становится ended и исчезает из `/budget-periods/current`.

## MT-12 — Responsive, accessibility и ошибки

1. Проверить все пять разделов при 480×900 и 1280×900.
2. Пройти основные формы только клавиатурой, проверить видимый focus.
3. Проверить dialog `Close`/`Cancel`, form errors, loading indicator и toast.
4. Убедиться, что главные tap targets не меньше 44 px и нет горизонтального
   scroll.
5. Просмотреть UI на отсутствие русских строк.

Ожидается: phone использует нижнюю навигацию и один столбец; desktop —
многоколоночную раскладку; labels доступны screen reader; ошибки не закрывают
форму и объясняют исправление; UI полностью English.

## MT-13 — Чистая миграция и автоматические проверки

```sh
DATABASE_URL=sqlite+aiosqlite:////tmp/finapp-v2-fresh.db alembic upgrade head
DATABASE_URL=sqlite+aiosqlite:////tmp/finapp-v2-fresh.db alembic current
.venv/bin/python -m pytest -q
node --check app/static/app.js
curl http://127.0.0.1:8000/health
```

Ожидается: Alembic показывает `0005_v2 (head)`, создано восемь assets, тесты и
JS syntax проходят, `/health` отвечает HTTP 200 `{"status":"ok"}`. Никаких
Redis, Celery, worker или внешних сервисов для запуска не требуется.
