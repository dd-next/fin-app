from decimal import Decimal, localcontext
from types import SimpleNamespace

from app.ledger import quantize_main_amount
from tests.conftest import register
from tests.test_ledger_v2 import create_account
from tests.test_sharing_v2 import accept, invitation, login


def account_named(summary: dict, name: str) -> dict:
    return next(item for item in summary["accounts"] if item["name"] == name)


def test_main_currency_rounding_is_centralized_and_half_up():
    usd = SimpleNamespace(decimals=2)
    vnd = SimpleNamespace(decimals=0)
    assert quantize_main_amount(Decimal("1.005"), usd) == Decimal("1.01")
    assert quantize_main_amount(Decimal("-1.005"), usd) == Decimal("-1.01")
    assert quantize_main_amount(Decimal("1.5"), vnd) == Decimal("2")


async def test_ledger_precision_is_preserved_before_main_currency_display(client):
    context = await register(client)
    workspace_id = context["workspace"]["id"]
    eth = await create_account(
        client, "Precise ETH", "ETH", "0.123456789012345678"
    )
    saved = await client.put(
        f"/api/v1/workspaces/{workspace_id}/valuation-rates/ETH",
        json={"displayed_rate": "0.000001"},
    )
    assert saved.status_code == 200, saved.text
    account = (await client.get(f"/api/v1/accounts/{eth['id']}")).json()
    assert account["balance"] == "0.123456789012345678"
    assert account["valued_balance"] == "123456.79"
    transaction = (await client.get("/api/v1/transactions?limit=10")).json()[
        "items"
    ][0]
    assert transaction["legs"][0]["amount"] == "0.123456789012345678"


async def test_38_digit_balance_and_direct_rate_math_stay_exact(client):
    context = await register(client)
    workspace_id = context["workspace"]["id"]
    changed = await client.patch(
        f"/api/v1/workspaces/{workspace_id}",
        json={"base_asset_code": "BTC"},
    )
    assert changed.status_code == 200, changed.text

    holding = await create_account(
        client,
        "Maximum ETH",
        "ETH",
        "99999999999999999999.123456789012345678",
    )
    smallest_unit = await client.post(
        "/api/v1/transactions/adjustment",
        json={"account_id": holding["id"], "delta": "0.000000000000000001"},
    )
    assert smallest_unit.status_code == 201, smallest_unit.text

    rate_source = await create_account(client, "Rate source ETH", "ETH", "1")
    rate_target = await create_account(client, "Rate target BTC", "BTC", "0")
    exchange = await client.post(
        "/api/v1/transactions/exchange",
        json={
            "from_account_id": rate_source["id"],
            "from_amount": "1",
            "to_account_id": rate_target["id"],
            "to_amount": "0.12345678",
        },
    )
    assert exchange.status_code == 201, exchange.text

    account = (await client.get(f"/api/v1/accounts/{holding['id']}")).json()
    assert account["balance"] == "99999999999999999999.123456789012345679"
    assert account["valued_balance"] == "12345677999999999999.89178480"
    summary = (await client.get("/api/v1/accounts/summary")).json()
    assert summary["net_worth"] == "12345678000000000000.01524158"

    outgoing = await client.post(
        "/api/v1/transactions/expense",
        json={
            "account_id": holding["id"],
            "amount": "99999999999999999999.123456789012345678",
        },
    )
    assert outgoing.status_code == 201, outgoing.text
    assert (
        outgoing.json()["legs"][0]["amount"]
        == "-99999999999999999999.123456789012345678"
    )
    remaining = (await client.get(f"/api/v1/accounts/{holding['id']}")).json()
    assert remaining["balance"] == "1E-18"


