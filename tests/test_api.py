"""API tests via httpx.AsyncClient against the FastAPI app."""

from datetime import date, timedelta
from decimal import Decimal

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
    resp = await client.post("/period", json=today_period(**kwargs))
    assert resp.status_code == 200
    return resp.json()


async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_post_period_then_budget_summary(client):
    body = await set_period(client, days=10, total="1000")
    assert D(body["period"]["total_amount"]) == D("1000")

    resp = await client.get("/budget")
    assert resp.status_code == 200
    b = resp.json()
    assert b["days_total"] == 10
    assert b["days_remaining"] == 10
    assert D(b["spent_total"]) == D("0")
    assert D(b["remaining_money"]) == D("1000")
    assert D(b["per_day_today"]) == D("100.00")


async def test_post_period_replaces_existing(client):
    await set_period(client, days=10, total="1000")
    resp = await client.post("/expenses", json={"amount": "50"})
    assert resp.status_code == 200

    await set_period(client, days=5, total="500")
    b = (await client.get("/budget")).json()
    assert b["days_total"] == 5
    assert D(b["spent_total"]) == D("0")  # old expenses gone with old period
    assert (await client.get("/expenses")).json() == []


async def test_expense_updates_budget_and_delete_restores(client):
    await set_period(client, days=10, total="1000")

    resp = await client.post("/expenses", json={"amount": "250", "comment": "food"})
    assert resp.status_code == 200
    body = resp.json()
    expense_id = body["expense"]["id"]
    assert body["expense"]["comment"] == "food"
    assert D(body["budget"]["remaining_money"]) == D("750")
    assert D(body["budget"]["per_day_today"]) == D("75.00")

    resp = await client.delete(f"/expenses/{expense_id}")
    assert resp.status_code == 200
    b = resp.json()
    assert D(b["remaining_money"]) == D("1000")
    assert D(b["per_day_today"]) == D("100.00")


async def test_expenses_listed_newest_first(client):
    await set_period(client)
    for amount in ("10", "20", "30"):
        await client.post("/expenses", json={"amount": amount})
    items = (await client.get("/expenses")).json()
    assert [D(e["amount"]) for e in items] == [D("30"), D("20"), D("10")]


async def test_budget_pending_preview(client):
    await set_period(client, days=10, total="1000")
    resp = await client.get("/budget", params={"pending": "100"})
    assert resp.status_code == 200
    b = resp.json()
    assert D(b["preview_after"]) == D("90.00")  # (1000-100)/10


async def test_overspend_negative_not_clamped(client):
    await set_period(client, days=10, total="100")
    await client.post("/expenses", json={"amount": "150"})
    b = (await client.get("/budget")).json()
    assert D(b["remaining_money"]) == D("-50")
    assert D(b["per_day_today"]) == D("-5.00")


async def test_delete_missing_expense_404(client):
    await set_period(client)
    resp = await client.delete("/expenses/99999")
    assert resp.status_code == 404


async def test_get_period_404_when_none(client):
    resp = await client.get("/period")
    assert resp.status_code == 404
    resp = await client.get("/budget")
    assert resp.status_code == 404


async def test_bad_input_422(client):
    # malformed amount
    resp = await client.post(
        "/period",
        json={"total_amount": "not-money", "start_date": "2026-07-01", "end_date": "2026-07-10"},
    )
    assert resp.status_code == 422
    # end_date before start_date
    resp = await client.post(
        "/period",
        json={"total_amount": "100", "start_date": "2026-07-10", "end_date": "2026-07-01"},
    )
    assert resp.status_code == 422
    # malformed expense
    await set_period(client)
    resp = await client.post("/expenses", json={"amount": "abc"})
    assert resp.status_code == 422
    # malformed pending
    resp = await client.get("/budget", params={"pending": "xyz"})
    assert resp.status_code == 422


async def test_expense_without_period_404(client):
    resp = await client.post("/expenses", json={"amount": "10"})
    assert resp.status_code == 404
