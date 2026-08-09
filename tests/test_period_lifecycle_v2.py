from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.models import AccountPeriod, Transaction, TransactionLeg
from app.periods import period_status, workspace_today
from tests.conftest import register
from tests.test_ledger_v2 import create_account
from tests.test_periods_v2 import add_test_leg, create_period, local_today


async def persisted_period_state(client, period_id):
    async with client._finapp_test_sessions() as session:
        period = await session.get(AccountPeriod, period_id)
        assert period is not None
        return (
            period.start_date,
            period.end_date,
            period.snapshot_at,
            period.opening_balance,
            period.rollover_policy,
            period.created_at,
            period.closed_at,
            period.closing_balance,
        )


async def account_ledger_rows(client, account_id):
    async with client._finapp_test_sessions() as session:
        rows = (
            await session.execute(
                select(
                    Transaction.id,
                    Transaction.status,
                    Transaction.voided_at,
                    TransactionLeg.id,
                    TransactionLeg.amount,
                    TransactionLeg.created_at,
                )
                .join(TransactionLeg)
                .where(TransactionLeg.account_id == account_id)
                .order_by(Transaction.id, TransactionLeg.id)
            )
        ).all()
        return [tuple(row) for row in rows]


async def account_balance(client, account_id):
    response = await client.get(f"/api/v1/accounts/{account_id}")
    assert response.status_code == 200, response.text
    return Decimal(response.json()["balance"])


def test_workspace_local_status_changes_only_at_local_midnight(monkeypatch):
    workspace = SimpleNamespace(timezone="Asia/Ho_Chi_Minh")
    period = SimpleNamespace(
        start_date=datetime(2026, 8, 8).date(),
        end_date=datetime(2026, 8, 8).date(),
        closed_at=None,
    )

    class BeforeMidnight(datetime):
        @classmethod
        def now(cls, timezone=None):
            value = datetime(2026, 8, 8, 16, 59, 59, tzinfo=UTC)
            return value if timezone is None else value.astimezone(timezone)

    monkeypatch.setattr("app.periods.datetime", BeforeMidnight)
    before = workspace_today(workspace)
    assert before == datetime(2026, 8, 8).date()
    assert period_status(period, before) == "current"

    class AtMidnight(datetime):
        @classmethod
        def now(cls, timezone=None):
            value = datetime(2026, 8, 8, 17, 0, 0, tzinfo=UTC)
            return value if timezone is None else value.astimezone(timezone)

    monkeypatch.setattr("app.periods.datetime", AtMidnight)
    after = workspace_today(workspace)
    assert after == datetime(2026, 8, 9).date()
    assert period_status(period, after) == "ended"
    period.closed_at = datetime(2026, 8, 8, 12, 0)
    assert period_status(period, before) == "closed"


async def test_natural_expiry_get_list_close_and_edit_are_persistence_neutral(client):
    await register(client)
    account = await create_account(client, "Naturally ended USD", "USD", "100")
    today = local_today()
    period = await create_period(
        client,
        account["id"],
        "100",
        today - timedelta(days=4),
        today - timedelta(days=2),
    )
    before = await persisted_period_state(client, period["id"])
    assert before[-2:] == (None, None)

    fetched = await client.get(f"/api/v1/account-periods/{period['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "ended"
    history = await client.get(
        f"/api/v1/accounts/{account['id']}/periods", params={"scope": "history"}
    )
    assert history.status_code == 200
    assert [item["id"] for item in history.json()] == [period["id"]]
    assert await persisted_period_state(client, period["id"]) == before

    edited = await client.patch(
        f"/api/v1/account-periods/{period['id']}",
        json={"end_date": today.isoformat(), "confirm_ended_period": True},
    )
    assert edited.status_code == 409
    assert edited.json()["detail"] == "Ended account period is read-only"
    closed = await client.post(f"/api/v1/account-periods/{period['id']}/close")
    assert closed.status_code == 409
    assert closed.json()["detail"] == "Ended account period is read-only"
    assert await persisted_period_state(client, period["id"]) == before


async def test_manual_close_captures_exact_balance_without_mutating_ledger(
    client, monkeypatch
):
    await register(client)
    account = await create_account(client, "Exact close BTC", "BTC", "0")
    today = local_today()
    period = await create_period(client, account["id"], "0", today, today)
    fixed = datetime.now(UTC).replace(tzinfo=None, microsecond=123456)
    exact = Decimal("0.123456789012345678")
    await add_test_leg(client, account["id"], str(exact), fixed)
    await add_test_leg(client, account["id"], "9", fixed, status="voided")
    await add_test_leg(client, account["id"], "1", fixed + timedelta(microseconds=1))
    ledger_before = await account_ledger_rows(client, account["id"])

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, timezone=None):
            aware = fixed.replace(tzinfo=UTC)
            return aware if timezone is None else aware.astimezone(timezone)

    monkeypatch.setattr("app.periods.datetime", FrozenDateTime)
    closed = await client.post(f"/api/v1/account-periods/{period['id']}/close")
    assert closed.status_code == 200, closed.text
    state = await persisted_period_state(client, period["id"])
    assert state[-2:] == (fixed, exact)
    assert await account_ledger_rows(client, account["id"]) == ledger_before


async def test_closed_snapshots_survive_correction_delete_and_undo(client):
    await register(client)
    account = await create_account(client, "Closed edits USD", "USD", "100")
    period = await create_period(client, account["id"], "100")
    spent = await client.post(
        "/api/v1/operations/spend",
        json={"account_id": account["id"], "amount": "10"},
    )
    assert spent.status_code == 201, spent.text
    closed = await client.post(f"/api/v1/account-periods/{period['id']}/close")
    assert closed.status_code == 200, closed.text
    closed_state = await persisted_period_state(client, period["id"])

    corrected = await client.patch(
        f"/api/v1/transactions/{spent.json()['id']}", json={"amount": "20"}
    )
    assert corrected.status_code == 200, corrected.text
    assert await account_balance(client, account["id"]) == Decimal("80")
    assert await persisted_period_state(client, period["id"]) == closed_state

    deleted = await client.post(f"/api/v1/transactions/{spent.json()['id']}/delete")
    assert deleted.status_code == 200, deleted.text
    assert await account_balance(client, account["id"]) == Decimal("100")
    assert await persisted_period_state(client, period["id"]) == closed_state

    later = await client.post(
        "/api/v1/operations/spend",
        json={"account_id": account["id"], "amount": "5"},
    )
    assert later.status_code == 201, later.text
    assert await persisted_period_state(client, period["id"]) == closed_state
    undone = await client.post(
        f"/api/v1/operations/accounts/{account['id']}/undo",
        json={"transaction_id": later.json()["id"]},
    )
    assert undone.status_code == 200, undone.text
    assert await account_balance(client, account["id"]) == Decimal("100")
    assert await persisted_period_state(client, period["id"]) == closed_state
