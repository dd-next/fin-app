from datetime import UTC, datetime, timedelta
from decimal import Decimal, localcontext
from pathlib import Path

from sqlalchemy import select

from app.budget import compute_allowance
from app.models import AccountPeriod, RebaseEvent, Transaction, TransactionLeg, Workspace
from app.periods import current_period_allowance, workspace_day_boundary
from tests.conftest import register
from tests.test_ledger_v2 import create_account
from tests.test_periods_v2 import add_test_leg, create_period, local_today


COMMON_PERIOD_KEYS = {
    "id",
    "account_id",
    "asset",
    "created_by_user_id",
    "start_date",
    "end_date",
    "snapshot_at",
    "opening_balance",
    "rollover_policy",
    "status",
    "created_at",
    "closed_at",
    "closing_balance",
}
CURRENT_PERIOD_KEYS = COMMON_PERIOD_KEYS | {"current_balance", "available_today"}


async def stored_period_contract_state(client, period_id):
    async with client._finapp_test_sessions() as session:
        period = await session.get(AccountPeriod, period_id)
        assert period is not None
        transactions = list((await session.execute(select(Transaction))).scalars())
        legs = list((await session.execute(select(TransactionLeg))).scalars())
        rebases = list((await session.execute(select(RebaseEvent))).scalars())
        return (
            period.start_date,
            period.end_date,
            period.snapshot_at,
            period.opening_balance,
            period.rollover_policy,
            period.closed_at,
            period.closing_balance,
            len(transactions),
            len(legs),
            len(rebases),
        )


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

    period = await create_period(client, account["id"],  start, end)
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
    period = await create_period(client, account["id"],  start, end)

    response = await client.get(f"/api/v1/account-periods/{period['id']}")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["opening_balance"] == "6000000"
    assert payload["current_balance"] == "5980000"
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
    period = await create_period(client, account["id"],  today, today)

    first = await client.post(
        "/api/v1/operations/spend",
        json={"account_id": account["id"], "amount": "20"},
    )
    assert first.status_code == 201, first.text
    after_first = await client.get(f"/api/v1/account-periods/{period['id']}")
    assert after_first.status_code == 200
    assert after_first.json()["current_balance"] == "-10.00"
    assert after_first.json()["available_today"] == "-10.00"

    second = await client.post(
        "/api/v1/operations/spend",
        json={"account_id": account["id"], "amount": "5"},
    )
    assert second.status_code == 201, second.text
    after_second = await client.get(f"/api/v1/account-periods/{period['id']}")
    assert after_second.status_code == 200
    assert after_second.json()["current_balance"] == "-15.00"
    assert after_second.json()["available_today"] == "-15.00"


