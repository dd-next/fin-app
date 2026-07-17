"""API tests via httpx.AsyncClient against the FastAPI app."""

from datetime import date, timedelta
from decimal import Decimal

from app.main import app

D = Decimal


def today_period(days: int = 10, total: str = "1000") -> dict:
    """A period starting today spanning `days` days, so days_remaining==days."""
    start = date.today()
    end = start + timedelta(days=days - 1)
    return {
        "total_amount": total,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
    }


async def set_period(client, **kwargs):
    resp = await client.post("/api/v1/workspaces/1/periods", json=today_period(**kwargs))
    assert resp.status_code == 200
    return resp.json()


async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_post_period_then_budget_summary(client):
    body = await set_period(client, days=10, total="1000")
    assert D(body["period"]["total_amount"]) == D("1000")

    resp = await client.get("/api/v1/workspaces/1/budget")
    assert resp.status_code == 200
    b = resp.json()
    assert b["days_total"] == 10
    assert b["days_remaining"] == 10
    assert D(b["spent_total"]) == D("0")
    assert D(b["remaining_money"]) == D("1000")
    assert D(b["per_day_today"]) == D("100.00")
    assert D(b["daily_base"]) == D("100.00")
    assert D(b["budget_today"]) == D("100.00")
    assert D(b["spent_today"]) == D("0")
    assert D(b["next_daily"]) == D("200.00")  # untouched today rolls forward


async def test_period_history_is_preserved_and_selectable(client):
    today = date.today()
    old = {
        "total_amount": "800",
        "start_date": (today - timedelta(days=20)).isoformat(),
        "end_date": (today - timedelta(days=11)).isoformat(),
    }
    old_id = (await client.post("/api/v1/workspaces/1/periods", json=old)).json()["period"]["id"]
    resp = await client.post(
        f"/api/v1/workspaces/1/periods/{old_id}/operations",
        json={"amount": "50", "occurred_on": old["end_date"]},
    )
    assert resp.status_code == 200

    current = await set_period(client, days=5, total="500")
    current_id = current["period"]["id"]

    history = (await client.get("/api/v1/workspaces/1/periods")).json()
    assert [p["period"]["id"] for p in history] == [current_id, old_id]
    assert history[0]["period"]["status"] == "current"
    assert history[1]["period"]["status"] == "ended"
    assert D(history[1]["budget"]["spent_total"]) == D("50")

    old_ops = (await client.get(f"/api/v1/workspaces/1/periods/{old_id}/operations")).json()
    assert len(old_ops) == 1
    assert D(old_ops[0]["amount"]) == D("50")


async def test_overlapping_period_is_rejected(client):
    await set_period(client, days=10, total="1000")
    resp = await client.post("/api/v1/workspaces/1/periods", json=today_period(days=5, total="500"))
    assert resp.status_code == 409
    assert "overlap" in resp.json()["detail"].lower()


async def test_ended_period_edit_requires_confirmation(client):
    today = date.today()
    payload = {
        "total_amount": "500",
        "start_date": (today - timedelta(days=10)).isoformat(),
        "end_date": (today - timedelta(days=1)).isoformat(),
    }
    period_id = (await client.post("/api/v1/workspaces/1/periods", json=payload)).json()["period"]["id"]

    resp = await client.patch(f"/api/v1/workspaces/1/periods/{period_id}", json={"total_amount": "600"})
    assert resp.status_code == 409
    resp = await client.patch(
        f"/api/v1/workspaces/1/periods/{period_id}?confirm_ended=true",
        json={"total_amount": "600"},
    )
    assert resp.status_code == 200
    assert D(resp.json()["period"]["total_amount"]) == D("600")


