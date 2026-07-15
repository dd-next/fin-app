"""API tests for the next-day savings decision (savings-prompt/-decision)."""

from datetime import date, timedelta
from decimal import Decimal

D = Decimal


def period_started_yesterday(days: int = 10, total: str = "1000") -> dict:
    start = date.today() - timedelta(days=1)
    end = start + timedelta(days=days - 1)
    return {
        "total_amount": total,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
    }


async def test_prompt_shown_when_yesterday_saved(client):
    # started yesterday, nothing spent → yesterday's 100 carried into today
    await client.post("/period", json=period_started_yesterday())
    resp = await client.get("/savings-prompt")
    assert resp.status_code == 200
    p = resp.json()
    assert p["show"] is True
    assert D(p["saved"]) == D("100.00")
    assert D(p["spend_today_value"]) == D("200.00")  # 100 base + 100 saved
    assert D(p["increase_daily_value"]) == D("111.11")  # 1000 / 9


async def test_prompt_hidden_on_first_day_and_without_period(client):
    resp = await client.get("/savings-prompt")
    assert resp.json() == {"show": False}  # no period at all

    start = date.today()
    await client.post("/period", json={
        "total_amount": "1000",
        "start_date": start.isoformat(),
        "end_date": (start + timedelta(days=9)).isoformat(),
    })
    resp = await client.get("/savings-prompt")
    assert resp.json() == {"show": False}  # first day: no yesterday to judge


async def test_prompt_survives_todays_spending(client):
    # saved is the carry at the START of today: spending today must not
    # change what yesterday left over (only answering hides the prompt).
    await client.post("/period", json=period_started_yesterday())
    await client.post("/operations", json={"amount": "150"})
    p = (await client.get("/savings-prompt")).json()
    assert p["show"] is True
    assert D(p["saved"]) == D("100.00")
    # (an overspent yesterday leaves zero carry → no prompt; that math is
    # unit-tested in test_budget.py, where days can be backdated)


async def test_decision_spend_today_keeps_numbers_and_acks(client):
    await client.post("/period", json=period_started_yesterday())
    before = (await client.get("/budget")).json()
    assert D(before["budget_today"]) == D("200.00")

    resp = await client.post(
        "/savings-decision", json={"choice": "spend_today"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    # numbers unchanged: the leftover still rolls onto today
    assert D(body["budget"]["budget_today"]) == D("200.00")
    assert D(body["budget"]["daily_base"]) == D("100.00")

    # prompt shows exactly once per qualifying day
    assert (await client.get("/savings-prompt")).json() == {"show": False}


async def test_decision_increase_daily_respreads_and_persists(client):
    await client.post("/period", json=period_started_yesterday())
    resp = await client.post(
        "/savings-decision", json={"choice": "increase_daily"}
    )
    assert resp.status_code == 200
    b = resp.json()["budget"]
    # 1000 re-spread over the 9 remaining days; carry-over gone
    assert D(b["daily_base"]) == D("111.11")
    assert D(b["budget_today"]) == D("111.11")

    # persisted: a fresh GET recomputes the same numbers from the DB
    again = (await client.get("/budget")).json()
    assert D(again["budget_today"]) == D("111.11")
    assert (await client.get("/savings-prompt")).json() == {"show": False}


async def test_decision_without_period_404(client):
    resp = await client.post(
        "/savings-decision", json={"choice": "spend_today"}
    )
    assert resp.status_code == 404


async def test_decision_bad_choice_422(client):
    await client.post("/period", json=period_started_yesterday())
    resp = await client.post("/savings-decision", json={"choice": "hoard"})
    assert resp.status_code == 422
