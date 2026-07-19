from datetime import date, timedelta
from decimal import Decimal

from tests.conftest import register
from tests.test_ledger_v2 import create_account


async def create_rule(client, workspace_id: int, **overrides):
    body = {
        "kind": "required_expense",
        "name": "Rent",
        "amount": "500",
        "asset_code": "USD",
        "recurrence": "once",
        "first_due_date": date.today().isoformat(),
        "is_required": True,
        **overrides,
    }
    return await client.post(
        f"/api/v1/workspaces/{workspace_id}/plan-rules", json=body
    )


async def occurrences_for_rule(client, workspace_id: int, rule_id: int):
    response = await client.get(
        f"/api/v1/workspaces/{workspace_id}/plan-occurrences"
    )
    assert response.status_code == 200, response.text
    return [item for item in response.json() if item["plan_rule_id"] == rule_id]


async def test_occurrences_materialize_idempotently_and_open_schedule_rebuilds(client):
    context = await register(client)
    workspace_id = context["workspace"]["id"]
    first = date.today()
    created = await create_rule(
        client,
        workspace_id,
        name="Weekly groceries",
        amount="100",
        recurrence="weekly",
        first_due_date=first.isoformat(),
    )
    assert created.status_code == 201, created.text
    rule = created.json()
    first_read = await occurrences_for_rule(client, workspace_id, rule["id"])
    second_read = await occurrences_for_rule(client, workspace_id, rule["id"])
    assert len(first_read) == 53
    assert [item["id"] for item in second_read] == [item["id"] for item in first_read]
    assert [item["due_date"] for item in first_read[:3]] == [
        first.isoformat(),
        (first + timedelta(days=7)).isoformat(),
        (first + timedelta(days=14)).isoformat(),
    ]

    patched = await client.patch(
        f"/api/v1/workspaces/{workspace_id}/plan-rules/{rule['id']}",
        json={"recurrence": "monthly", "amount": "125"},
    )
    assert patched.status_code == 200, patched.text
    after = await occurrences_for_rule(client, workspace_id, rule["id"])
    assert len(after) == 13
    assert all(Decimal(item["planned_amount"]) == Decimal("125") for item in after)
    assert len({item["due_date"] for item in after}) == len(after)

    archived = await client.post(
        f"/api/v1/workspaces/{workspace_id}/plan-rules/{rule['id']}/archive"
    )
    assert archived.status_code == 200, archived.text
    assert archived.json()["is_active"] is False
    assert {item["status"] for item in await occurrences_for_rule(
        client, workspace_id, rule["id"]
    )} == {"skipped"}


async def test_resolved_occurrences_survive_rule_edit_and_archive(client):
    context = await register(client)
    workspace_id = context["workspace"]["id"]
    account = await create_account(client, "Plan USD", "USD", "1000")
    rule = (
        await create_rule(
            client,
            workspace_id,
            name="Weekly essentials",
            amount="100",
            recurrence="weekly",
            default_from_account_id=account["id"],
        )
    ).json()
    original = await occurrences_for_rule(client, workspace_id, rule["id"])
    completed, skipped = original[:2]
    expense = (
        await client.post(
            "/api/v1/operations/spend",
            json={"account_id": account["id"], "amount": "90"},
        )
    ).json()
    linked = await client.post(
        f"/api/v1/workspaces/{workspace_id}/plan-occurrences/"
        f"{completed['id']}/link-transaction",
        json={"transaction_id": expense["id"]},
    )
    assert linked.status_code == 200, linked.text
    skipped_response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/plan-occurrences/{skipped['id']}/skip"
    )
    assert skipped_response.status_code == 200, skipped_response.text

    patched = await client.patch(
        f"/api/v1/workspaces/{workspace_id}/plan-rules/{rule['id']}",
        json={
            "recurrence": "monthly",
            "first_due_date": (date.today() + timedelta(days=2)).isoformat(),
            "amount": "125",
        },
    )
    assert patched.status_code == 200, patched.text
    after = {
        item["id"]: item
        for item in await occurrences_for_rule(client, workspace_id, rule["id"])
    }
    assert after[completed["id"]]["status"] == "completed"
    assert after[completed["id"]]["planned_amount"] == completed["planned_amount"]
    assert after[skipped["id"]]["status"] == "skipped"
    assert after[skipped["id"]]["planned_amount"] == skipped["planned_amount"]

    archived = await client.post(
        f"/api/v1/workspaces/{workspace_id}/plan-rules/{rule['id']}/archive"
    )
    assert archived.status_code == 200, archived.text
    final = {
        item["id"]: item
        for item in await occurrences_for_rule(client, workspace_id, rule["id"])
    }
    assert final[completed["id"]]["status"] == "completed"
    assert final[skipped["id"]]["status"] == "skipped"
    assert all(
        item["status"] == "skipped"
        for item_id, item in final.items()
        if item_id not in {completed["id"], skipped["id"]}
    )


