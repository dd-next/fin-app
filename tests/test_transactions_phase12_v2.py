from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select, update

from app.models import AccountPeriod, Transaction, TransactionLeg, Workspace
from app.periods import (
    current_period_allowance,
    workspace_day_at,
    workspace_day_boundary,
)
from tests.conftest import register
from tests.test_ledger_v2 import create_account
from tests.test_periods_v2 import add_test_leg, create_period, local_today
from tests.test_sharing_v2 import accept, invitation, login


async def test_period_filter_uses_canonical_window_for_all_financial_types(client):
    await register(client)
    usd = await create_account(client, "Period history USD", "USD", "1000")
    other_usd = await create_account(client, "Period target USD", "USD", "0")
    vnd = await create_account(client, "Period target VND", "VND", "0")
    today = local_today()
    period = await create_period(
        client,
        usd["id"],
        "1000",
        start=today - timedelta(days=1),
        end=today + timedelta(days=1),
    )

    responses = [
        await client.post(
            "/api/v1/operations/spend",
            json={"account_id": usd["id"], "amount": "10", "local_date": today.isoformat()},
        ),
        await client.post(
            "/api/v1/operations/add-funds",
            json={"account_id": usd["id"], "amount": "20", "local_date": today.isoformat()},
        ),
        await client.post(
            "/api/v1/operations/transfer",
            json={
                "from_account_id": usd["id"],
                "to_account_id": other_usd["id"],
                "amount": "30",
                "local_date": today.isoformat(),
            },
        ),
        await client.post(
            "/api/v1/operations/exchange",
            json={
                "from_account_id": usd["id"],
                "from_amount": "40",
                "to_account_id": vnd["id"],
                "to_amount": "1000000",
                "local_date": today.isoformat(),
            },
        ),
    ]
    assert [response.status_code for response in responses] == [201, 201, 201, 201]
    outside = await client.post(
        "/api/v1/operations/spend",
        json={
            "account_id": usd["id"],
            "amount": "1",
            "local_date": (today + timedelta(days=2)).isoformat(),
        },
    )
    boundary = await client.post(
        "/api/v1/operations/spend",
        json={"account_id": usd["id"], "amount": "2", "local_date": today.isoformat()},
    )
    assert outside.status_code == boundary.status_code == 201
    async with client._finapp_test_sessions() as session:
        persisted_period = await session.get(AccountPeriod, period["id"])
        assert persisted_period is not None
        await session.execute(
            update(TransactionLeg)
            .where(TransactionLeg.transaction_id == boundary.json()["id"])
            .values(created_at=persisted_period.snapshot_at)
        )
        opening_id = (
            await session.execute(
                select(Transaction.id)
                .join(TransactionLeg)
                .where(
                    TransactionLeg.account_id == usd["id"],
                    Transaction.type == "adjustment",
                )
            )
        ).scalar_one()
        await session.commit()

    filtered = await client.get(f"/api/v1/transactions?period_id={period['id']}")
    assert filtered.status_code == 200, filtered.text
    items = filtered.json()["items"]
    assert {item["id"] for item in items} == {
        response.json()["id"] for response in responses
    } | {outside.json()["id"], opening_id}
    assert {item["type"] for item in items} == {
        "expense",
        "income",
        "transfer",
        "exchange",
        "adjustment",
    }
    assert any(item["type"] == "adjustment" for item in items)
    assert outside.json()["id"] in {item["id"] for item in items}
    assert boundary.json()["id"] not in {item["id"] for item in items}
    assert opening_id in {item["id"] for item in items}

    mismatched = await client.get(
        f"/api/v1/transactions?period_id={period['id']}&account_id={other_usd['id']}"
    )
    assert mismatched.status_code == 422