async def test_operation_financial_date_must_be_inside_period(client):
    body = await set_period(client, days=10, total="1000")
    period_id = body["period"]["id"]
    start = date.fromisoformat(body["period"]["start_date"])
    resp = await client.post(
        f"/api/v1/workspaces/1/periods/{period_id}/operations",
        json={"amount": "10", "occurred_on": start.isoformat()},
    )
    assert resp.status_code == 200
    assert resp.json()["operation"]["occurred_on"] == start.isoformat()

    resp = await client.post(
        f"/api/v1/workspaces/1/periods/{period_id}/operations",
        json={"amount": "10", "occurred_on": (start - timedelta(days=1)).isoformat()},
    )
    assert resp.status_code == 422


async def test_expense_updates_budget_and_delete_restores(client):
    await set_period(client, days=10, total="1000")

    resp = await client.post("/api/v1/workspaces/1/operations", json={"amount": "250", "comment": "food"})
    assert resp.status_code == 200
    body = resp.json()
    operation_id = body["operation"]["id"]
    assert body["operation"]["comment"] == "food"
    assert body["operation"]["kind"] == "expense"  # the default
    assert D(body["budget"]["remaining_money"]) == D("750")
    # spending reduces TODAY 1:1: 100 budget - 250 spent, not (1000-250)/10
    assert D(body["budget"]["budget_today"]) == D("100.00")
    assert D(body["budget"]["per_day_today"]) == D("-150.00")

    resp = await client.delete(f"/api/v1/workspaces/1/operations/{operation_id}")
    assert resp.status_code == 200
    b = resp.json()
    assert D(b["remaining_money"]) == D("1000")
    assert D(b["per_day_today"]) == D("100.00")


async def test_expenses_listed_newest_first(client):
    await set_period(client)
    for amount in ("10", "20", "30"):
        await client.post("/api/v1/workspaces/1/operations", json={"amount": amount})
    items = (await client.get("/api/v1/workspaces/1/operations")).json()
    assert [D(e["amount"]) for e in items] == [D("30"), D("20"), D("10")]


async def test_budget_pending_preview(client):
    await set_period(client, days=10, total="1000")
    resp = await client.get("/api/v1/workspaces/1/budget", params={"pending": "30"})
    assert resp.status_code == 200
    b = resp.json()
    assert D(b["preview_after"]) == D("70.00")  # today's 100.00 - 30


async def test_overspend_negative_not_clamped(client):
    await set_period(client, days=10, total="100")
    await client.post("/api/v1/workspaces/1/operations", json={"amount": "150"})
    b = (await client.get("/api/v1/workspaces/1/budget")).json()
    assert D(b["remaining_money"]) == D("-50")
    assert D(b["per_day_today"]) == D("-140.00")  # 10 today - 150 spent
    assert D(b["next_daily"]) == D("-5.56")  # -50/9, rebase preview


async def test_delete_missing_expense_404(client):
    await set_period(client)
    resp = await client.delete("/api/v1/workspaces/1/operations/99999")
    assert resp.status_code == 404


async def test_get_period_404_when_none(client):
    resp = await client.get("/api/v1/workspaces/1/period")
    assert resp.status_code == 404
    resp = await client.get("/api/v1/workspaces/1/budget")
    assert resp.status_code == 404


async def test_bad_input_422(client):
    # malformed amount
    resp = await client.post(
        "/api/v1/workspaces/1/periods",
        json={"total_amount": "not-money", "start_date": "2026-07-01", "end_date": "2026-07-10"},
    )
    assert resp.status_code == 422
    # end_date before start_date
    resp = await client.post(
        "/api/v1/workspaces/1/periods",
        json={"total_amount": "100", "start_date": "2026-07-10", "end_date": "2026-07-01"},
    )
    assert resp.status_code == 422
    # malformed expense
    await set_period(client)
    resp = await client.post("/api/v1/workspaces/1/operations", json={"amount": "abc"})
    assert resp.status_code == 422
    # malformed pending
    resp = await client.get("/api/v1/workspaces/1/budget", params={"pending": "xyz"})
    assert resp.status_code == 422


async def test_expense_without_period_404(client):
    resp = await client.post("/api/v1/workspaces/1/operations", json={"amount": "10"})
    assert resp.status_code == 404