async def test_plan_is_link_and_skip_only_and_void_reopens_link(client):
    context = await register(client)
    workspace_id = context["workspace"]["id"]
    account = await create_account(client, "Main USD", "USD", "1000")
    linked_rule = (
        await create_rule(
            client,
            workspace_id,
            name="Linked bill",
            amount="20",
            default_from_account_id=account["id"],
        )
    ).json()
    linked_occurrence = (await occurrences_for_rule(
        client, workspace_id, linked_rule["id"]
    ))[0]
    transaction = (
        await client.post(
            "/api/v1/operations/spend",
            json={"account_id": account["id"], "amount": "22", "note": "Paid"},
        )
    ).json()
    linked = await client.post(
        f"/api/v1/workspaces/{workspace_id}/plan-occurrences/"
        f"{linked_occurrence['id']}/link-transaction",
        json={"transaction_id": transaction["id"]},
    )
    assert linked.status_code == 200, linked.text
    assert linked.json()["status"] == "completed"
    assert Decimal(linked.json()["actual_amount"]) == Decimal("22")

    base = (
        f"/api/v1/workspaces/{workspace_id}/plan-occurrences/"
        f"{linked_occurrence['id']}"
    )
    assert (await client.post(f"{base}/pay", json={})).status_code in {404, 405}
    assert (await client.post(f"{base}/receive", json={})).status_code in {404, 405}

    voided = await client.post(f"/api/v1/transactions/{transaction['id']}/delete")
    assert voided.status_code == 200, voided.text
    reopened = (await occurrences_for_rule(
        client, workspace_id, linked_rule["id"]
    ))[0]
    assert reopened["status"] == "planned"
    assert reopened["transaction_id"] is None

    skipped_rule = (
        await create_rule(client, workspace_id, name="Optional", is_required=False)
    ).json()
    skipped_occurrence = (await occurrences_for_rule(
        client, workspace_id, skipped_rule["id"]
    ))[0]
    skipped = await client.post(
        f"/api/v1/workspaces/{workspace_id}/plan-occurrences/"
        f"{skipped_occurrence['id']}/skip"
    )
    assert skipped.status_code == 200, skipped.text
    assert skipped.json()["status"] == "skipped"