async def test_current_period_filter_matches_allowance_window_and_clamped_days(
    client, monkeypatch
):
    await register(client)
    account = await create_account(client, "Current audit USD", "USD", "0")
    other = await create_account(client, "Other audit USD", "USD", "0")
    today = local_today()
    start = today - timedelta(days=1)
    end = today + timedelta(days=1)
    period = await create_period(client, account["id"], "999", start, end)
    async with client._finapp_test_sessions() as session:
        workspace = await session.get(Workspace, account["workspace_id"])
        row = await session.get(AccountPeriod, period["id"])
        assert workspace is not None
        assert row is not None
        reference_time = workspace_day_boundary(workspace, today) + timedelta(hours=12)
        snapshot_at = row.snapshot_at

    snapshot_id = await add_test_leg(client, account["id"], "1", snapshot_at)
    backdated_id = await add_test_leg(
        client, account["id"], "2", snapshot_at + timedelta(hours=1)
    )
    future_dated_id = await add_test_leg(
        client, account["id"], "3", reference_time
    )
    after_cutoff_id = await add_test_leg(
        client, account["id"], "4", reference_time + timedelta(seconds=1)
    )
    voided_id = await add_test_leg(
        client,
        account["id"],
        "5",
        reference_time - timedelta(seconds=1),
        status="voided",
    )
    other_id = await add_test_leg(
        client, other["id"], "6", reference_time - timedelta(seconds=1)
    )
    async with client._finapp_test_sessions() as session:
        for transaction_id, financial_day in (
            (backdated_id, start - timedelta(days=10)),
            (future_dated_id, end + timedelta(days=10)),
            (after_cutoff_id, start),
        ):
            transaction = await session.get(Transaction, transaction_id)
            assert transaction is not None
            transaction.local_date = financial_day
        await session.commit()

    calls = []

    def frozen_reference_time():
        calls.append(True)
        return reference_time

    monkeypatch.setattr(
        "app.transactions.utc_reference_time", frozen_reference_time
    )
    response = await client.get(f"/api/v1/transactions?period_id={period['id']}")
    assert response.status_code == 200, response.text
    returned_ids = {item["id"] for item in response.json()["items"]}
    assert returned_ids == {backdated_id, future_dated_id}
    assert snapshot_id not in returned_ids
    assert after_cutoff_id not in returned_ids
    assert voided_id not in returned_ids
    assert other_id not in returned_ids
    assert calls == [True]

    async with client._finapp_test_sessions() as session:
        row = await session.get(AccountPeriod, period["id"])
        workspace = await session.get(Workspace, account["workspace_id"])
        assert row is not None
        assert workspace is not None
        reference_day = workspace_day_at(workspace, reference_time)
        projection = await current_period_allowance(
            session,
            row,
            reference_time=reference_time,
            reference_day=reference_day,
            quantum=Decimal("0.01"),
        )
        assert projection.effective_effects == (
            (start, Decimal("2")),
            (reference_day, Decimal("3")),
        )


