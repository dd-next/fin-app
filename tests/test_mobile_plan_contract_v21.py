from datetime import date

from tests.conftest import register
from tests.test_ledger_v2 import create_account


async def test_mobile_plan_create_edit_and_detail_adapter(client):
    context = await register(client)
    workspace_id = context["workspace"]["id"]
    account = await create_account(client, "Main USD", "USD")
    route = f"/api/v1/workspaces/{workspace_id}/plan-rules"

    created = await client.post(
        route,
        json={
            "kind": "expectedIncome",
            "name": "Salary",
            "amount": "1350",
            "asset_code": "USD",
            "recurrence": "monthly",
            "first_due_date": date.today().isoformat(),
            "account_id": account["id"],
            "is_required": False,
        },
    )
    assert created.status_code == 201, created.text
    rule = created.json()
    assert rule["kind"] == "income"
    assert rule["mobile_kind"] == "expectedIncome"
    assert rule["account_field"] == "to_account"
    assert rule["account_id"] == account["id"]
    assert rule["default_from_account_id"] is None
    assert rule["default_to_account_id"] == account["id"]
    assert rule["is_required"] is False

    detail_route = f"{route}/{rule['id']}"
    detail = await client.get(detail_route)
    assert detail.status_code == 200
    assert detail.json() == rule

    edited = await client.patch(
        detail_route,
        json={
            "kind": "requiredExpense",
            "account_id": account["id"],
            "is_required": True,
        },
    )
    assert edited.status_code == 200, edited.text
    body = edited.json()
    assert body["kind"] == "required_expense"
    assert body["mobile_kind"] == "requiredExpense"
    assert body["account_field"] == "from_account"
    assert body["account_id"] == account["id"]
    assert body["default_from_account_id"] == account["id"]
    assert body["default_to_account_id"] is None
    assert body["is_required"] is True


async def test_mobile_plan_adapter_validates_direction_asset_and_privacy(client):
    alice = await register(client)
    workspace_id = alice["workspace"]["id"]
    usd = await create_account(client, "Main USD", "USD")
    other_usd = await create_account(client, "Other USD", "USD")
    vnd = await create_account(client, "Main VND", "VND")
    route = f"/api/v1/workspaces/{workspace_id}/plan-rules"
    base = {
        "kind": "expectedIncome",
        "name": "Salary",
        "amount": "100",
        "asset_code": "USD",
        "first_due_date": date.today().isoformat(),
    }

    wrong_asset = await client.post(route, json={**base, "account_id": vnd["id"]})
    assert wrong_asset.status_code == 422
    assert wrong_asset.json()["detail"] == "Target account asset does not match rule"

    conflicting = await client.post(
        route,
        json={
            **base,
            "account_id": usd["id"],
            "default_to_account_id": other_usd["id"],
        },
    )
    assert conflicting.status_code == 422
    assert conflicting.json()["detail"] == (
        "account_id conflicts with default_to_account_id"
    )

    created = await client.post(route, json={**base, "account_id": usd["id"]})
    assert created.status_code == 201

    await client.post("/api/v1/auth/logout")
    await register(client, "bob")
    hidden = await client.get(f"{route}/{created.json()['id']}")
    assert hidden.status_code == 404
    assert hidden.json()["detail"] == "Workspace not found"


async def test_mobile_reserve_transfer_account_is_source_and_keeps_destination(client):
    context = await register(client)
    workspace_id = context["workspace"]["id"]
    source = await create_account(client, "Source USD", "USD")
    replacement_source = await create_account(client, "Second USD", "USD")
    destination = await create_account(client, "Reserve USD", "USD")
    route = f"/api/v1/workspaces/{workspace_id}/plan-rules"

    created = await client.post(
        route,
        json={
            "kind": "reserveTransfer",
            "name": "Build reserve",
            "amount": "50",
            "asset_code": "USD",
            "first_due_date": date.today().isoformat(),
            "account_id": source["id"],
            "default_to_account_id": destination["id"],
        },
    )
    assert created.status_code == 201, created.text
    rule = created.json()
    assert rule["mobile_kind"] == "reserveTransfer"
    assert rule["account_field"] == "from_account"
    assert rule["account_id"] == source["id"]
    assert rule["default_to_account_id"] == destination["id"]

    patched = await client.patch(
        f"{route}/{rule['id']}", json={"account_id": replacement_source["id"]}
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["account_id"] == replacement_source["id"]
    assert patched.json()["default_from_account_id"] == replacement_source["id"]
    assert patched.json()["default_to_account_id"] == destination["id"]


async def test_openapi_exposes_mobile_plan_adapter_and_detail_route(client):
    schema = (await client.get("/openapi.json")).json()
    plan_create = schema["components"]["schemas"]["PlanRuleCreate"]["properties"]
    plan_out = schema["components"]["schemas"]["PlanRuleOut"]["properties"]

    assert "expectedIncome" in plan_create["kind"]["enum"]
    assert "account_id" in plan_create
    assert {"mobile_kind", "account_field", "account_id"} <= set(plan_out)
    assert (
        f"/api/v1/workspaces/{{workspace_id}}/plan-rules/{{rule_id}}"
        in schema["paths"]
    )
