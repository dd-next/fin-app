from datetime import date

from tests.conftest import register


async def test_archived_category_is_preserved_only_as_an_existing_transaction_value(client):
    context = await register(client)
    workspace_id = context["workspace"]["id"]
    category_route = f"/api/v1/workspaces/{workspace_id}/categories"
    account = await client.post(
        "/api/v1/accounts",
        json={
            "name": "Main USD",
            "storage_type": "bank",
            "purpose": "spending",
            "asset_code": "USD",
            "opening_balance": "100",
            "include_in_available": True,
        },
    )
    assert account.status_code == 201, account.text
    historical = await client.post(
        category_route, json={"name": "Old food", "kind": "expense"}
    )
    other = await client.post(
        category_route, json={"name": "Old travel", "kind": "expense"}
    )
    assert historical.status_code == other.status_code == 201

    transaction = await client.post(
        "/api/v1/operations/spend",
        json={
            "account_id": account.json()["id"],
            "amount": "10",
            "category_id": historical.json()["id"],
        },
    )
    assert transaction.status_code == 201, transaction.text
    for category in (historical.json(), other.json()):
        archived = await client.post(
            f"{category_route}/{category['id']}/archive"
        )
        assert archived.status_code == 200, archived.text

    kept = await client.patch(
        f"/api/v1/transactions/{transaction.json()['id']}",
        json={"category_id": historical.json()["id"], "note": "Receipt kept"},
    )
    assert kept.status_code == 200, kept.text
    assert kept.json()["category_id"] == historical.json()["id"]

    reassigned = await client.patch(
        f"/api/v1/transactions/{transaction.json()['id']}",
        json={"category_id": other.json()["id"]},
    )
    assert reassigned.status_code == 422
    assert reassigned.json()["detail"] == "Invalid category"

    created_with_archived = await client.post(
        "/api/v1/operations/spend",
        json={
            "account_id": account.json()["id"],
            "amount": "1",
            "category_id": historical.json()["id"],
        },
    )
    assert created_with_archived.status_code == 422


async def test_archived_category_is_preserved_only_on_its_existing_plan_rule(client):
    context = await register(client)
    workspace_id = context["workspace"]["id"]
    category_route = f"/api/v1/workspaces/{workspace_id}/categories"
    historical = await client.post(
        category_route, json={"name": "Old rent", "kind": "expense"}
    )
    replacement = await client.post(
        category_route, json={"name": "Current rent", "kind": "expense"}
    )
    assert historical.status_code == replacement.status_code == 201

    rules_route = f"/api/v1/workspaces/{workspace_id}/plan-rules"
    rule_body = {
        "kind": "required_expense",
        "name": "Rent",
        "amount": "500",
        "asset_code": "USD",
        "recurrence": "monthly",
        "first_due_date": date.today().isoformat(),
        "category_id": historical.json()["id"],
        "is_required": True,
    }
    historical_rule = await client.post(rules_route, json=rule_body)
    replacement_rule = await client.post(
        rules_route,
        json={
            **rule_body,
            "name": "Utilities",
            "category_id": replacement.json()["id"],
        },
    )
    assert historical_rule.status_code == replacement_rule.status_code == 201
    archived = await client.post(
        f"{category_route}/{historical.json()['id']}/archive"
    )
    assert archived.status_code == 200, archived.text

    kept = await client.patch(
        f"{rules_route}/{historical_rule.json()['id']}",
        json={
            "name": "Rent updated",
            "category_id": historical.json()["id"],
        },
    )
    assert kept.status_code == 200, kept.text
    assert kept.json()["category_id"] == historical.json()["id"]

    reassigned = await client.patch(
        f"{rules_route}/{replacement_rule.json()['id']}",
        json={"category_id": historical.json()["id"]},
    )
    assert reassigned.status_code == 422
    assert reassigned.json()["detail"] == "Invalid category"

    created_with_archived = await client.post(
        rules_route,
        json={**rule_body, "name": "New archived category rule"},
    )
    assert created_with_archived.status_code == 422
