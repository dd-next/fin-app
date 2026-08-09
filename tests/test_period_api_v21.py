from datetime import timedelta
from decimal import Decimal, localcontext

from sqlalchemy import select

from app.budget import compute_allowance
from app.models import AccountPeriod, RebaseEvent, Transaction, TransactionLeg, Workspace
from app.periods import current_period_allowance, workspace_day_boundary
from tests.conftest import register
from tests.test_ledger_v2 import create_account
from tests.test_periods_v2 import add_test_leg, create_period, local_today


async def set_transaction_day(client, transaction_id, day):
    async with client._finapp_test_sessions() as session:
        transaction = await session.get(Transaction, transaction_id)
        assert transaction is not None
        transaction.local_date = day
        await session.commit()


async def test_canonical_projection_clamps_signed_effects_and_reconciles_exactly(
    client,
):
    await register(client)
    account = await create_account(client, "Projection precision BTC", "BTC", "0")
    today = local_today()
    start = today - timedelta(days=2)
    end = today + timedelta(days=2)
    async with client._finapp_test_sessions() as session:
        workspace = await session.get(Workspace, account["workspace_id"])
        assert workspace is not None
        snapshot_at = workspace_day_boundary(workspace, start)
        today_boundary = workspace_day_boundary(workspace, today)

    boundary_transaction_id = await add_test_leg(
        client, account["id"], "5.000000000000000001", snapshot_at
    )
    before_id = await add_test_leg(
        client, account["id"], "-2.000000000000000002", snapshot_at + timedelta(hours=1)
    )
    today_id = await add_test_leg(
        client,
        account["id"],
        "0.123456789012345678",
        snapshot_at + timedelta(hours=2),
    )
    future_id = await add_test_leg(
        client, account["id"], "3.000000000000000003", snapshot_at + timedelta(hours=3)
    )
    await add_test_leg(
        client,
        account["id"],
        "999",
        snapshot_at + timedelta(hours=4),
        status="voided",
    )
    await set_transaction_day(client, before_id, start - timedelta(days=10))
    await set_transaction_day(client, today_id, today)
    await set_transaction_day(client, future_id, end + timedelta(days=10))

    period = await create_period(client, account["id"], "999", start, end)
    reference_time = today_boundary + timedelta(hours=12)
    async with client._finapp_test_sessions() as session:
        boundary_leg = (
            await session.execute(
                select(TransactionLeg).where(
                    TransactionLeg.transaction_id == boundary_transaction_id
                )
            )
        ).scalar_one()
        boundary_leg.amount = Decimal("7.000000000000000001")
        await session.commit()

        row = await session.get(AccountPeriod, period["id"])
        assert row is not None
        projection = await current_period_allowance(
            session,
            row,
            reference_time=reference_time,
            reference_day=today,
            quantum=Decimal("0.000000000000000001"),
        )
        inputs = projection.balance_inputs
        exact_current = Decimal("8.123456789012345680")
        assert inputs.window_net == Decimal("1.123456789012345679")
        assert inputs.reconciliation_delta == Decimal("2.000000000000000000")
        assert inputs.calculation_opening_balance == Decimal(
            "7.000000000000000001"
        )
        assert inputs.current_balance == exact_current
        assert projection.effective_effects == (
            (start, Decimal("-2.000000000000000002")),
            (today, Decimal("0.123456789012345678")),
            (today, Decimal("3.000000000000000003")),
        )
        assert projection.allowance.current_balance == exact_current
        assert projection.allowance == compute_allowance(
            inputs.calculation_opening_balance,
            start,
            end,
            projection.effective_effects,
            rollover_policy="redistribute_remaining_days",
            today=today,
            quantum=Decimal("0.000000000000000001"),
        )

        row.rollover_policy = "carry_next_day"
        carried = await current_period_allowance(
            session,
            row,
            reference_time=reference_time,
            reference_day=today,
            quantum=Decimal("0.000000000000000001"),
        )
        assert carried.allowance.current_balance == exact_current
        assert carried.allowance == compute_allowance(
            inputs.calculation_opening_balance,
            start,
            end,
            projection.effective_effects,
            rollover_policy="carry_next_day",
            today=today,
            quantum=Decimal("0.000000000000000001"),
        )


async def test_vnd_api_fixture_uses_redistribution_without_hard_coded_values(client):
    await register(client)
    account = await create_account(client, "Allowance fixture VND", "VND", "0")
    today = local_today()
    start = today - timedelta(days=1)
    end = today + timedelta(days=14)
    async with client._finapp_test_sessions() as session:
        workspace = await session.get(Workspace, account["workspace_id"])
        assert workspace is not None
        start_boundary = workspace_day_boundary(workspace, start)
        today_boundary = workspace_day_boundary(workspace, today)

    await add_test_leg(client, account["id"], "6000000", start_boundary)
    await add_test_leg(
        client, account["id"], "-327731", start_boundary + timedelta(minutes=1)
    )
    await add_test_leg(client, account["id"], "307731", today_boundary)
    period = await create_period(client, account["id"], "1", start, end)

    response = await client.get(f"/api/v1/account-periods/{period['id']}")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["funding_amount"] == "6000000"
    assert payload["remaining"] == "5980000"
    assert payload["available_today"] == "685882"

    async with client._finapp_test_sessions() as session:
        row = await session.get(AccountPeriod, period["id"])
        assert row is not None
        projection = await current_period_allowance(
            session,
            row,
            reference_time=today_boundary + timedelta(hours=12),
            reference_day=today,
            quantum=Decimal("1"),
        )
        with localcontext() as context:
            context.prec = 100
            expected_base = Decimal("5672269") / Decimal("15")
        assert projection.allowance.daily_base_exact == expected_base
        assert projection.allowance.current_balance == Decimal("5980000")
        assert projection.allowance.available_today == Decimal("685882")


async def test_available_today_never_blocks_repeated_overspend(client):
    await register(client)
    account = await create_account(client, "Informational allowance USD", "USD", "10")
    today = local_today()
    period = await create_period(client, account["id"], "999", today, today)

    first = await client.post(
        "/api/v1/operations/spend",
        json={"account_id": account["id"], "amount": "20"},
    )
    assert first.status_code == 201, first.text
    after_first = await client.get(f"/api/v1/account-periods/{period['id']}")
    assert after_first.status_code == 200
    assert after_first.json()["remaining"] == "-10"
    assert after_first.json()["available_today"] == "-10.00"

    second = await client.post(
        "/api/v1/operations/spend",
        json={"account_id": account["id"], "amount": "5"},
    )
    assert second.status_code == 201, second.text
    after_second = await client.get(f"/api/v1/account-periods/{period['id']}")
    assert after_second.status_code == 200
    assert after_second.json()["remaining"] == "-15"
    assert after_second.json()["available_today"] == "-15.00"


async def test_current_allowance_ignores_dormant_rebase_rows(client):
    await register(client)
    account = await create_account(client, "Dormant rebase USD", "USD", "300")
    today = local_today()
    period = await create_period(
        client, account["id"], "999", today, today + timedelta(days=2)
    )
    before = await client.get(f"/api/v1/account-periods/{period['id']}")
    assert before.status_code == 200

    async with client._finapp_test_sessions() as session:
        session.add(
            RebaseEvent(
                account_period_id=period["id"],
                day=today,
                reason="legacy_manual",
            )
        )
        await session.commit()

    after = await client.get(f"/api/v1/account-periods/{period['id']}")
    assert after.status_code == 200
    assert after.json()["available_today"] == before.json()["available_today"]
    assert after.json()["remaining"] == before.json()["remaining"]
