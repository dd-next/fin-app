from datetime import timedelta
from decimal import Decimal

from tests.conftest import register
from tests.test_ledger_v2 import create_account
from tests.test_periods_v2 import create_period, local_today
from tests.test_sharing_v2 import accept, invitation, login


async def account_balance(client, account_id):
    return Decimal((await client.get(f"/api/v1/accounts/{account_id}")).json()["balance"])


async def test_operations_financial_actions_work_without_a_period(client):
    await register(client)
    source = await create_account(client, "Operations USD", "USD", "1000")
    target = await create_account(client, "Operations target USD", "USD", "0")
    vnd = await create_account(client, "Operations VND", "VND", "0")
    assert (await client.get(f"/api/v1/accounts/{source['id']}/periods")).json() == []

    spend = await client.post(
        "/api/v1/operations/spend",
        json={"account_id": source["id"], "amount": "20"},
    )
    assert spend.status_code == 201, spend.text
    assert spend.json()["type"] == "expense"
    assert spend.json()["origin"] == "operations"
    added = await client.post(
        "/api/v1/operations/add-funds",
        json={"account_id": source["id"], "amount": "5"},
    )
    assert added.status_code == 201, added.text
    assert added.json()["type"] == "income"
    assert added.json()["origin"] == "operations"
    transfer = await client.post(
        "/api/v1/operations/transfer",
        json={
            "from_account_id": source["id"],
            "to_account_id": target["id"],
            "amount": "100",
        },
    )
    assert transfer.status_code == 201, transfer.text
    assert transfer.json()["origin"] == "operations"
    exchange = await client.post(
        "/api/v1/operations/exchange",
        json={
            "from_account_id": source["id"],
            "from_amount": "10",
            "to_account_id": vnd["id"],
            "to_amount": "250000",
            "fee": {"account_id": source["id"], "amount": "2"},
        },
    )
    assert exchange.status_code == 201, exchange.text
    assert exchange.json()["origin"] == "operations"
    assert await account_balance(client, source["id"]) == Decimal("873")
    assert await account_balance(client, target["id"]) == Decimal("100")
    assert await account_balance(client, vnd["id"]) == Decimal("250000")
    assert (await client.get(f"/api/v1/accounts/{source['id']}/periods")).json() == []

    transactions = (await client.get("/api/v1/transactions?limit=20")).json()["items"]
    fee = next(item for item in transactions if item["parent_transaction_id"] == exchange.json()["id"])
    assert fee["type"] == "expense"
    assert fee["origin"] == "operations"


async def test_operations_actions_replay_selected_account_periods(client):
    await register(client)
    source = await create_account(client, "Period Operations source", "USD")
    target = await create_account(client, "Period Operations target", "USD")
    source_period = await create_period(client, source["id"], "500")
    target_period = await create_period(client, target["id"], "100")

    transfer = await client.post(
        "/api/v1/operations/transfer",
        json={
            "from_account_id": source["id"],
            "to_account_id": target["id"],
            "amount": "50",
        },
    )
    assert transfer.status_code == 201, transfer.text
    spend = await client.post(
        "/api/v1/operations/spend",
        json={"account_id": source["id"], "amount": "10"},
    )
    assert spend.status_code == 201, spend.text
    added = await client.post(
        "/api/v1/operations/add-funds",
        json={"account_id": target["id"], "amount": "5"},
    )
    assert added.status_code == 201, added.text
    assert (
        await client.get(f"/api/v1/account-periods/{source_period['id']}")
    ).json()["remaining"] == "-60.00"
    assert (
        await client.get(f"/api/v1/account-periods/{target_period['id']}")
    ).json()["remaining"] == "55.00"


async def test_operations_routes_keep_transaction_validation(client):
    await register(client)
    usd = await create_account(client, "Validation USD", "USD")
    other_usd = await create_account(client, "Validation other USD", "USD")
    vnd = await create_account(client, "Validation VND", "VND")
    assert (
        await client.post("/api/v1/operations/spend", json={"amount": "1"})
    ).status_code == 422
    assert (
        await client.post(
            "/api/v1/operations/transfer",
            json={"from_account_id": usd["id"], "to_account_id": vnd["id"], "amount": "1"},
        )
    ).status_code == 422
    assert (
        await client.post(
            "/api/v1/operations/exchange",
            json={
                "from_account_id": usd["id"],
                "from_amount": "1",
                "to_account_id": other_usd["id"],
                "to_amount": "1",
            },
        )
    ).status_code == 422


