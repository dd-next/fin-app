"""Workspace categories, period limits, and non-blocking warnings."""

from datetime import date, timedelta
from decimal import Decimal


D = Decimal


async def current_period(client, total="100"):
    today = date.today()
    response = await client.post(
        "/api/v1/workspaces/1/periods",
        json={
            "total_amount": total,
            "start_date": today.isoformat(),
            "end_date": (today + timedelta(days=9)).isoformat(),
        },
    )
    assert response.status_code == 200
    return response.json()["period"]["id"]


async def create_category(client, name):
    response = await client.post("/api/v1/workspaces/1/categories", json={"name": name})
    assert response.status_code == 200
    return response.json()


async def test_category_limits_warn_but_do_not_block_real_expense(client):
    period_id = await current_period(client)
    food = await create_category(client, "Food")
    home = await create_category(client, "Home")

    duplicate = await client.post("/api/v1/workspaces/1/categories", json={"name": "  food  "})
    assert duplicate.status_code == 409

    response = await client.put(
        f"/api/v1/workspaces/1/periods/{period_id}/category-plans/{food['id']}",
        json={"limit_amount": "60"},
    )
    assert response.status_code == 200
    assert D(response.json()["remaining"]) == D("60")

    too_much = await client.put(
        f"/api/v1/workspaces/1/periods/{period_id}/category-plans/{home['id']}",
        json={"limit_amount": "50"},
    )
    assert too_much.status_code == 409
    assert (
        await client.put(
            f"/api/v1/workspaces/1/periods/{period_id}/category-plans/{home['id']}",
            json={"limit_amount": "40"},
        )
    ).status_code == 200

    expense = await client.post(
        f"/api/v1/workspaces/1/periods/{period_id}/operations",
        json={"amount": "70", "category_id": food["id"]},
    )
    assert expense.status_code == 200
    body = expense.json()
    assert D(body["budget"]["spent_total"]) == D("70")
    assert body["warnings"] == [
        {
            "scope": "category",
            "target_id": food["id"],
            "name": "Food",
            "limit_amount": "60",
            "spent": "70",
            "over_by": "10",
        }
    ]

    plans = (await client.get(f"/api/v1/workspaces/1/periods/{period_id}/category-plans")).json()
    food_plan = next(p for p in plans if p["category"]["id"] == food["id"])
    assert food_plan["over_limit"] is True
    assert D(food_plan["remaining"]) == D("-10")

    # Planning is strict, but lowering below allocated limits is rejected too.
    lowered = await client.patch(
        f"/api/v1/workspaces/1/periods/{period_id}", json={"total_amount": "90"}
    )
    assert lowered.status_code == 409

    operation_id = body["operation"]["id"]
    assert (await client.delete(f"/api/v1/workspaces/1/operations/{operation_id}")).status_code == 200
    plans = (await client.get(f"/api/v1/workspaces/1/periods/{period_id}/category-plans")).json()
    food_plan = next(p for p in plans if p["category"]["id"] == food["id"])
    assert D(food_plan["spent"]) == D("0")
    assert food_plan["over_limit"] is False


async def test_uncategorized_allowed_and_income_category_rejected(client):
    period_id = await current_period(client, total="1000")
    food = await create_category(client, "Food")

    uncategorized = await client.post(
        f"/api/v1/workspaces/1/periods/{period_id}/operations", json={"amount": "10"}
    )
    assert uncategorized.status_code == 200
    assert uncategorized.json()["operation"]["category_id"] is None
    assert uncategorized.json()["warnings"] == []

    invalid_income = await client.post(
        f"/api/v1/workspaces/1/periods/{period_id}/operations",
        json={"amount": "10", "kind": "income", "category_id": food["id"]},
    )
    assert invalid_income.status_code == 422

    archived = await client.patch(
        f"/api/v1/workspaces/1/categories/{food['id']}", json={"archived": True}
    )
    assert archived.status_code == 200
    assert (await client.get("/api/v1/workspaces/1/categories")).json() == []
    rejected = await client.post(
        f"/api/v1/workspaces/1/periods/{period_id}/operations",
        json={"amount": "5", "category_id": food["id"]},
    )
    assert rejected.status_code == 422