async def test_closed_and_ended_period_filters_use_exact_lifecycle_cutoffs(
    client, monkeypatch
):
    await register(client)
    today = local_today()

    ended_account = await create_account(client, "Ended audit USD", "USD", "0")
    ended_period = await create_period(
        client,
        ended_account["id"],
        "999",
        today - timedelta(days=4),
        today - timedelta(days=2),
    )
    async with client._finapp_test_sessions() as session:
        workspace = await session.get(Workspace, ended_account["workspace_id"])
        ended_row = await session.get(AccountPeriod, ended_period["id"])
        assert workspace is not None
        assert ended_row is not None
        ended_snapshot = ended_row.snapshot_at
        ended_cutoff = workspace_day_boundary(
            workspace, ended_row.end_date + timedelta(days=1)
        )
    ended_snapshot_id = await add_test_leg(
        client, ended_account["id"], "1", ended_snapshot
    )
    ended_inside_id = await add_test_leg(
        client, ended_account["id"], "2", ended_cutoff - timedelta(microseconds=1)
    )
    ended_equal_id = await add_test_leg(
        client, ended_account["id"], "3", ended_cutoff
    )
    ended_after_id = await add_test_leg(
        client, ended_account["id"], "4", ended_cutoff + timedelta(microseconds=1)
    )
    ended_void_id = await add_test_leg(
        client,
        ended_account["id"],
        "5",
        ended_cutoff - timedelta(seconds=1),
        status="voided",
    )
    async with client._finapp_test_sessions() as session:
        inside = await session.get(Transaction, ended_inside_id)
        assert inside is not None
        inside.local_date = today + timedelta(days=20)
        await session.commit()
    ended_response = await client.get(
        f"/api/v1/transactions?period_id={ended_period['id']}"
    )
    assert ended_response.status_code == 200, ended_response.text
    ended_ids = {item["id"] for item in ended_response.json()["items"]}
    assert ended_ids == {ended_inside_id}
    assert not {
        ended_snapshot_id,
        ended_equal_id,
        ended_after_id,
        ended_void_id,
    }.intersection(ended_ids)

    closed_account = await create_account(client, "Closed audit USD", "USD", "0")
    closed_period = await create_period(
        client,
        closed_account["id"],
        "999",
        today - timedelta(days=1),
        today + timedelta(days=1),
    )
    async with client._finapp_test_sessions() as session:
        workspace = await session.get(Workspace, closed_account["workspace_id"])
        closed_row = await session.get(AccountPeriod, closed_period["id"])
        assert workspace is not None
        assert closed_row is not None
        closed_snapshot = closed_row.snapshot_at
        closed_at = workspace_day_boundary(workspace, today) + timedelta(hours=10)
    closed_snapshot_id = await add_test_leg(
        client, closed_account["id"], "1", closed_snapshot
    )
    closed_inside_id = await add_test_leg(
        client, closed_account["id"], "2", closed_at - timedelta(microseconds=1)
    )
    closed_equal_id = await add_test_leg(
        client, closed_account["id"], "3", closed_at
    )
    closed_after_id = await add_test_leg(
        client, closed_account["id"], "4", closed_at + timedelta(microseconds=1)
    )

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, timezone=None):
            aware = closed_at.replace(tzinfo=UTC)
            return aware if timezone is None else aware.astimezone(timezone)

    monkeypatch.setattr("app.periods.datetime", FrozenDateTime)
    closed = await client.post(
        f"/api/v1/account-periods/{closed_period['id']}/close"
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["closed_at"] == closed_at.isoformat()
    closed_response = await client.get(
        f"/api/v1/transactions?period_id={closed_period['id']}"
    )
    assert closed_response.status_code == 200, closed_response.text
    closed_ids = {item["id"] for item in closed_response.json()["items"]}
    assert closed_ids == {closed_inside_id, closed_equal_id}
    assert closed_snapshot_id not in closed_ids
    assert closed_after_id not in closed_ids


async def test_delete_is_soft_history_action_and_legacy_routes_are_absent(client):
    await register(client)
    account = await create_account(client, "Delete USD", "USD", "100")
    today = local_today()
    period = await create_period(
        client,
        account["id"],
        "100",
        start=today - timedelta(days=1),
        end=today + timedelta(days=1),
    )
    created = await client.post(
        "/api/v1/operations/spend",
        json={"account_id": account["id"], "amount": "25", "local_date": today.isoformat()},
    )
    assert created.status_code == 201, created.text
    transaction_id = created.json()["id"]
    assert Decimal((await client.get(f"/api/v1/accounts/{account['id']}")).json()["balance"]) == Decimal("75")
    assert Decimal((await client.get(f"/api/v1/account-periods/{period['id']}")).json()["remaining"]) == Decimal("75")

    deleted = await client.post(f"/api/v1/transactions/{transaction_id}/delete")
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["status"] == "deleted"
    assert deleted.json()["deleted_at"] is not None
    assert Decimal((await client.get(f"/api/v1/accounts/{account['id']}")).json()["balance"]) == Decimal("100")
    assert Decimal((await client.get(f"/api/v1/account-periods/{period['id']}")).json()["remaining"]) == Decimal("100")

    period_history = await client.get(
        f"/api/v1/transactions?period_id={period['id']}&status=deleted"
    )
    assert period_history.status_code == 200, period_history.text
    assert period_history.json()["items"] == []
    history = await client.get(
        "/api/v1/transactions?status=deleted"
    )
    assert history.status_code == 200, history.text
    assert [item["id"] for item in history.json()["items"]] == [transaction_id]
    assert history.json()["items"][0]["status"] == "deleted"
    assert (await client.get("/api/v1/transactions?status=voided")).status_code == 422
    assert (
        await client.post(f"/api/v1/transactions/{transaction_id}/void")
    ).status_code in {404, 405}

    paths = (await client.get("/openapi.json")).json()["paths"]
    assert "/api/v1/transactions/{transaction_id}/delete" in paths
    assert "/api/v1/transactions/{transaction_id}/void" not in paths
    for suffix in ("expense", "income", "transfer", "exchange", "adjustment"):
        assert f"/api/v1/transactions/{suffix}" not in paths


async def test_period_filter_is_owner_private_even_for_shared_account_access(client):
    await register(client)
    owner_account = await create_account(client, "Private period USD", "USD", "100")
    owner_period = await create_period(client, owner_account["id"], "100")
    token = await invitation(client, owner_account["id"], "viewer")

    await register(client, "bob")
    await accept(client, token)
    shared_lookup = await client.get(
        f"/api/v1/transactions?period_id={owner_period['id']}"
    )
    assert shared_lookup.status_code == 404
    assert shared_lookup.json()["detail"] == "Account period not found"

    bob_account = await create_account(client, "Bob period USD", "USD", "50")
    bob_period = await create_period(client, bob_account["id"], "50")
    await login(client, "alice")
    foreign_lookup = await client.get(
        f"/api/v1/transactions?period_id={bob_period['id']}"
    )
    assert foreign_lookup.status_code == 404
    assert foreign_lookup.json()["detail"] == "Account period not found"