async def test_link_validates_semantic_type_and_allows_asset_account_differences(client):
    context = await register(client)
    workspace_id = context["workspace"]["id"]
    usd = await create_account(client, "Main USD", "USD", "1000")
    vnd = await create_account(client, "Cash VND", "VND", "5000000")
    vnd_reserve = await create_account(client, "Reserve VND", "VND", "0")

    expense_rule = (
        await create_rule(
            client,
            workspace_id,
            name="Rent USD",
            amount="500",
            default_from_account_id=usd["id"],
        )
    ).json()
    expense_occurrence = (await occurrences_for_rule(
        client, workspace_id, expense_rule["id"]
    ))[0]
    vnd_spend = (
        await client.post(
            "/api/v1/operations/spend",
            json={"account_id": vnd["id"], "amount": "1200000"},
        )
    ).json()
    linked = await client.post(
        f"/api/v1/workspaces/{workspace_id}/plan-occurrences/"
        f"{expense_occurrence['id']}/link-transaction",
        json={"transaction_id": vnd_spend["id"]},
    )
    assert linked.status_code == 200, linked.text
    body = linked.json()
    assert body["status"] == "completed"
    assert Decimal(body["actual_amount"]) == Decimal("1200000")
    assert body["actual_asset"]["code"] == "VND"
    assert body["rule"]["asset"]["code"] == "USD"

    transfer_rule = (
        await create_rule(
            client,
            workspace_id,
            kind="reserve_transfer",
            name="Reserve USD",
            amount="100",
            category_id=None,
        )
    ).json()
    transfer_occurrence = (await occurrences_for_rule(
        client, workspace_id, transfer_rule["id"]
    ))[0]
    vnd_transfer = (
        await client.post(
            "/api/v1/operations/transfer",
            json={
                "from_account_id": vnd["id"],
                "to_account_id": vnd_reserve["id"],
                "amount": "700000",
            },
        )
    ).json()
    linked_transfer = await client.post(
        f"/api/v1/workspaces/{workspace_id}/plan-occurrences/"
        f"{transfer_occurrence['id']}/link-transaction",
        json={"transaction_id": vnd_transfer["id"]},
    )
    assert linked_transfer.status_code == 200, linked_transfer.text
    assert Decimal(linked_transfer.json()["actual_amount"]) == Decimal("700000")
    assert linked_transfer.json()["actual_asset"]["code"] == "VND"

    income_rule = (
        await create_rule(
            client,
            workspace_id,
            kind="income",
            name="Salary",
            amount="900",
            category_id=None,
        )
    ).json()
    income_occurrence = (await occurrences_for_rule(
        client, workspace_id, income_rule["id"]
    ))[0]
    income_link_route = (
        f"/api/v1/workspaces/{workspace_id}/plan-occurrences/"
        f"{income_occurrence['id']}/link-transaction"
    )
    another_spend = (
        await client.post(
            "/api/v1/operations/spend",
            json={"account_id": usd["id"], "amount": "10"},
        )
    ).json()
    wrong_type = await client.post(
        income_link_route, json={"transaction_id": another_spend["id"]}
    )
    assert wrong_type.status_code == 422
    assert "type" in wrong_type.json()["detail"].lower()

    exchange = (
        await client.post(
            "/api/v1/operations/exchange",
            json={
                "from_account_id": vnd["id"],
                "from_amount": "260000",
                "to_account_id": usd["id"],
                "to_amount": "10",
            },
        )
    ).json()
    open_transfer_rule = (
        await create_rule(
            client,
            workspace_id,
            kind="reserve_transfer",
            name="Reserve again",
            amount="50",
            category_id=None,
        )
    ).json()
    open_transfer_occurrence = (await occurrences_for_rule(
        client, workspace_id, open_transfer_rule["id"]
    ))[0]
    exchange_to_transfer_rule = await client.post(
        f"/api/v1/workspaces/{workspace_id}/plan-occurrences/"
        f"{open_transfer_occurrence['id']}/link-transaction",
        json={"transaction_id": exchange["id"]},
    )
    assert exchange_to_transfer_rule.status_code == 422
    assert "type" in exchange_to_transfer_rule.json()["detail"].lower()

    income = (
        await client.post(
            "/api/v1/operations/add-funds",
            json={"account_id": usd["id"], "amount": "900"},
        )
    ).json()
    deleted = await client.post(f"/api/v1/transactions/{income['id']}/delete")
    assert deleted.status_code == 200
    non_posted = await client.post(
        income_link_route, json={"transaction_id": income["id"]}
    )
    assert non_posted.status_code == 422

    relink = await client.post(
        f"/api/v1/workspaces/{workspace_id}/plan-occurrences/"
        f"{expense_occurrence['id']}/link-transaction",
        json={"transaction_id": vnd_spend["id"]},
    )
    assert relink.status_code == 409

    fresh_income = (
        await client.post(
            "/api/v1/operations/add-funds",
            json={"account_id": usd["id"], "amount": "901"},
        )
    ).json()
    wrong_type_linked = await client.post(
        income_link_route, json={"transaction_id": vnd_spend["id"]}
    )
    assert wrong_type_linked.status_code == 422

    second_expense_rule = (
        await create_rule(
            client, workspace_id, name="Second bill", amount="30"
        )
    ).json()
    second_expense_occurrence = (await occurrences_for_rule(
        client, workspace_id, second_expense_rule["id"]
    ))[0]
    already_linked = await client.post(
        f"/api/v1/workspaces/{workspace_id}/plan-occurrences/"
        f"{second_expense_occurrence['id']}/link-transaction",
        json={"transaction_id": vnd_spend["id"]},
    )
    assert already_linked.status_code == 409
    assert "already linked" in already_linked.json()["detail"]

    linked_income = await client.post(
        income_link_route, json={"transaction_id": fresh_income["id"]}
    )
    assert linked_income.status_code == 200, linked_income.text
    assert linked_income.json()["actual_asset"]["code"] == "USD"


