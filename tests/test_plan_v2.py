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
