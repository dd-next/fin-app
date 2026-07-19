from decimal import Decimal

from tests.conftest import register
from tests.test_ledger_v2 import create_account

async def test_exchange_rate_lookup_is_isolated_between_workspaces(client):
    await register(client, "alice")
    alice_usd = await create_account(client, "Alice USD", "USD", "1000")
    alice_btc = await create_account(client, "Alice BTC", "BTC", "0")
    exchange = await client.post(
        "/api/v1/transactions/exchange",
        json={
            "from_account_id": alice_usd["id"],
            "from_amount": "100",
            "to_account_id": alice_btc["id"],
            "to_amount": "0.01",
        },
    )
    assert exchange.status_code == 201, exchange.text

    await client.post("/api/v1/auth/logout")
    await register(client, "bob")
    bob_btc = await create_account(client, "Bob BTC", "BTC", "1")

    rates = await client.get("/api/v1/exchange-rates")
    assert rates.status_code == 200, rates.text
    assert rates.json() == []

    summary = (await client.get("/api/v1/accounts/summary")).json()
    assert summary["net_worth"] == "0.00"
    assert summary["available"] == "0.00"
    assert summary["accounts"][0]["valued_balance"] is None
    assert summary["unvalued"] == [
        {
            "asset": {
                "id": bob_btc["asset"]["id"],
                "code": "BTC",
                "name": "Bitcoin",
                "kind": "crypto",
                "decimals": 8,
                "is_active": True,
            },
            "total": "1.00000000",
        }
    ]

async def test_rates_and_account_summary_use_output_precision_boundaries(client):
    await register(client)
    usd = await create_account(
        client, "Protected USD", "USD", "10", available=False
    )
    btc = await create_account(client, "Precise BTC", "BTC", "0.12345678")
    await create_account(client, "Precise ETH", "ETH", "0.123456789012345678")
    await create_account(client, "Whole VND", "VND", "7")

    exchange = await client.post(
        "/api/v1/transactions/exchange",
        json={
            "from_account_id": usd["id"],
            "from_amount": "1",
            "to_account_id": btc["id"],
            "to_amount": "0.03",
        },
    )
    assert exchange.status_code == 201, exchange.text

    rates = (await client.get("/api/v1/exchange-rates")).json()
    assert {item["base_asset"]["code"]: item["rate"] for item in rates} == {
        "BTC": "33.333333333333333333",
        "USD": "0.030000000000000000",
    }
    assert all(
        max(-Decimal(item["rate"]).as_tuple().exponent, 0) <= 18
        for item in rates
    )

    summary = (await client.get("/api/v1/accounts/summary")).json()
    accounts = {item["name"]: item for item in summary["accounts"]}
    assert accounts["Protected USD"]["balance"] == "9.00"
    assert accounts["Protected USD"]["valued_balance"] == "9.00"
    assert accounts["Precise BTC"]["balance"] == "0.15345678"
    assert accounts["Precise BTC"]["valued_balance"] == "5.12"
    assert accounts["Precise ETH"]["balance"] == "0.123456789012345678"
    assert accounts["Whole VND"]["balance"] == "7"
    assert summary["net_worth"] == "14.12"
    assert summary["available"] == "5.12"
    assert {
        item["asset"]["code"]: item["total"] for item in summary["unvalued"]
    } == {
        "ETH": "0.123456789012345678",
        "VND": "7",
    }


async def test_account_summary_rounds_the_exact_aggregate_only_once(client):
    await register(client)
    usd = await create_account(client, "Rate source USD", "USD", "1000")
    btc = await create_account(client, "Rate source BTC", "BTC", "0")
    exchange = await client.post(
        "/api/v1/transactions/exchange",
        json={
            "from_account_id": usd["id"],
            "from_amount": "1000",
            "to_account_id": btc["id"],
            "to_amount": "0.01",
        },
    )
    assert exchange.status_code == 201, exchange.text
    for index in range(10):
        await create_account(
            client,
            f"Micro BTC {index}",
            "BTC",
            "0.00000001",
        )

    summary = (await client.get("/api/v1/accounts/summary")).json()
    micros = [
        item for item in summary["accounts"] if item["name"].startswith("Micro BTC")
    ]
    assert len(micros) == 10
    assert {item["valued_balance"] for item in micros} == {"0.00"}
    assert summary["net_worth"] == "1000.01"
    assert summary["available"] == "1000.01"


async def test_unrepresentable_exchange_rate_is_rejected(client):
    await register(client)
    eth = await create_account(client, "Manual ETH", "ETH", "1")
    usd = await create_account(client, "Tiny-rate USD", "USD", "1")
    tiny_exchange = await client.post(
        "/api/v1/transactions/exchange",
        json={
            "from_account_id": usd["id"],
            "from_amount": "10000000000000000000",
            "to_account_id": eth["id"],
            "to_amount": "0.000000000000000001",
        },
    )
    assert tiny_exchange.status_code == 422
    assert "supported 18-decimal precision" in tiny_exchange.json()["detail"]
