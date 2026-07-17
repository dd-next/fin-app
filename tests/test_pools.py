"""Pool allocation, nested category limits, warnings, and plan cloning."""

from datetime import date, timedelta
from decimal import Decimal


D = Decimal


async def create_period(client, start, total="1000", clone_from=None):
    params = {}
    if clone_from is not None:
        params["clone_from_period_id"] = clone_from
    response = await client.post(
        "/periods",
        params=params,
        json={
            "total_amount": total,
            "start_date": start.isoformat(),
            "end_date": (start + timedelta(days=9)).isoformat(),
        },
    )
    assert response.status_code == 200
    return response.json()["period"]["id"]


async def test_pool_nested_limits_and_soft_warning(client):
    period_id = await create_period(client, date.today())
    home = (await client.post("/pools", json={"name": "Home"})).json()
    food_pool = (await client.post("/pools", json={"name": "Food"})).json()
    rent = (await client.post("/categories", json={"name": "Rent"})).json()
    utilities = (await client.post("/categories", json={"name": "Utilities"})).json()

    home_plan = await client.put(
        f"/periods/{period_id}/pool-plans/{home['id']}",
        json={"allocated_amount": "600"},
    )
    assert home_plan.status_code == 200
    home_plan_id = home_plan.json()["id"]

    too_much = await client.put(
        f"/periods/{period_id}/pool-plans/{food_pool['id']}",
        json={"allocated_amount": "500"},
    )
    assert too_much.status_code == 409
    assert (
        await client.put(
            f"/periods/{period_id}/pool-plans/{food_pool['id']}",
            json={"allocated_amount": "400"},
        )
    ).status_code == 200

    assert (
        await client.put(
            f"/periods/{period_id}/category-plans/{rent['id']}",
            json={"limit_amount": "400", "pool_plan_id": home_plan_id},
        )
    ).status_code == 200
    child_overflow = await client.put(
        f"/periods/{period_id}/category-plans/{utilities['id']}",
        json={"limit_amount": "250", "pool_plan_id": home_plan_id},
    )
    assert child_overflow.status_code == 409
    assert (
        await client.put(
            f"/periods/{period_id}/category-plans/{utilities['id']}",
            json={"limit_amount": "200", "pool_plan_id": home_plan_id},
        )
    ).status_code == 200

    cannot_lower = await client.put(
        f"/periods/{period_id}/pool-plans/{home['id']}",
        json={"allocated_amount": "599"},
    )
    assert cannot_lower.status_code == 409

    first = await client.post(
        f"/periods/{period_id}/operations",
        json={"amount": "450", "category_id": rent["id"]},
    )
    assert first.status_code == 200
    assert [warning["scope"] for warning in first.json()["warnings"]] == ["category"]

    second = await client.post(
        f"/periods/{period_id}/operations",
        json={"amount": "200", "category_id": utilities["id"]},
    )
    assert second.status_code == 200
    assert [warning["scope"] for warning in second.json()["warnings"]] == ["pool"]
    assert D(second.json()["warnings"][0]["over_by"]) == D("50")

    plans = (await client.get(f"/periods/{period_id}/pool-plans")).json()
    home_result = next(plan for plan in plans if plan["pool"]["id"] == home["id"])
    assert D(home_result["spent"]) == D("650")
    assert D(home_result["remaining"]) == D("-50")
    assert home_result["over_limit"] is True


async def test_period_plan_clone_copies_structure_not_spending(client):
    today = date.today()
    period_id = await create_period(client, today, total="500")
    pool = (await client.post("/pools", json={"name": "Home"})).json()
    category = (await client.post("/categories", json={"name": "Rent"})).json()
    pool_plan = (
        await client.put(
            f"/periods/{period_id}/pool-plans/{pool['id']}",
            json={"allocated_amount": "300"},
        )
    ).json()
    await client.put(
        f"/periods/{period_id}/category-plans/{category['id']}",
        json={"limit_amount": "250", "pool_plan_id": pool_plan["id"]},
    )
    await client.post(
        f"/periods/{period_id}/operations",
        json={"amount": "100", "category_id": category["id"]},
    )

    next_period_id = await create_period(
        client, today + timedelta(days=10), total="500", clone_from=period_id
    )
    next_pools = (await client.get(f"/periods/{next_period_id}/pool-plans")).json()
    next_categories = (
        await client.get(f"/periods/{next_period_id}/category-plans")
    ).json()
    assert len(next_pools) == 1
    assert D(next_pools[0]["allocated_amount"]) == D("300")
    assert D(next_pools[0]["spent"]) == D("0")
    assert len(next_categories) == 1
    assert D(next_categories[0]["limit_amount"]) == D("250")
    assert next_categories[0]["pool_plan_id"] == next_pools[0]["id"]
    assert D(next_categories[0]["spent"]) == D("0")