async def test_current_allowance_ignores_dormant_rebase_rows(client):
    await register(client)
    account = await create_account(client, "Dormant rebase USD", "USD", "300")
    today = local_today()
    period = await create_period(
        client, account["id"],  today, today + timedelta(days=2)
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
    assert after.json()["current_balance"] == before.json()["current_balance"]


async def test_create_defaults_current_lookup_and_exact_lifecycle_shapes(client):
    await register(client)
    account = await create_account(client, "Lifecycle shape USD", "USD", "100")
    today = local_today()
    created = await client.post(
        f"/api/v1/accounts/{account['id']}/periods",
        json={"end_date": (today + timedelta(days=2)).isoformat()},
    )
    assert created.status_code == 201, created.text
    current = created.json()
    assert set(current) == CURRENT_PERIOD_KEYS
    assert current["status"] == "current"
    assert current["start_date"] == today.isoformat()
    assert current["rollover_policy"] == "redistribute_remaining_days"
    assert current["closed_at"] is None
    assert current["closing_balance"] is None
    assert current["opening_balance"] == "0.00"
    assert current["current_balance"] == "100.00"

    lookup = await client.get(
        f"/api/v1/accounts/{account['id']}/periods/current"
    )
    assert lookup.status_code == 200
    assert lookup.json() == current

    closed = await client.post(
        f"/api/v1/account-periods/{current['id']}/close"
    )
    assert closed.status_code == 200, closed.text
    closed_payload = closed.json()
    assert set(closed_payload) == COMMON_PERIOD_KEYS
    assert closed_payload["status"] == "closed"
    assert closed_payload["closed_at"] is not None
    assert closed_payload["closing_balance"] == "100.00"
    assert "remaining" not in closed_payload
    assert "current_balance" not in closed_payload
    assert "available_today" not in closed_payload
    assert (
        await client.get(f"/api/v1/accounts/{account['id']}/periods/current")
    ).json() is None

    ended_account = await create_account(client, "Ended shape USD", "USD", "0")
    ended = await client.post(
        f"/api/v1/accounts/{ended_account['id']}/periods",
        json={
            "start_date": (today - timedelta(days=4)).isoformat(),
            "end_date": (today - timedelta(days=2)).isoformat(),
        },
    )
    assert ended.status_code == 201, ended.text
    ended_payload = ended.json()
    assert set(ended_payload) == COMMON_PERIOD_KEYS
    assert ended_payload["status"] == "ended"
    assert ended_payload["closed_at"] is None
    assert ended_payload["closing_balance"] is None
    assert "remaining" not in ended_payload
    assert "current_balance" not in ended_payload
    assert "available_today" not in ended_payload

    closed_history = (
        await client.get(
            f"/api/v1/accounts/{account['id']}/periods?scope=history"
        )
    ).json()
    ended_history = (
        await client.get(
            f"/api/v1/accounts/{ended_account['id']}/periods?scope=history"
        )
    ).json()
    history = closed_history + ended_history
    assert {item["status"] for item in history} == {"ended", "closed"}
    assert all(set(item) == COMMON_PERIOD_KEYS for item in history)


async def test_create_and_patch_policy_transition_without_financial_mutation(client):
    await register(client)
    account = await create_account(client, "Policy transition USD", "USD", "0")
    explicit_redistribute_account = await create_account(
        client, "Explicit redistribution USD", "USD", "0"
    )
    today = local_today()
    start = today - timedelta(days=1)
    end = today + timedelta(days=1)
    async with client._finapp_test_sessions() as session:
        transaction_count = len(
            list((await session.execute(select(Transaction))).scalars())
        )
        leg_count = len(list((await session.execute(select(TransactionLeg))).scalars()))
        rebase_count = len(
            list((await session.execute(select(RebaseEvent))).scalars())
        )
    explicit_redistribution = await client.post(
        f"/api/v1/accounts/{explicit_redistribute_account['id']}/periods",
        json={
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "rollover_policy": "redistribute_remaining_days",
        },
    )
    assert explicit_redistribution.status_code == 201, explicit_redistribution.text
    assert (
        explicit_redistribution.json()["rollover_policy"]
        == "redistribute_remaining_days"
    )
    explicit_state = await stored_period_contract_state(
        client, explicit_redistribution.json()["id"]
    )
    assert explicit_state[4] == "redistribute_remaining_days"
    assert explicit_state[7:] == (transaction_count, leg_count, rebase_count)

    async with client._finapp_test_sessions() as session:
        workspace = await session.get(Workspace, account["workspace_id"])
        assert workspace is not None
        start_boundary = workspace_day_boundary(workspace, start)
    await add_test_leg(client, account["id"], "120", start_boundary)

    created = await client.post(
        f"/api/v1/accounts/{account['id']}/periods",
        json={
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "rollover_policy": "carry_next_day",
        },
    )
    assert created.status_code == 201, created.text
    carried = created.json()
    assert carried["rollover_policy"] == "carry_next_day"
    assert carried["opening_balance"] == "120.00"
    spent = await client.post(
        "/api/v1/operations/spend",
        json={"account_id": account["id"], "amount": "30"},
    )
    assert spent.status_code == 201, spent.text
    before = await client.get(f"/api/v1/account-periods/{carried['id']}")
    assert before.status_code == 200
    state_before = await stored_period_contract_state(client, carried["id"])

    patched = await client.patch(
        f"/api/v1/account-periods/{carried['id']}",
        json={"rollover_policy": "redistribute_remaining_days"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["rollover_policy"] == "redistribute_remaining_days"
    assert patched.json()["available_today"] != before.json()["available_today"]
    state_after = await stored_period_contract_state(client, carried["id"])
    assert state_after[:4] == state_before[:4]
    assert state_after[4] == "redistribute_remaining_days"
    assert state_after[5:] == state_before[5:]

    combined_end = end + timedelta(days=1)
    combined = await client.patch(
        f"/api/v1/account-periods/{carried['id']}",
        json={
            "start_date": start.isoformat(),
            "end_date": combined_end.isoformat(),
            "rollover_policy": "carry_next_day",
        },
    )
    assert combined.status_code == 200, combined.text
    assert combined.json()["start_date"] == start.isoformat()
    assert combined.json()["end_date"] == combined_end.isoformat()
    assert combined.json()["rollover_policy"] == "carry_next_day"
    combined_state = await stored_period_contract_state(client, carried["id"])
    assert combined_state[0] == state_after[0]
    assert combined_state[1] == combined_end
    assert combined_state[2:4] == state_after[2:4]
    assert combined_state[4] == "carry_next_day"
    assert combined_state[5:] == state_after[5:]


async def test_patch_can_return_ended_shape_then_current_lookup_is_null(client):
    await register(client)
    account = await create_account(client, "Resulting ended USD", "USD", "10")
    today = local_today()
    current = await create_period(
        client,
        account["id"],

        today - timedelta(days=1),
        today + timedelta(days=1),
    )
    ended = await client.patch(
        f"/api/v1/account-periods/{current['id']}",
        json={
            "start_date": (today - timedelta(days=4)).isoformat(),
            "end_date": (today - timedelta(days=2)).isoformat(),
        },
    )
    assert ended.status_code == 200, ended.text
    assert set(ended.json()) == COMMON_PERIOD_KEYS
    assert ended.json()["status"] == "ended"
    assert "remaining" not in ended.json()
    assert (
        await client.get(f"/api/v1/accounts/{account['id']}/periods/current")
    ).json() is None


async def test_period_request_validation_is_exhaustive_and_mutation_neutral(client):
    await register(client)
    account = await create_account(client, "Validation USD", "USD", "25")
    today = local_today()
    create_route = f"/api/v1/accounts/{account['id']}/periods"
    async with client._finapp_test_sessions() as session:
        original_transactions = len(
            list((await session.execute(select(Transaction))).scalars())
        )
        original_legs = len(
            list((await session.execute(select(TransactionLeg))).scalars())
        )
    forbidden = {
        "snapshot_at": datetime.now(UTC).isoformat(),
        "opening_balance": "1",
        "closing_balance": "1",
        "current_balance": "1",
        "account_balance": "1",
        "remaining": "1",
        "planned": "1",
        "account_id": account["id"],
        "asset_id": account["asset"]["id"],
        "created_by_user_id": 1,
        "status": "current",
        "created_at": datetime.now(UTC).isoformat(),
        "closed_at": datetime.now(UTC).isoformat(),
    }
    invalid_create_bodies = [
        {"end_date": today.isoformat(), key: value}
        for key, value in forbidden.items()
    ] + [
        {"end_date": today.isoformat(), "start_date": None},
        {"end_date": today.isoformat(), "rollover_policy": None},
        {"end_date": today.isoformat(), "rollover_policy": "unknown"},
        {
            "start_date": (today + timedelta(days=1)).isoformat(),
            "end_date": (today + timedelta(days=2)).isoformat(),
        },
        {
            "start_date": today.isoformat(),
            "end_date": (today - timedelta(days=1)).isoformat(),
        },
    ]
    for body in invalid_create_bodies:
        response = await client.post(create_route, json=body)
        assert response.status_code == 422, (body, response.text)
    async with client._finapp_test_sessions() as session:
        assert list((await session.execute(select(AccountPeriod))).scalars()) == []
        assert len(list((await session.execute(select(Transaction))).scalars())) == (
            original_transactions
        )
        assert len(list((await session.execute(select(TransactionLeg))).scalars())) == (
            original_legs
        )

    valid = await client.post(create_route, json={"end_date": today.isoformat()})
    assert valid.status_code == 201, valid.text
    period_id = valid.json()["id"]
    before = await stored_period_contract_state(client, period_id)
    patch_route = f"/api/v1/account-periods/{period_id}"
    for key, value in forbidden.items():
        response = await client.patch(patch_route, json={key: value})
        assert response.status_code == 422, (key, response.text)
    for body in (
        {},
        {"confirm_ended_period": True},
        {"start_date": None},
        {"end_date": None},
        {"rollover_policy": None},
        {"rollover_policy": "unknown"},
    ):
        response = await client.patch(patch_route, json=body)
        assert response.status_code == 422, (body, response.text)
    assert await stored_period_contract_state(client, period_id) == before


async def test_response_quantization_preserves_stored_exact_money(client):
    await register(client)
    today = local_today()
    usd = await create_account(client, "Round half up USD", "USD", "0")
    eth = await create_account(client, "Exact ETH", "ETH", "0")
    for account, amount in (
        (usd, "1.005"),
        (eth, "0.123456789012345678"),
    ):
        async with client._finapp_test_sessions() as session:
            workspace = await session.get(Workspace, account["workspace_id"])
            assert workspace is not None
            boundary = workspace_day_boundary(workspace, today)
        await add_test_leg(client, account["id"], amount, boundary)
    usd_period = await create_period(client, usd["id"],  today, today)
    eth_period = await create_period(client, eth["id"],  today, today)
    assert usd_period["opening_balance"] == "1.01"
    assert usd_period["current_balance"] == "1.01"
    assert eth_period["opening_balance"] == "0.123456789012345678"
    assert eth_period["current_balance"] == "0.123456789012345678"
    async with client._finapp_test_sessions() as session:
        usd_row = await session.get(AccountPeriod, usd_period["id"])
        assert usd_row is not None
        assert usd_row.opening_balance == Decimal("1.005")


async def test_period_routes_capture_one_coherent_reference_time(client, monkeypatch):
    await register(client)
    account = await create_account(client, "Coherent list USD", "USD", "10")
    today = local_today()
    await create_period(
        client,
        account["id"],

        today - timedelta(days=3),
        today - timedelta(days=2),
    )
    await create_period(client, account["id"],  today, today)
    fixed = datetime.now(UTC).replace(tzinfo=None)
    calls = []

    class CountingDateTime(datetime):
        @classmethod
        def now(cls, timezone=None):
            calls.append(timezone)
            aware = fixed.replace(tzinfo=UTC)
            return aware if timezone is None else aware.astimezone(timezone)

    monkeypatch.setattr("app.periods.datetime", CountingDateTime)
    response = await client.get(f"/api/v1/accounts/{account['id']}/periods")
    assert response.status_code == 200, response.text
    assert {item["status"] for item in response.json()} == {"current", "ended"}
    assert calls == [UTC]


def test_period_routes_do_not_query_legacy_plan_or_rebase_inputs():
    source = Path("app/periods.py").read_text()
    assert "PlanOccurrence" not in source
    assert "PlanRule" not in source
    assert "RebaseEvent" not in source
    assert "compute_budget" not in source
