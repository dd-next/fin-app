from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select, update

from app.models import AccountPeriod, Transaction, TransactionLeg
from tests.conftest import register
from tests.test_ledger_v2 import create_account
from tests.test_periods_v2 import create_period, local_today
from tests.test_sharing_v2 import accept, invitation, login


async def test_period_filter_uses_snapshot_leg_membership_for_all_financial_types(client):
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
            .values(created_at=persisted_period.created_at)
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
    }
    assert {item["type"] for item in items} == {
        "expense",
        "income",
        "transfer",
        "exchange",
    }
    assert all(item["type"] != "adjustment" for item in items)
    assert outside.json()["id"] not in {item["id"] for item in items}
    assert boundary.json()["id"] not in {item["id"] for item in items}
    assert opening_id not in {item["id"] for item in items}

    mismatched = await client.get(
        f"/api/v1/transactions?period_id={period['id']}&account_id={other_usd['id']}"
    )
    assert mismatched.status_code == 422


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
