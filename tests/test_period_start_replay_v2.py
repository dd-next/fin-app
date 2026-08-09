import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.assets import seed_default_assets
from app.db import get_session
from app.ledger import account_balance
from app.main import app
from app.models import Account, AccountPeriod, Base, Transaction, TransactionLeg, Workspace
from app.periods import (
    current_period_balance_inputs,
    period_movements,
    workspace_day_boundary,
)
from tests.conftest import register
from tests.test_ledger_v2 import create_account
from tests.test_periods_v2 import add_test_leg, create_period, local_today


@pytest_asyncio.fixture
async def replay_concurrent_client(tmp_path):
    database_path = tmp_path / "period-start-replay.db"
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


async def persisted_period(client, period_id):
    async with client._finapp_test_sessions() as session:
        period = await session.get(AccountPeriod, period_id)
        assert period is not None
        return (
            period.start_date,
            period.end_date,
            period.snapshot_at,
            period.opening_balance,
            period.closed_at,
            period.closing_balance,
        )


async def ledger_rows(client, account_id):
    async with client._finapp_test_sessions() as session:
        rows = (
            await session.execute(
                select(
                    Transaction.id,
                    Transaction.status,
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


async def period_count(client, account_id):
    async with client._finapp_test_sessions() as session:
        return len(
            list(
                (
                    await session.execute(
                        select(AccountPeriod).where(
                            AccountPeriod.account_id == account_id
                        )
                    )
                ).scalars()
            )
        )


async def test_create_explicit_start_validation_and_snapshot_chronology(client):
    await register(client)
    today = local_today()

    past_account = await create_account(client, "Past start USD", "USD", "10")
    past = await client.post(
        f"/api/v1/accounts/{past_account['id']}/periods",
        json={
            "start_date": (today - timedelta(days=2)).isoformat(),
            "end_date": (today + timedelta(days=2)).isoformat(),
            "funding_amount": "999",
        },
    )
    assert past.status_code == 201, past.text

    today_account = await create_account(client, "Today start USD", "USD", "10")
    today_response = await client.post(
        f"/api/v1/accounts/{today_account['id']}/periods",
        json={
            "start_date": today.isoformat(),
            "end_date": today.isoformat(),
            "funding_amount": "999",
        },
    )
    assert today_response.status_code == 201, today_response.text

    future_account = await create_account(client, "Future start USD", "USD", "10")
    future = await client.post(
        f"/api/v1/accounts/{future_account['id']}/periods",
        json={
            "start_date": (today + timedelta(days=1)).isoformat(),
            "end_date": (today + timedelta(days=2)).isoformat(),
            "funding_amount": "999",
        },
    )
    assert future.status_code == 422
    assert future.json()["detail"] == "Start date must not be in the future"
    assert await period_count(client, future_account["id"]) == 0

    invalid_account = await create_account(client, "Invalid range USD", "USD", "10")
    invalid = await client.post(
        f"/api/v1/accounts/{invalid_account['id']}/periods",
        json={
            "start_date": today.isoformat(),
            "end_date": (today - timedelta(days=1)).isoformat(),
            "funding_amount": "999",
        },
    )
    assert invalid.status_code == 422
    assert invalid.json()["detail"] == "End date must not precede start date"
    assert await period_count(client, invalid_account["id"]) == 0

    chronology_account = await create_account(
        client, "Create chronology USD", "USD", "10"
    )
    await create_period(
        client,
        chronology_account["id"],
        "999",
        today - timedelta(days=5),
        today - timedelta(days=3),
    )
    before_ledger = await ledger_rows(client, chronology_account["id"])
    for end_date in (today - timedelta(days=3), today - timedelta(days=4)):
        rejected = await client.post(
            f"/api/v1/accounts/{chronology_account['id']}/periods",
            json={
                "start_date": (today - timedelta(days=5)).isoformat(),
                "end_date": end_date.isoformat(),
                "funding_amount": "999",
            },
        )
        assert rejected.status_code == 422
        assert rejected.json()["detail"] == (
            "Period snapshot must precede end boundary"
        )
    assert await period_count(client, chronology_account["id"]) == 1
    assert await ledger_rows(client, chronology_account["id"]) == before_ledger


async def test_start_replay_moves_backward_and_forward_without_ledger_change(client):
    await register(client)
    account = await create_account(client, "Replay precision BTC", "BTC", "0")
    today = local_today()
    async with client._finapp_test_sessions() as session:
        workspace = await session.get(Workspace, account["workspace_id"])
        assert workspace is not None
        backward_boundary = workspace_day_boundary(
            workspace, today - timedelta(days=2)
        )
        original_boundary = workspace_day_boundary(
            workspace, today - timedelta(days=1)
        )
        forward_boundary = workspace_day_boundary(workspace, today)

    await add_test_leg(
        client, account["id"], "5.000000000000000001", backward_boundary
    )
    await add_test_leg(
        client, account["id"], "10.000000000000000002", original_boundary
    )
    await add_test_leg(
        client,
        account["id"],
        "0.123456789012345678",
        original_boundary + timedelta(hours=1),
    )
    await add_test_leg(
        client,
        account["id"],
        "999",
        original_boundary + timedelta(hours=2),
        status="voided",
    )
    period = await create_period(
        client,
        account["id"],
        "999",
        today - timedelta(days=1),
        today + timedelta(days=2),
    )
    original_ledger = await ledger_rows(client, account["id"])

    backward = await client.patch(
        f"/api/v1/account-periods/{period['id']}",
        json={"start_date": (today - timedelta(days=2)).isoformat()},
    )
    assert backward.status_code == 200, backward.text
    assert backward.json()["funding_amount"] == "5.000000000000000001"

    reference_time = forward_boundary + timedelta(hours=1)
    async with client._finapp_test_sessions() as session:
        row = await session.get(AccountPeriod, period["id"])
        assert row is not None
        assert row.snapshot_at == backward_boundary
        assert row.opening_balance == Decimal("5.000000000000000001")
        movements = await period_movements(
            session, row, reference_time=reference_time
        )
        assert movements == [
            (today - timedelta(days=1), Decimal("10.000000000000000002")),
            (today - timedelta(days=1), Decimal("0.123456789012345678")),
        ]
        inputs = await current_period_balance_inputs(
            session, row, reference_time=reference_time
        )
        exact = Decimal("15.123456789012345681")
        assert inputs.current_balance == exact
        assert inputs.current_balance == await account_balance(
            session, account["id"], through=reference_time
        )
        assert inputs.window_net == Decimal("10.123456789012345680")
        assert inputs.reconciliation_delta == 0
        assert inputs.calculation_opening_balance == row.opening_balance

    forward = await client.patch(
        f"/api/v1/account-periods/{period['id']}",
        json={"start_date": today.isoformat()},
    )
    assert forward.status_code == 200, forward.text
    async with client._finapp_test_sessions() as session:
        row = await session.get(AccountPeriod, period["id"])
        assert row is not None
        assert row.snapshot_at == forward_boundary
        assert row.opening_balance == Decimal("15.123456789012345681")
        assert await period_movements(
            session, row, reference_time=reference_time
        ) == []
    assert await ledger_rows(client, account["id"]) == original_ledger


async def test_replay_failure_rolls_back_period_and_ledger(client, monkeypatch):
    await register(client)
    account = await create_account(client, "Replay rollback USD", "USD", "100")
    today = local_today()
    period = await create_period(
        client, account["id"], "999", today - timedelta(days=1), today + timedelta(days=2)
    )
    before_period = await persisted_period(client, period["id"])
    before_ledger = await ledger_rows(client, account["id"])

    future = await client.patch(
        f"/api/v1/account-periods/{period['id']}",
        json={"start_date": (today + timedelta(days=1)).isoformat()},
    )
    assert future.status_code == 422
    assert future.json()["detail"] == "Start date must not be in the future"
    assert await persisted_period(client, period["id"]) == before_period
    assert await ledger_rows(client, account["id"]) == before_ledger

    null_start = await client.patch(
        f"/api/v1/account-periods/{period['id']}",
        json={"start_date": None},
    )
    assert null_start.status_code == 422
    assert null_start.json()["detail"] == "Period fields cannot be null"
    assert await persisted_period(client, period["id"]) == before_period
    assert await ledger_rows(client, account["id"]) == before_ledger

    async def fail_balance(*args, **kwargs):
        raise RuntimeError("forced snapshot replay failure")

    monkeypatch.setattr("app.periods.posted_balance_at", fail_balance)
    with pytest.raises(RuntimeError, match="forced snapshot replay failure"):
        await client.patch(
            f"/api/v1/account-periods/{period['id']}",
            json={"start_date": (today - timedelta(days=2)).isoformat()},
        )
    assert await persisted_period(client, period["id"]) == before_period
    assert await ledger_rows(client, account["id"]) == before_ledger


async def test_resulting_ended_replay_is_strict_read_only_and_allows_successor(client):
    await register(client)
    account = await create_account(client, "Resulting ended USD", "USD", "0")
    today = local_today()
    async with client._finapp_test_sessions() as session:
        workspace = await session.get(Workspace, account["workspace_id"])
        assert workspace is not None
        selected_boundary = workspace_day_boundary(
            workspace, today - timedelta(days=3)
        )
        ended_boundary = workspace_day_boundary(workspace, today)

    await add_test_leg(client, account["id"], "7", selected_boundary)
    await add_test_leg(
        client, account["id"], "-2", ended_boundary - timedelta(minutes=1)
    )
    await add_test_leg(client, account["id"], "3", ended_boundary)
    period = await create_period(
        client,
        account["id"],
        "999",
        today - timedelta(days=2),
        today + timedelta(days=1),
    )

    ended = await client.patch(
        f"/api/v1/account-periods/{period['id']}",
        json={
            "start_date": (today - timedelta(days=3)).isoformat(),
            "end_date": (today - timedelta(days=1)).isoformat(),
        },
    )
    assert ended.status_code == 200, ended.text
    assert ended.json()["status"] == "ended"
    stored = await persisted_period(client, period["id"])
    assert stored[2] == selected_boundary
    assert stored[3:] == (Decimal("7"), None, None)

    async with client._finapp_test_sessions() as session:
        row = await session.get(AccountPeriod, period["id"])
        assert row is not None
        assert await period_movements(
            session,
            row,
            reference_time=ended_boundary,
            include_reference_time=False,
        ) == [(today - timedelta(days=1), Decimal("-2"))]

    immutable = await client.patch(
        f"/api/v1/account-periods/{period['id']}",
        json={"end_date": today.isoformat()},
    )
    assert immutable.status_code == 409
    assert immutable.json()["detail"] == "Ended account period is read-only"
    assert await persisted_period(client, period["id"]) == stored

    successor = await create_period(
        client, account["id"], "999", today, today + timedelta(days=2)
    )
    assert successor["status"] == "current"
    async with client._finapp_test_sessions() as session:
        row = await session.get(AccountPeriod, successor["id"])
        assert row is not None
        assert row.snapshot_at == ended_boundary
        assert row.opening_balance == Decimal("8")
        assert await period_movements(
            session, row, reference_time=ended_boundary
        ) == []


async def test_same_day_predecessor_overlap_and_end_chronology_guards(
    client, monkeypatch
):
    await register(client)
    account = await create_account(client, "Overlap successor USD", "USD", "0")
    today = local_today()
    async with client._finapp_test_sessions() as session:
        workspace = await session.get(Workspace, account["workspace_id"])
        assert workspace is not None
        today_boundary = workspace_day_boundary(workspace, today)

    predecessor = await create_period(
        client, account["id"], "999", today - timedelta(days=2), today + timedelta(days=5)
    )

    class BoundaryDateTime(datetime):
        @classmethod
        def now(cls, timezone=None):
            aware = today_boundary.replace(tzinfo=UTC)
            return aware if timezone is None else aware.astimezone(timezone)

    monkeypatch.setattr("app.periods.datetime", BoundaryDateTime)
    equality_leg = await add_test_leg(client, account["id"], "4", today_boundary)
    closed = await client.post(
        f"/api/v1/account-periods/{predecessor['id']}/close"
    )
    assert closed.status_code == 200, closed.text
    successor = await create_period(
        client, account["id"], "999", today, today + timedelta(days=4)
    )
    before_ledger = await ledger_rows(client, account["id"])

    overlap = await client.patch(
        f"/api/v1/account-periods/{successor['id']}",
        json={
            "start_date": (today - timedelta(days=3)).isoformat(),
            "end_date": (today + timedelta(days=3)).isoformat(),
        },
    )
    assert overlap.status_code == 200, overlap.text
    end_only_overlap = await client.patch(
        f"/api/v1/account-periods/{successor['id']}",
        json={"end_date": (today + timedelta(days=2)).isoformat()},
    )
    assert end_only_overlap.status_code == 200, end_only_overlap.text
    assert end_only_overlap.json()["start_date"] == (
        today - timedelta(days=3)
    ).isoformat()
    assert end_only_overlap.json()["end_date"] == (
        today + timedelta(days=2)
    ).isoformat()
    async with client._finapp_test_sessions() as session:
        row = await session.get(AccountPeriod, successor["id"])
        assert row is not None
        assert row.snapshot_at == today_boundary
        assert row.opening_balance == Decimal("4")
        assert await period_movements(
            session, row, reference_time=today_boundary
        ) == []
        equality_transaction = await session.get(Transaction, equality_leg)
        assert equality_transaction is not None
        assert equality_transaction.status == "posted"

    accepted_state = await persisted_period(client, successor["id"])
    for offset in (1, 2):
        rejected = await client.patch(
            f"/api/v1/account-periods/{successor['id']}",
            json={
                "start_date": (today - timedelta(days=offset)).isoformat(),
                "end_date": (today - timedelta(days=offset)).isoformat(),
            },
        )
        assert rejected.status_code == 422
        assert rejected.json()["detail"] == (
            "Period snapshot must precede end boundary"
        )
        assert await persisted_period(client, successor["id"]) == accepted_state
        assert await ledger_rows(client, account["id"]) == before_ledger


async def test_distinct_current_guard_and_other_account_patch_independence(client):
    await register(client)
    today = local_today()
    guarded_account = await create_account(client, "Duplicate current USD", "USD", "0")
    guarded = await create_period(
        client,
        guarded_account["id"],
        "999",
        today - timedelta(days=1),
        today + timedelta(days=2),
    )
    independent_account = await create_account(
        client, "Independent replay USD", "USD", "0"
    )
    independent = await create_period(
        client,
        independent_account["id"],
        "999",
        today - timedelta(days=1),
        today + timedelta(days=2),
    )

    async with client._finapp_test_sessions() as session:
        guarded_row = await session.get(AccountPeriod, guarded["id"])
        assert guarded_row is not None
        duplicate = AccountPeriod(
            account_id=guarded_row.account_id,
            asset_id=guarded_row.asset_id,
            created_by_user_id=guarded_row.created_by_user_id,
            start_date=guarded_row.start_date,
            end_date=guarded_row.end_date,
            snapshot_at=guarded_row.snapshot_at,
            opening_balance=guarded_row.opening_balance,
            rollover_policy=guarded_row.rollover_policy,
        )
        session.add(duplicate)
        await session.commit()
        await session.refresh(duplicate)
        duplicate_id = duplicate.id

    guarded_before = await persisted_period(client, guarded["id"])
    duplicate_before = await persisted_period(client, duplicate_id)
    guarded_ledger = await ledger_rows(client, guarded_account["id"])
    blocked = await client.patch(
        f"/api/v1/account-periods/{guarded['id']}",
        json={"start_date": (today - timedelta(days=2)).isoformat()},
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"] == "Account already has a current period"
    assert await persisted_period(client, guarded["id"]) == guarded_before
    assert await persisted_period(client, duplicate_id) == duplicate_before
    assert await ledger_rows(client, guarded_account["id"]) == guarded_ledger

    independent_before_ledger = await ledger_rows(client, independent_account["id"])
    moved = await client.patch(
        f"/api/v1/account-periods/{independent['id']}",
        json={"start_date": (today - timedelta(days=2)).isoformat()},
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["start_date"] == (today - timedelta(days=2)).isoformat()
    assert await persisted_period(client, guarded["id"]) == guarded_before
    assert await persisted_period(client, duplicate_id) == duplicate_before
    assert await ledger_rows(client, independent_account["id"]) == (
        independent_before_ledger
    )


async def test_stale_patch_waits_for_accepted_successor_and_does_not_revive_target(
    replay_concurrent_client,
    monkeypatch,
):
    client = replay_concurrent_client
    await register(client)
    account = await create_account(client, "Stale replay USD", "USD", "100")
    today = local_today()
    target = await create_period(
        client, account["id"], "999", today - timedelta(days=1), today + timedelta(days=2)
    )
    before_ledger = await ledger_rows(client, account["id"])
    sessions = client._finapp_test_sessions

    fixed = datetime.now(UTC).replace(tzinfo=None)
    reserve_entered = asyncio.Event()
    reserve_allowed = asyncio.Event()
    reserve_attempted = asyncio.Event()
    from app import periods as periods_module

    original_reserve = periods_module.reserve_period_writer

    async def controlled_reserve(session):
        reserve_entered.set()
        await reserve_allowed.wait()
        reserve_attempted.set()
        await original_reserve(session)

    monkeypatch.setattr(periods_module, "reserve_period_writer", controlled_reserve)
    stale_patch = asyncio.create_task(
        client.patch(
            f"/api/v1/account-periods/{target['id']}",
            json={"start_date": (today - timedelta(days=2)).isoformat()},
        )
    )
    await asyncio.wait_for(reserve_entered.wait(), timeout=1)

    async with sessions() as writer:
        await writer.execute(text("BEGIN IMMEDIATE"))
        target_row = await writer.get(AccountPeriod, target["id"])
        assert target_row is not None
        target_row.closed_at = fixed
        target_row.closing_balance = Decimal("100")
        successor_row = AccountPeriod(
            account_id=target_row.account_id,
            asset_id=target_row.asset_id,
            created_by_user_id=target_row.created_by_user_id,
            start_date=today,
            end_date=today + timedelta(days=2),
            snapshot_at=fixed,
            opening_balance=Decimal("100"),
            rollover_policy="redistribute_remaining_days",
        )
        writer.add(successor_row)
        await writer.flush()
        successor_id = successor_row.id
        target_snapshot_at = target_row.snapshot_at
        target_opening_balance = target_row.opening_balance

        reserve_allowed.set()
        await asyncio.wait_for(reserve_attempted.wait(), timeout=1)
        assert not stale_patch.done()
        await writer.commit()

    response = await stale_patch
    assert response.status_code == 409
    assert response.json()["detail"] == "Closed account period is read-only"
    assert await persisted_period(client, target["id"]) == (
        today - timedelta(days=1),
        today + timedelta(days=2),
        target_snapshot_at,
        target_opening_balance,
        fixed,
        Decimal("100"),
    )
    assert await ledger_rows(client, account["id"]) == before_ledger

    async with sessions() as session:
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
        assert [row.id for row in current_rows] == [successor_id]