async def test_operations_enforce_every_account_role_and_keep_periods_private(client):
    await register(client)
    viewer = await create_account(client, "Operations viewer USD", "USD", "100")
    contributor = await create_account(client, "Operations contributor USD", "USD", "100")
    editor_source = await create_account(client, "Operations editor source USD", "USD", "100")
    editor_target = await create_account(client, "Operations editor target USD", "USD", "0")
    editor_vnd = await create_account(client, "Operations editor VND", "VND", "0")
    private_target = await create_account(client, "Operations private USD", "USD", "0")
    ended_date = local_today() - timedelta(days=7)
    await create_period(
        client,
        editor_source["id"],
        "100",
        ended_date - timedelta(days=2),
        ended_date + timedelta(days=2),
    )
    tokens = [
        await invitation(client, viewer["id"], "viewer"),
        await invitation(client, contributor["id"], "contributor"),
        await invitation(client, editor_source["id"], "editor"),
        await invitation(client, editor_target["id"], "editor"),
        await invitation(client, editor_vnd["id"], "editor"),
    ]

    await register(client, "bob")
    for token in tokens:
        await accept(client, token)

    assert (
        await client.post(
            "/api/v1/operations/spend",
            json={"account_id": viewer["id"], "amount": "1"},
        )
    ).status_code == 403
    contributor_spend = await client.post(
        "/api/v1/operations/spend",
        json={"account_id": contributor["id"], "amount": "2"},
    )
    assert contributor_spend.status_code == 201, contributor_spend.text
    assert contributor_spend.json()["has_hidden_legs"] is False
    assert (
        await client.post(
            "/api/v1/operations/add-funds",
            json={"account_id": contributor["id"], "amount": "2"},
        )
    ).status_code == 403
    assert (
        await client.post(
            "/api/v1/operations/add-funds",
            json={"account_id": editor_target["id"], "amount": "2"},
        )
    ).status_code == 201
    transfer = await client.post(
        "/api/v1/operations/transfer",
        json={
            "from_account_id": editor_source["id"],
            "to_account_id": editor_target["id"],
            "amount": "3",
        },
    )
    assert transfer.status_code == 201, transfer.text
    assert {leg["account_id"] for leg in transfer.json()["legs"]} == {
        editor_source["id"],
        editor_target["id"],
    }
    assert (
        await client.post(
            "/api/v1/operations/transfer",
            json={
                "from_account_id": editor_source["id"],
                "to_account_id": contributor["id"],
                "amount": "1",
            },
        )
    ).status_code == 403
    hidden_target = await client.post(
        "/api/v1/operations/transfer",
        json={
            "from_account_id": editor_source["id"],
            "to_account_id": private_target["id"],
            "amount": "1",
        },
    )
    assert hidden_target.status_code == 404
    assert hidden_target.json()["detail"] == "Account not found"
    assert (
        await client.post(
            "/api/v1/operations/exchange",
            json={
                "from_account_id": editor_source["id"],
                "from_amount": "1",
                "to_account_id": editor_vnd["id"],
                "to_amount": "25000",
                "fee": {"account_id": contributor["id"], "amount": "1"},
            },
        )
    ).status_code == 403

    guarded = await client.post(
        "/api/v1/operations/spend",
        json={
            "account_id": editor_source["id"],
            "amount": "1",
            "local_date": ended_date.isoformat(),
        },
    )
    assert guarded.status_code == 409
    assert guarded.json()["detail"] == "Transaction change requires explicit confirmation"

    await login(client, "alice")
    assert await account_balance(client, private_target["id"]) == Decimal("0")


async def test_transaction_creation_routes_are_absent_and_operations_set_origin(client):
    await register(client)
    usd = await create_account(client, "Manual source USD", "USD", "100")
    other_usd = await create_account(client, "Manual target USD", "USD", "0")
    vnd = await create_account(client, "Manual target VND", "VND", "0")

    legacy_requests = [
        ("expense", {"account_id": usd["id"], "amount": "1"}),
        ("income", {"account_id": usd["id"], "amount": "1"}),
        (
            "transfer",
            {
                "from_account_id": usd["id"],
                "to_account_id": other_usd["id"],
                "amount": "1",
            },
        ),
        (
            "exchange",
            {
                "from_account_id": usd["id"],
                "from_amount": "1",
                "to_account_id": vnd["id"],
                "to_amount": "25000",
            },
        ),
        ("adjustment", {"account_id": usd["id"], "delta": "1"}),
    ]
    for route, body in legacy_requests:
        response = await client.post(f"/api/v1/transactions/{route}", json=body)
        assert response.status_code in {404, 405}

    responses = [
        await client.post(
            "/api/v1/operations/spend",
            json={"account_id": usd["id"], "amount": "1"},
        ),
        await client.post(
            "/api/v1/operations/add-funds",
            json={"account_id": usd["id"], "amount": "1"},
        ),
        await client.post(
            "/api/v1/operations/transfer",
            json={
                "from_account_id": usd["id"],
                "to_account_id": other_usd["id"],
                "amount": "1",
            },
        ),
        await client.post(
            "/api/v1/operations/exchange",
            json={
                "from_account_id": usd["id"],
                "from_amount": "1",
                "to_account_id": vnd["id"],
                "to_amount": "25000",
                "fee": {"account_id": usd["id"], "amount": "0.5"},
            },
        ),
    ]
    assert [response.status_code for response in responses] == [201, 201, 201, 201]
    assert {response.json()["origin"] for response in responses} == {"operations"}
    transactions = (await client.get("/api/v1/transactions?limit=20")).json()["items"]
    operations_exchange = responses[-1].json()
    fee = next(
        item
        for item in transactions
        if item["parent_transaction_id"] == operations_exchange["id"]
    )
    assert fee["origin"] == "operations"

    paths = (await client.get("/openapi.json")).json()["paths"]
    for route, _ in legacy_requests:
        assert f"/api/v1/transactions/{route}" not in paths
