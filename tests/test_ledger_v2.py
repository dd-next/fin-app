from decimal import Decimal

from tests.conftest import register


async def create_account(
    client,
    name: str,
    asset: str,
    opening: str = "0",
    *,
    purpose: str = "spending",
    available: bool = True,
):
    response = await client.post(
        "/api/v1/accounts",
        json={
            "name": name,
            "storage_type": "cash" if "Cash" in name else "bank",
            "purpose": purpose,
            "asset_code": asset,
            "opening_balance": opening,
            "include_in_available": available,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_account_opening_balance_precision_and_reconcile(client):
    await register(client)
    usd = await create_account(client, "Main USD", "USD", "100.25")
    assert Decimal(usd["balance"]) == Decimal("100.25")
    bad = await client.post(
        "/api/v1/accounts",
        json={
            "name": "Bad VND",
            "storage_type": "cash",
            "purpose": "spending",
            "asset_code": "VND",
            "opening_balance": "1.5",
        },
    )
    assert bad.status_code == 422
    reconciled = await client.post(
        f"/api/v1/accounts/{usd['id']}/reconcile",
        json={"target_balance": "110.25", "note": "Counted cash"},
    )
    assert reconciled.status_code == 200
    assert Decimal((await client.get(f"/api/v1/accounts/{usd['id']}")).json()["balance"]) == Decimal("110.25")


async def test_net_worth_available_and_archive(client):
    await register(client)
    await create_account(client, "Main USD", "USD", "1000")
    reserve = await create_account(
        client, "Emergency USD", "USD", "300", purpose="reserve", available=False
    )
    summary = (await client.get("/api/v1/accounts/summary")).json()
    assert Decimal(summary["net_worth"]) == Decimal("1300")
    assert Decimal(summary["available"]) == Decimal("1000")
    assert (await client.post(f"/api/v1/accounts/{reserve['id']}/archive")).status_code == 200
    summary = (await client.get("/api/v1/accounts/summary")).json()
    assert Decimal(summary["net_worth"]) == Decimal("1000")


async def test_expense_income_and_category_rules(client):
    context = await register(client)
    account = await create_account(client, "Main USD", "USD", "1000")
    route = f"/api/v1/workspaces/{context['workspace']['id']}/categories"
    expense_category = (
        await client.post(route, json={"name": "Food", "kind": "expense"})
    ).json()
    expense = await client.post(
        "/api/v1/transactions/expense",
        json={"account_id": account["id"], "amount": "25.50", "category_id": expense_category["id"]},
    )
    assert expense.status_code == 201
    assert Decimal(expense.json()["legs"][0]["amount"]) == Decimal("-25.50")
    income = await client.post(
        "/api/v1/transactions/income",
        json={"account_id": account["id"], "amount": "100"},
    )
    assert income.status_code == 201
    assert Decimal((await client.get(f"/api/v1/accounts/{account['id']}")).json()["balance"]) == Decimal("1074.50")
    wrong_category = await client.post(
        "/api/v1/transactions/income",
        json={"account_id": account["id"], "amount": "1", "category_id": expense_category["id"]},
    )
    assert wrong_category.status_code == 422


async def test_transfer_is_neutral_and_requires_same_asset(client):
    await register(client)
    bank = await create_account(client, "Bank USD", "USD", "500")
    cash = await create_account(client, "Cash USD", "USD", "0")
    vnd = await create_account(client, "Cash VND", "VND", "0")
    transfer = await client.post(
        "/api/v1/transactions/transfer",
        json={"from_account_id": bank["id"], "to_account_id": cash["id"], "amount": "120"},
    )
    assert transfer.status_code == 201
    balances = {item["name"]: Decimal(item["balance"]) for item in (await client.get("/api/v1/accounts")).json()}
    assert balances["Bank USD"] == Decimal("380")
    assert balances["Cash USD"] == Decimal("120")
    assert Decimal((await client.get("/api/v1/accounts/summary")).json()["net_worth"]) == Decimal("500")
    bad = await client.post(
        "/api/v1/transactions/transfer",
        json={"from_account_id": bank["id"], "to_account_id": vnd["id"], "amount": "1"},
    )
    assert bad.status_code == 422


async def test_exchange_derives_rate_values_accounts_and_fee_is_expense(client):
    await register(client)
    usd = await create_account(client, "Bank USD", "USD", "1000")
    vnd = await create_account(client, "Cash VND", "VND", "0")
    exchange = await client.post(
        "/api/v1/transactions/exchange",
        json={
            "from_account_id": usd["id"], "from_amount": "100",
            "to_account_id": vnd["id"], "to_amount": "2600000",
            "fee": {"account_id": usd["id"], "amount": "2"},
        },
    )
    assert exchange.status_code == 201, exchange.text
    rates = (await client.get("/api/v1/exchange-rates")).json()
    assert len(rates) == 2
    assert any(item["base_asset"]["code"] == "VND" and Decimal(item["rate"]) == Decimal("1") / Decimal("26000") for item in rates)
    summary = (await client.get("/api/v1/accounts/summary")).json()
    assert Decimal(summary["net_worth"]) == Decimal("998")
    assert summary["unvalued"] == []
    assert (await client.post(f"/api/v1/transactions/{exchange.json()['id']}/void")).status_code == 200
    summary = (await client.get("/api/v1/accounts/summary")).json()
    # The child fee is voided atomically with the exchange.
    assert Decimal(summary["net_worth"]) == Decimal("1000")
    assert (await client.get("/api/v1/exchange-rates")).json() == []


async def test_unassigned_operation_does_not_touch_balance_then_assigns(client):
    await register(client)
    account = await create_account(client, "Cash USD", "USD", "100")
    expense = await client.post(
        "/api/v1/transactions/expense",
        json={"asset_code": "USD", "amount": "10", "note": "Wallet unknown"},
    )
    assert expense.status_code == 201
    assert expense.json()["status"] == "unassigned"
    assert Decimal((await client.get(f"/api/v1/accounts/{account['id']}")).json()["balance"]) == Decimal("100")
    assigned = await client.post(
        f"/api/v1/transactions/{expense.json()['id']}/assign-account",
        json={"account_id": account["id"]},
    )
    assert assigned.status_code == 200
    assert assigned.json()["status"] == "posted"
    assert Decimal((await client.get(f"/api/v1/accounts/{account['id']}")).json()["balance"]) == Decimal("90")


async def test_patch_void_filters_and_pagination(client):
    await register(client)
    account = await create_account(client, "Cash USD", "USD", "100")
    ids = []
    for amount in ("5", "6", "7"):
        response = await client.post(
            "/api/v1/transactions/expense",
            json={"account_id": account["id"], "amount": amount},
        )
        ids.append(response.json()["id"])
    page = (await client.get("/api/v1/transactions?type=expense&limit=2")).json()
    assert [item["id"] for item in page["items"]] == [ids[2], ids[1]]
    assert page["next_cursor"] == ids[1]
    second = (await client.get(f"/api/v1/transactions?type=expense&cursor={page['next_cursor']}&limit=2")).json()
    assert [item["id"] for item in second["items"]] == [ids[0]]
    patched = await client.patch(
        f"/api/v1/transactions/{ids[0]}", json={"amount": "15", "note": "Corrected"}
    )
    assert patched.status_code == 200, patched.text
    assert Decimal((await client.get(f"/api/v1/accounts/{account['id']}")).json()["balance"]) == Decimal("72")
    assert (await client.post(f"/api/v1/transactions/{ids[1]}/void")).status_code == 200
    assert Decimal((await client.get(f"/api/v1/accounts/{account['id']}")).json()["balance"]) == Decimal("78")


async def test_other_user_cannot_see_accounts_or_transactions(client):
    await register(client)
    account = await create_account(client, "Private USD", "USD", "100")
    transaction = (
        await client.post(
            "/api/v1/transactions/expense",
            json={"account_id": account["id"], "amount": "1"},
        )
    ).json()
    await client.post("/api/v1/auth/logout")
    await register(client, "bob")
    assert (await client.get(f"/api/v1/accounts/{account['id']}")).status_code == 404
    assert (await client.get(f"/api/v1/transactions/{transaction['id']}")).status_code == 404
