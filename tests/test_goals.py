"""Savings goals, planned contributions, and atomic ledger transfers."""

from datetime import date, timedelta
from decimal import Decimal


D = Decimal


async def create_period(client, start, clone_from=None):
    params = {}
    if clone_from is not None:
        params["clone_from_period_id"] = clone_from
    response = await client.post(
        "/periods",
        params=params,
        json={
            "total_amount": "1000",
            "start_date": start.isoformat(),
            "end_date": (start + timedelta(days=9)).isoformat(),
        },
    )
    assert response.status_code == 200
    return response.json()["period"]["id"]


async def test_savings_transfers_affect_period_and_persistent_goal(client):
    today = date.today()
    period_id = await create_period(client, today)
    goal = (
        await client.post(
            "/savings-goals",
            json={"name": "Emergency fund", "target_amount": "3000"},
        )
    ).json()

    plan = await client.put(
        f"/periods/{period_id}/goal-plans/{goal['id']}",
        json={"planned_amount": "400"},
    )
    assert plan.status_code == 200

    pool = (await client.post("/pools", json={"name": "Living"})).json()
    too_much = await client.put(
        f"/periods/{period_id}/pool-plans/{pool['id']}",
        json={"allocated_amount": "700"},
    )
    assert too_much.status_code == 409
    assert (
        await client.put(
            f"/periods/{period_id}/pool-plans/{pool['id']}",
            json={"allocated_amount": "600"},
        )
    ).status_code == 200

    first = await client.post(
        f"/periods/{period_id}/operations",
        json={
            "amount": "300",
            "kind": "transfer_to_goal",
            "savings_goal_id": goal["id"],
        },
    )
    assert first.status_code == 200
    assert first.json()["warnings"] == []
    assert D(first.json()["budget"]["remaining_money"]) == D("700")

    second = await client.post(
        f"/periods/{period_id}/operations",
        json={
            "amount": "150",
            "kind": "transfer_to_goal",
            "savings_goal_id": goal["id"],
        },
    )
    assert second.status_code == 200
    assert second.json()["warnings"][0]["scope"] == "goal"
    assert D(second.json()["warnings"][0]["over_by"]) == D("50")

    listed_goal = (await client.get("/savings-goals")).json()[0]
    assert D(listed_goal["balance"]) == D("450")
    assert D(listed_goal["remaining"]) == D("2550")

    withdrawal = await client.post(
        f"/periods/{period_id}/operations",
        json={
            "amount": "100",
            "kind": "transfer_from_goal",
            "savings_goal_id": goal["id"],
        },
    )
    assert withdrawal.status_code == 200
    assert D(withdrawal.json()["budget"]["spent_total"]) == D("350")
    assert D(withdrawal.json()["budget"]["remaining_money"]) == D("650")
    assert D((await client.get("/savings-goals")).json()[0]["balance"]) == D("350")

    rejected = await client.post(
        f"/periods/{period_id}/operations",
        json={
            "amount": "400",
            "kind": "transfer_from_goal",
            "savings_goal_id": goal["id"],
        },
    )
    assert rejected.status_code == 409
    assert D((await client.get("/savings-goals")).json()[0]["balance"]) == D("350")

    next_period_id = await create_period(
        client, today + timedelta(days=10), clone_from=period_id
    )
    next_plans = (await client.get(f"/periods/{next_period_id}/goal-plans")).json()
    assert len(next_plans) == 1
    assert D(next_plans[0]["planned_amount"]) == D("400")
    assert D(next_plans[0]["contributed"]) == D("0")
    assert D(next_plans[0]["goal"]["balance"]) == D("350")


async def test_goal_reference_rules(client):
    period_id = await create_period(client, date.today())
    goal = (
        await client.post(
            "/savings-goals", json={"name": "Trip", "target_amount": "500"}
        )
    ).json()
    missing_goal = await client.post(
        f"/periods/{period_id}/operations",
        json={"amount": "10", "kind": "transfer_to_goal"},
    )
    assert missing_goal.status_code == 422
    invalid_expense = await client.post(
        f"/periods/{period_id}/operations",
        json={"amount": "10", "savings_goal_id": goal["id"]},
    )
    assert invalid_expense.status_code == 422
