import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.assets import seed_default_assets
from app.db import get_session
from app.main import app
from app.models import AccountPeriod, Base, Transaction, TransactionLeg, Workspace
from app.periods import period_movements, period_status, workspace_day_boundary, workspace_today
from tests.conftest import register
from tests.test_ledger_v2 import create_account
from tests.test_periods_v2 import add_test_leg, create_period, local_today


@pytest_asyncio.fixture
async def concurrent_client(tmp_path):
    database_path = tmp_path / "period-concurrency.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        await seed_default_assets(session)

    async def override_session():
        async with sessions() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as value:
        value._finapp_test_sessions = sessions
        yield value
    app.dependency_overrides.clear()
    await engine.dispose()


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


async def test_same_day_closed_successor_partitions_exact_close_boundary(
    client, monkeypatch
):
    await register(client)
    account = await create_account(client, "Same-day successor BTC", "BTC", "0")
    today = local_today()
    predecessor = await create_period(
        client, account["id"], "0", today, today + timedelta(days=5)
    )
    fixed = datetime.now(UTC).replace(tzinfo=None, microsecond=234567)
    exact = Decimal("0.333333333333333333")
    later = Decimal("0.000000000000000001")
    await add_test_leg(client, account["id"], str(exact), fixed)
    await add_test_leg(client, account["id"], str(later), fixed + timedelta(microseconds=1))

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, timezone=None):
            aware = fixed.replace(tzinfo=UTC)
            return aware if timezone is None else aware.astimezone(timezone)

    monkeypatch.setattr("app.periods.datetime", FrozenDateTime)
    closed = await client.post(f"/api/v1/account-periods/{predecessor['id']}/close")
    assert closed.status_code == 200, closed.text
    successor = await create_period(
        client, account["id"], "0", today, today + timedelta(days=2)
    )

    async with client._finapp_test_sessions() as session:
        predecessor_row = await session.get(AccountPeriod, predecessor["id"])
        successor_row = await session.get(AccountPeriod, successor["id"])
        assert predecessor_row is not None
        assert successor_row is not None
        assert predecessor_row.closed_at == fixed
        assert predecessor_row.closing_balance == exact
        assert successor_row.snapshot_at == fixed
        assert successor_row.opening_balance == exact
        assert await period_movements(
            session, predecessor_row, reference_time=fixed
        ) == [(today, exact)]
        assert await period_movements(
            session,
            successor_row,
            reference_time=fixed + timedelta(microseconds=1),
        ) == [(today, later)]


async def test_natural_successor_uses_latest_non_utc_end_boundary(client):
    await register(client)
    account = await create_account(client, "Natural successor USD", "USD", "0")
    today = local_today()
    older = await create_period(
        client,
        account["id"],
        "0",
        today - timedelta(days=9),
        today - timedelta(days=7),
    )
    latest = await create_period(
        client,
        account["id"],
        "0",
        today - timedelta(days=6),
        today - timedelta(days=2),
    )
    async with client._finapp_test_sessions() as session:
        workspace = await session.get(Workspace, account["workspace_id"])
        older_row = await session.get(AccountPeriod, older["id"])
        latest_row = await session.get(AccountPeriod, latest["id"])
        assert workspace is not None
        assert workspace.timezone != "UTC"
        assert older_row is not None
        assert latest_row is not None
        latest_boundary = workspace_day_boundary(
            workspace, latest_row.end_date + timedelta(days=1)
        )
        older_boundary = workspace_day_boundary(
            workspace, older_row.end_date + timedelta(days=1)
        )
        assert older_boundary < latest_boundary

    before = Decimal("3")
    exact = Decimal("7")
    after = Decimal("11")
    await add_test_leg(
        client, account["id"], str(before), latest_boundary - timedelta(microseconds=1)
    )
    await add_test_leg(client, account["id"], str(exact), latest_boundary)
    await add_test_leg(
        client, account["id"], str(after), latest_boundary + timedelta(microseconds=1)
    )
    successor = await create_period(
        client,
        account["id"],
        "0",
        today - timedelta(days=3),
        today + timedelta(days=2),
    )

    async with client._finapp_test_sessions() as session:
        latest_row = await session.get(AccountPeriod, latest["id"])
        successor_row = await session.get(AccountPeriod, successor["id"])
        assert latest_row is not None
        assert successor_row is not None
        assert latest_row.closed_at is None
        assert latest_row.closing_balance is None
        assert successor_row.snapshot_at == latest_boundary
        assert successor_row.opening_balance == before + exact
        assert await period_movements(
            session,
            latest_row,
            reference_time=latest_boundary,
            include_reference_time=False,
        ) == [(latest_row.end_date, before)]
        assert await period_movements(
            session,
            successor_row,
            reference_time=latest_boundary + timedelta(microseconds=1),
        ) == [(today - timedelta(days=1), after)]


async def test_only_same_account_current_period_blocks_creation(client):
    await register(client)
    first = await create_account(client, "Current guard one USD", "USD", "10")
    second = await create_account(client, "Current guard two USD", "USD", "20")
    today = local_today()
    await create_period(client, first["id"], "10", today, today + timedelta(days=2))

    blocked = await client.post(
        f"/api/v1/accounts/{first['id']}/periods",
        json={
            "start_date": (today - timedelta(days=1)).isoformat(),
            "end_date": (today + timedelta(days=1)).isoformat(),
            "funding_amount": "10",
        },
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"] == "Account already has a current period"

    independent = await create_period(
        client, second["id"], "20", today, today + timedelta(days=1)
    )
    assert independent["status"] == "current"


async def test_concurrent_current_period_creation_serializes_at_guard(
    concurrent_client,
):
    await register(concurrent_client)
    account = await create_account(
        concurrent_client, "Concurrent current USD", "USD", "100"
    )
    today = local_today()
    body = {
        "start_date": today.isoformat(),
        "end_date": (today + timedelta(days=2)).isoformat(),
        "funding_amount": "100",
    }

    first, second = await asyncio.gather(
        concurrent_client.post(
            f"/api/v1/accounts/{account['id']}/periods", json=body
        ),
        concurrent_client.post(
            f"/api/v1/accounts/{account['id']}/periods", json=body
        ),
    )
    assert sorted((first.status_code, second.status_code)) == [201, 409]
    conflict = first if first.status_code == 409 else second
    assert conflict.json()["detail"] == "Account already has a current period"

    async with concurrent_client._finapp_test_sessions() as session:
        current_rows = list(
            (
                await session.execute(
                    select(AccountPeriod).where(
                        AccountPeriod.account_id == account["id"],
                        AccountPeriod.closed_at.is_(None),
                        AccountPeriod.start_date <= today,
                        AccountPeriod.end_date >= today,
                    )
                )
            ).scalars()
        )
        assert len(current_rows) == 1
