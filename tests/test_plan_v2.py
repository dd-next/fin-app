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
    response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/plan-rules", json=body
    )
    return response


async def test_occurrences_materialize_idempotently_and_rule_edits_replace_open_schedule(client):
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
    route = f"/api/v1/workspaces/{workspace_id}/plan-occurrences"
    first_read = (await client.get(route)).json()
    second_read = (await client.get(route)).json()
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
    after = (await client.get(route)).json()
    assert len(after) == 13
    assert all(Decimal(item["planned_amount"]) == Decimal("125") for item in after)
    assert len({item["due_date"] for item in after}) == len(after)

    archived = await client.post(
        f"/api/v1/workspaces/{workspace_id}/plan-rules/{rule['id']}/archive"
    )
    assert archived.status_code == 200
    assert archived.json()["is_active"] is False
    archived_occurrences = (await client.get(route)).json()
    assert len(archived_occurrences) == 13
    assert {item["status"] for item in archived_occurrences} == {"skipped"}


async def test_receive_pay_transfer_skip_link_and_void_reopens_plan(client):
    context = await register(client)
    workspace_id = context["workspace"]["id"]
    main = await create_account(client, "Main USD", "USD", "1000")
    reserve = await create_account(client, "Reserve USD", "USD", "0", purpose="reserve", available=False)
    category_route = f"/api/v1/workspaces/{workspace_id}/categories"
    salary_category = (
        await client.post(category_route, json={"name": "Salary", "kind": "income"})
    ).json()
    bills_category = (
        await client.post(category_route, json={"name": "Bills", "kind": "expense"})
    ).json()

    income_rule = (
        await create_rule(
            client,
            workspace_id,
            kind="income",
            name="Salary",
            amount="500",
            category_id=salary_category["id"],
            default_to_account_id=main["id"],
            is_required=False,
        )
    ).json()
    occurrences_route = f"/api/v1/workspaces/{workspace_id}/plan-occurrences"
    occurrences = (await client.get(occurrences_route)).json()
    income_occurrence = next(item for item in occurrences if item["plan_rule_id"] == income_rule["id"])
    received = await client.post(
        f"{occurrences_route}/{income_occurrence['id']}/receive", json={}
    )
    assert received.status_code == 200, received.text
    assert received.json()["status"] == "completed"
    assert Decimal(received.json()["actual_amount"]) == Decimal("500")
    income_transaction_id = received.json()["transaction_id"]
    transaction = (await client.get(f"/api/v1/transactions/{income_transaction_id}")).json()
    assert transaction["source"] == "planned"
    assert transaction["plan_occurrence_id"] == income_occurrence["id"]
    assert (
        await client.post(f"{occurrences_route}/{income_occurrence['id']}/receive", json={})
    ).status_code == 409

    expense_rule = (
        await create_rule(
            client,
            workspace_id,
            kind="subscription",
            name="Internet",
            amount="50",
            category_id=bills_category["id"],
            default_from_account_id=main["id"],
        )
    ).json()
    expense_occurrence = next(
        item for item in (await client.get(occurrences_route)).json()
        if item["plan_rule_id"] == expense_rule["id"]
    )
    paid = await client.post(
        f"{occurrences_route}/{expense_occurrence['id']}/pay",
        json={"amount": "60", "note": "Actual invoice"},
    )
    assert paid.status_code == 200, paid.text
    assert Decimal(paid.json()["actual_amount"]) == Decimal("60")

    transfer_rule = (
        await create_rule(
            client,
            workspace_id,
            kind="reserve_transfer",
            name="Emergency fund",
            amount="100",
            default_from_account_id=main["id"],
            default_to_account_id=reserve["id"],
            is_required=False,
        )
    ).json()
    transfer_occurrence = next(
        item for item in (await client.get(occurrences_route)).json()
        if item["plan_rule_id"] == transfer_rule["id"]
    )
    moved = await client.post(f"{occurrences_route}/{transfer_occurrence['id']}/pay", json={})
    assert moved.status_code == 200, moved.text

    skipped_rule = (await create_rule(client, workspace_id, name="Optional", is_required=False)).json()
    skipped_occurrence = next(
        item for item in (await client.get(occurrences_route)).json()
        if item["plan_rule_id"] == skipped_rule["id"]
    )
    skipped = await client.post(f"{occurrences_route}/{skipped_occurrence['id']}/skip")
    assert skipped.status_code == 200
    assert skipped.json()["status"] == "skipped"

    linked_rule = (await create_rule(client, workspace_id, name="Linked bill", amount="20")).json()
    linked_occurrence = next(
        item for item in (await client.get(occurrences_route)).json()
        if item["plan_rule_id"] == linked_rule["id"]
    )
    manual = (
        await client.post(
            "/api/v1/transactions/expense",
            json={"account_id": main["id"], "amount": "22", "note": "Already paid"},
        )
    ).json()
    linked = await client.post(
        f"{occurrences_route}/{linked_occurrence['id']}/link-transaction",
        json={"transaction_id": manual["id"]},
    )
    assert linked.status_code == 200, linked.text
    assert Decimal(linked.json()["actual_amount"]) == Decimal("22")
    assert (
        await client.post(
            f"/api/v1/transactions/{manual['id']}/link-plan",
            json={"occurrence_id": linked_occurrence["id"]},
        )
    ).status_code == 409
    assert (await client.post(f"/api/v1/transactions/{manual['id']}/void")).status_code == 200
    reopened = next(
        item for item in (await client.get(occurrences_route)).json()
        if item["id"] == linked_occurrence["id"]
    )
    assert reopened["status"] == "planned"
    assert reopened["transaction_id"] is None

    balances = {item["name"]: Decimal(item["balance"]) for item in (await client.get("/api/v1/accounts")).json()}
    assert balances["Main USD"] == Decimal("1340")
    assert balances["Reserve USD"] == Decimal("100")


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