async def test_link_hides_foreign_transactions(client):
    alice = await register(client)
    alice_workspace = alice["workspace"]["id"]
    alice_account = await create_account(client, "Alice USD", "USD", "100")
    alice_spend = (
        await client.post(
            "/api/v1/operations/spend",
            json={"account_id": alice_account["id"], "amount": "5"},
        )
    ).json()

    await client.post("/api/v1/auth/logout")
    bob = await register(client, "bob")
    bob_workspace = bob["workspace"]["id"]
    await create_account(client, "Bob USD", "USD", "100")
    bob_rule = (
        await create_rule(client, bob_workspace, name="Bob bill", amount="5")
    ).json()
    bob_occurrence = (await occurrences_for_rule(
        client, bob_workspace, bob_rule["id"]
    ))[0]

    foreign = await client.post(
        f"/api/v1/workspaces/{bob_workspace}/plan-occurrences/"
        f"{bob_occurrence['id']}/link-transaction",
        json={"transaction_id": alice_spend["id"]},
    )
    assert foreign.status_code == 404
    missing = await client.post(
        f"/api/v1/workspaces/{bob_workspace}/plan-occurrences/"
        f"{bob_occurrence['id']}/link-transaction",
        json={"transaction_id": alice_spend["id"] + 100000},
    )
    assert missing.status_code == 404
    assert foreign.json()["detail"] == missing.json()["detail"]

    reverse_foreign = await client.post(
        f"/api/v1/transactions/{alice_spend['id']}/link-plan",
        json={"occurrence_id": bob_occurrence["id"]},
    )
    reverse_missing = await client.post(
        f"/api/v1/transactions/{alice_spend['id'] + 100000}/link-plan",
        json={"occurrence_id": bob_occurrence["id"]},
    )
    assert reverse_foreign.status_code == 404
    assert reverse_missing.status_code == 404
    assert reverse_foreign.json()["detail"] == reverse_missing.json()["detail"]

    reverse_foreign_occurrence = await client.post(
        f"/api/v1/transactions/{alice_spend['id']}/link-plan",
        json={"occurrence_id": bob_occurrence["id"] + 100000},
    )
    assert reverse_foreign_occurrence.status_code == 404
    assert (
        reverse_foreign_occurrence.json()["detail"]
        == "Plan occurrence not found"
    )

    resolved = await client.post(
        f"/api/v1/workspaces/{bob_workspace}/plan-occurrences/"
        f"{bob_occurrence['id']}/skip"
    )
    assert resolved.status_code == 200
    resolved_foreign = await client.post(
        f"/api/v1/workspaces/{bob_workspace}/plan-occurrences/"
        f"{bob_occurrence['id']}/link-transaction",
        json={"transaction_id": alice_spend["id"]},
    )
    resolved_missing = await client.post(
        f"/api/v1/workspaces/{bob_workspace}/plan-occurrences/"
        f"{bob_occurrence['id']}/link-transaction",
        json={"transaction_id": alice_spend["id"] + 100000},
    )
    assert resolved_foreign.status_code == 404
    assert resolved_missing.status_code == 404
    assert resolved_foreign.json()["detail"] == resolved_missing.json()["detail"]


async def test_plan_validation_and_permissions(client):
    alice = await register(client)
    workspace_id = alice["workspace"]["id"]
    usd = await create_account(client, "Main USD", "USD", "0")
    vnd = await create_account(client, "Main VND", "VND", "0")
    category_route = f"/api/v1/workspaces/{workspace_id}/categories"
    expense_category = (
        await client.post(category_route, json={"name": "Rent", "kind": "expense"})
    ).json()

    wrong_asset = await create_rule(
        client, workspace_id, default_from_account_id=vnd["id"]
    )
    assert wrong_asset.status_code == 422
    wrong_category = await create_rule(
        client,
        workspace_id,
        kind="income",
        category_id=expense_category["id"],
        default_to_account_id=usd["id"],
    )
    assert wrong_category.status_code == 422
    same_transfer = await create_rule(
        client,
        workspace_id,
        kind="reserve_transfer",
        default_from_account_id=usd["id"],
        default_to_account_id=usd["id"],
    )
    assert same_transfer.status_code == 422

    await client.post("/api/v1/auth/logout")
    await register(client, "bob")
    assert (
        await client.get(f"/api/v1/workspaces/{workspace_id}/plan-rules")
    ).status_code == 404
    assert (
        await client.get(f"/api/v1/workspaces/{workspace_id}/plan-occurrences")
    ).status_code == 404