async def test_manual_override_delete_exchange_fallback_and_unvalued(client):
    context = await register(client)
    workspace_id = context["workspace"]["id"]
    usd = await create_account(client, "Rate USD", "USD", "10")
    vnd = await create_account(client, "Rate VND", "VND", "0")
    exchange = await client.post(
        "/api/v1/transactions/exchange",
        json={
            "from_account_id": usd["id"],
            "from_amount": "1",
            "to_account_id": vnd["id"],
            "to_amount": "25000",
        },
    )
    assert exchange.status_code == 201, exchange.text
    regression = await create_account(
        client, "Regression VND", "VND", "15258400"
    )
    assert regression["valued_balance"] == "610.34"

    route = f"/api/v1/workspaces/{workspace_id}/valuation-rates/VND"
    saved = await client.put(route, json={"displayed_rate": "26292"})
    assert saved.status_code == 200, saved.text
    payload = saved.json()
    assert payload["workspace_id"] == workspace_id
    assert payload["main_asset"]["code"] == "USD"
    assert payload["asset"]["code"] == "VND"
    assert Decimal(payload["displayed_rate"]) == Decimal("26292")
    with localcontext() as context:
        context.prec = 80
        product = (
            Decimal(payload["displayed_rate"])
            * Decimal(payload["effective_valuation_rate"])
        )
    assert abs(product - Decimal(1)) < Decimal("1e-75")
    summary = (await client.get("/api/v1/accounts/summary")).json()
    assert account_named(summary, "Regression VND")["valued_balance"] == "580.34"

    listed = await client.get(
        f"/api/v1/workspaces/{workspace_id}/valuation-rates"
    )
    assert listed.status_code == 200, listed.text
    assert [item["id"] for item in listed.json()] == [payload["id"]]
    rejected_main = await client.put(
        f"/api/v1/workspaces/{workspace_id}/valuation-rates/USD",
        json={"displayed_rate": "2"},
    )
    assert rejected_main.status_code == 422
    assert "exactly 1" in rejected_main.json()["detail"]

    deleted = await client.delete(route)
    assert deleted.status_code == 204, deleted.text
    summary = (await client.get("/api/v1/accounts/summary")).json()
    assert account_named(summary, "Regression VND")["valued_balance"] == "610.34"

    voided = await client.post(
        f"/api/v1/transactions/{exchange.json()['id']}/void"
    )
    assert voided.status_code == 200, voided.text
    summary = (await client.get("/api/v1/accounts/summary")).json()
    assert account_named(summary, "Regression VND")["valued_balance"] is None
    assert {item["asset"]["code"] for item in summary["unvalued"]} == {"VND"}