async def test_operations_roundtrip_both_kinds(client):
    await set_period(client, days=10, total="1000")

    resp = await client.post("/api/v1/workspaces/1/operations", json={"amount": "100", "comment": "food"})
    assert resp.status_code == 200
    resp = await client.post(
        "/api/v1/workspaces/1/operations", json={"amount": "50", "kind": "income", "comment": "refund"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["operation"]["kind"] == "income"
    # income raises today's number 1:1: 100 - 100 + 50
    assert D(body["budget"]["per_day_today"]) == D("50.00")
    assert D(body["budget"]["remaining_money"]) == D("950")

    items = (await client.get("/api/v1/workspaces/1/operations")).json()
    assert [(i["kind"], D(i["amount"])) for i in items] == [
        ("income", D("50")),
        ("expense", D("100")),
    ]

    # deleting the income recomputes correctly
    resp = await client.delete(f"/api/v1/workspaces/1/operations/{body['operation']['id']}")
    assert resp.status_code == 200
    b = resp.json()
    assert D(b["per_day_today"]) == D("0.00")
    assert D(b["remaining_money"]) == D("900")


async def test_operation_invalid_kind_422(client):
    await set_period(client)
    resp = await client.post(
        "/api/v1/workspaces/1/operations", json={"amount": "10", "kind": "transfer"}
    )
    assert resp.status_code == 422


async def test_operation_patch_recalculates_all_totals(client):
    body = await set_period(client, days=10, total="1000")
    period_id = body["period"]["id"]
    category = (
        await client.post(
            "/api/v1/workspaces/1/categories", json={"name": "Food"}
        )
    ).json()
    await client.put(
        f"/api/v1/workspaces/1/periods/{period_id}/category-plans/{category['id']}",
        json={"limit_amount": "500"},
    )
    created = await client.post(
        f"/api/v1/workspaces/1/periods/{period_id}/operations",
        json={"amount": "100", "category_id": category["id"]},
    )
    operation_id = created.json()["operation"]["id"]

    corrected = await client.patch(
        f"/api/v1/workspaces/1/periods/{period_id}/operations/{operation_id}",
        json={"amount": "40", "comment": "corrected"},
    )
    assert corrected.status_code == 200
    assert corrected.json()["operation"]["comment"] == "corrected"
    assert D(corrected.json()["budget"]["spent_total"]) == D("40")
    assert D(corrected.json()["budget"]["remaining_money"]) == D("960")
    plans = (
        await client.get(
            f"/api/v1/workspaces/1/periods/{period_id}/category-plans"
        )
    ).json()
    assert D(plans[0]["spent"]) == D("40")


async def test_ended_operation_patch_requires_confirmation(client):
    today = date.today()
    payload = {
        "total_amount": "500",
        "start_date": (today - timedelta(days=10)).isoformat(),
        "end_date": (today - timedelta(days=1)).isoformat(),
    }
    period_id = (
        await client.post("/api/v1/workspaces/1/periods", json=payload)
    ).json()["period"]["id"]
    operation_id = (
        await client.post(
            f"/api/v1/workspaces/1/periods/{period_id}/operations",
            json={"amount": "100", "occurred_on": payload["end_date"]},
        )
    ).json()["operation"]["id"]

    denied = await client.patch(
        f"/api/v1/workspaces/1/periods/{period_id}/operations/{operation_id}",
        json={"amount": "75"},
    )
    assert denied.status_code == 409
    corrected = await client.patch(
        f"/api/v1/workspaces/1/periods/{period_id}/operations/{operation_id}",
        params={"confirm_ended": "true"},
        json={"amount": "75"},
    )
    assert corrected.status_code == 200
    assert D(corrected.json()["budget"]["spent_total"]) == D("75")


def test_financial_api_has_no_legacy_root_routes():
    paths = set(app.openapi()["paths"])
    assert "/period" not in paths
    assert "/periods" not in paths
    assert "/operations" not in paths
    assert "/budget" not in paths
    assert "/export.xlsx" not in paths