async def test_main_currency_change_activates_only_its_saved_rate_pair(client):
    context = await register(client)
    workspace_id = context["workspace"]["id"]
    rates_route = f"/api/v1/workspaces/{workspace_id}/valuation-rates"
    usd_rate = await client.put(
        f"{rates_route}/VND", json={"displayed_rate": "26292"}
    )
    assert usd_rate.status_code == 200, usd_rate.text

    changed = await client.patch(
        f"/api/v1/workspaces/{workspace_id}",
        json={"base_asset_code": "EUR"},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["base_asset"]["code"] == "EUR"
    assert (await client.get(rates_route)).json() == []

    eur_rate = await client.put(
        f"{rates_route}/VND", json={"displayed_rate": "25000"}
    )
    assert eur_rate.status_code == 200, eur_rate.text
    assert eur_rate.json()["main_asset"]["code"] == "EUR"
    assert eur_rate.json()["id"] != usd_rate.json()["id"]

    changed_back = await client.patch(
        f"/api/v1/workspaces/{workspace_id}",
        json={"base_asset_code": "USD"},
    )
    assert changed_back.status_code == 200, changed_back.text
    listed = (await client.get(rates_route)).json()
    assert len(listed) == 1
    assert listed[0]["id"] == usd_rate.json()["id"]
    assert listed[0]["displayed_rate"] == "26292"


async def test_shared_account_never_discloses_owner_workspace_rate(client):
    alice = await register(client)
    workspace_id = alice["workspace"]["id"]
    shared = await create_account(client, "Shared BTC", "BTC", "1")
    alice_rate = await client.put(
        f"/api/v1/workspaces/{workspace_id}/valuation-rates/BTC",
        json={"displayed_rate": "0.00002"},
    )
    assert alice_rate.status_code == 200, alice_rate.text
    assert shared["valued_balance"] is None
    alice_summary = (await client.get("/api/v1/accounts/summary")).json()
    assert account_named(alice_summary, "Shared BTC")["valued_balance"] == "50000.00"
    token = await invitation(client, shared["id"], "viewer")

    bob = await register(client, "bob")
    await accept(client, token)
    bob_workspace_id = bob["workspace"]["id"]
    bob_summary = (await client.get("/api/v1/accounts/summary")).json()
    assert account_named(bob_summary, "Shared BTC")["valued_balance"] is None
    assert (
        await client.get(
            f"/api/v1/workspaces/{bob_workspace_id}/valuation-rates"
        )
    ).json() == []
    assert (
        await client.get(
            f"/api/v1/workspaces/{workspace_id}/valuation-rates"
        )
    ).status_code == 404
    assert (
        await client.put(
            f"/api/v1/workspaces/{workspace_id}/valuation-rates/BTC",
            json={"displayed_rate": "0.00001"},
        )
    ).status_code == 404
    assert (
        await client.delete(
            f"/api/v1/workspaces/{workspace_id}/valuation-rates/BTC"
        )
    ).status_code == 404

    await login(client, "alice")
    alice_rates = (
        await client.get(
            f"/api/v1/workspaces/{workspace_id}/valuation-rates"
        )
    ).json()
    assert len(alice_rates) == 1
    assert alice_rates[0]["displayed_rate"] == "0.00002"

    await login(client, "bob")
    bob_rate = await client.put(
        f"/api/v1/workspaces/{bob_workspace_id}/valuation-rates/BTC",
        json={"displayed_rate": "0.00004"},
    )
    assert bob_rate.status_code == 200, bob_rate.text
    bob_summary = (await client.get("/api/v1/accounts/summary")).json()
    assert account_named(bob_summary, "Shared BTC")["valued_balance"] == "25000.00"

    await login(client, "alice")
    alice_summary = (await client.get("/api/v1/accounts/summary")).json()
    assert account_named(alice_summary, "Shared BTC")["valued_balance"] == "50000.00"


async def test_conflicting_direct_rates_latest_fallback_and_no_multihop(client):
    await register(client)
    alice_usd = await create_account(client, "Alice USD", "USD", "10")
    alice_vnd = await create_account(client, "Alice rate VND", "VND", "0")
    held_vnd = await create_account(client, "Alice held VND", "VND", "260000")
    first = await client.post(
        "/api/v1/transactions/exchange",
        json={
            "from_account_id": alice_usd["id"],
            "from_amount": "1",
            "to_account_id": alice_vnd["id"],
            "to_amount": "25000",
        },
    )
    assert first.status_code == 201, first.text
    second = await client.post(
        "/api/v1/transactions/exchange",
        json={
            "from_account_id": alice_usd["id"],
            "from_amount": "1",
            "to_account_id": alice_vnd["id"],
            "to_amount": "26000",
        },
    )
    assert second.status_code == 201, second.text
    summary = (await client.get("/api/v1/accounts/summary")).json()
    assert account_named(summary, "Alice held VND")["valued_balance"] == "10.00"
    assert (
        await client.post(f"/api/v1/transactions/{second.json()['id']}/void")
    ).status_code == 200
    summary = (await client.get("/api/v1/accounts/summary")).json()
    assert account_named(summary, "Alice held VND")["valued_balance"] == "10.40"

    alice_eur = await create_account(client, "Alice EUR", "EUR", "100")
    alice_btc = await create_account(client, "Alice BTC", "BTC", "1")
    btc_eur = await client.post(
        "/api/v1/transactions/exchange",
        json={
            "from_account_id": alice_btc["id"],
            "from_amount": "0.1",
            "to_account_id": alice_eur["id"],
            "to_amount": "3000",
        },
    )
    assert btc_eur.status_code == 201, btc_eur.text
    eur_usd = await client.post(
        "/api/v1/transactions/exchange",
        json={
            "from_account_id": alice_eur["id"],
            "from_amount": "1",
            "to_account_id": alice_usd["id"],
            "to_amount": "1.2",
        },
    )
    assert eur_usd.status_code == 201, eur_usd.text
    summary = (await client.get("/api/v1/accounts/summary")).json()
    assert account_named(summary, "Alice BTC")["valued_balance"] is None
    assert "BTC" in {item["asset"]["code"] for item in summary["unvalued"]}

    await client.post("/api/v1/auth/logout")
    await register(client, "bob")
    bob_usd = await create_account(client, "Bob USD", "USD", "10")
    bob_vnd = await create_account(client, "Bob rate VND", "VND", "0")
    await create_account(client, "Bob held VND", "VND", "260000")
    bob_exchange = await client.post(
        "/api/v1/transactions/exchange",
        json={
            "from_account_id": bob_usd["id"],
            "from_amount": "1",
            "to_account_id": bob_vnd["id"],
            "to_amount": "30000",
        },
    )
    assert bob_exchange.status_code == 201, bob_exchange.text
    bob_summary = (await client.get("/api/v1/accounts/summary")).json()
    assert account_named(bob_summary, "Bob held VND")["valued_balance"] == "8.67"

    await login(client, "alice")
    alice_summary = (await client.get("/api/v1/accounts/summary")).json()
    assert account_named(alice_summary, "Alice held VND")["valued_balance"] == "10.40"


async def test_shared_account_never_discloses_owner_exchange_rate(client):
    await register(client)
    usd = await create_account(client, "Owner USD", "USD", "10")
    shared = await create_account(client, "Shared exchange BTC", "BTC", "1")
    exchange = await client.post(
        "/api/v1/transactions/exchange",
        json={
            "from_account_id": usd["id"],
            "from_amount": "1",
            "to_account_id": shared["id"],
            "to_amount": "0.00002",
        },
    )
    assert exchange.status_code == 201, exchange.text
    owner_summary = (await client.get("/api/v1/accounts/summary")).json()
    assert account_named(
        owner_summary, "Shared exchange BTC"
    )["valued_balance"] == "50001.00"
    token = await invitation(client, shared["id"], "viewer")

    await register(client, "bob")
    await accept(client, token)
    shared_summary = (await client.get("/api/v1/accounts/summary")).json()
    assert account_named(
        shared_summary, "Shared exchange BTC"
    )["valued_balance"] is None
    assert (await client.get("/api/v1/exchange-rates")).json() == []
