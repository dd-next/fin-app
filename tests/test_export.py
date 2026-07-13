"""Round-trip test: create data via the API, download /export.xlsx, load the
bytes back with openpyxl, and check both sheets against the API's numbers."""

from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

from openpyxl import load_workbook

D = Decimal


async def test_export_roundtrip(client):
    start = date.today()
    end = start + timedelta(days=9)  # 10-day period
    resp = await client.post(
        "/period",
        json={
            "total_amount": "1000",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
    )
    assert resp.status_code == 200

    for amount, comment in [("250", "groceries"), ("100", None), ("50.50", "coffee")]:
        resp = await client.post("/expenses", json={"amount": amount, "comment": comment})
        assert resp.status_code == 200

    api_budget = (await client.get("/budget")).json()
    api_expenses = (await client.get("/expenses")).json()

    resp = await client.get("/export.xlsx")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert resp.headers["content-disposition"] == 'attachment; filename="tzlvt-export.xlsx"'

    wb = load_workbook(BytesIO(resp.content))
    assert wb.sheetnames == ["Period", "Expenses"]

    # --- Period sheet: key/value pairs match the API ------------------------
    period_kv = {row[0]: row[1] for row in wb["Period"].iter_rows(values_only=True)}
    assert D(str(period_kv["total_amount"])) == D("1000")
    assert period_kv["start_date"] == start.isoformat()
    assert period_kv["end_date"] == end.isoformat()
    assert period_kv["days_total"] == api_budget["days_total"]
    assert D(str(period_kv["spent_total"])) == D(api_budget["spent_total"]) == D("400.50")
    assert D(str(period_kv["remaining"])) == D(api_budget["remaining_money"]) == D("599.50")

    # --- Expenses sheet: header + one row per expense, replayed in order ----
    rows = list(wb["Expenses"].iter_rows(values_only=True))
    assert rows[0] == (
        "Date",
        "Amount",
        "Comment",
        "Running balance",
        "Per-day allowance at that point",
    )
    body = rows[1:]
    assert len(body) == len(api_expenses) == 3

    # chronological order (API lists newest first — export replays oldest first)
    amounts = [D(str(r[1])) for r in body]
    assert amounts == [D("250"), D("100"), D("50.50")]
    assert sum(amounts) == D(api_budget["spent_total"])

    # running balance replays correctly and ends at the API's remaining_money
    balances = [D(str(r[3])) for r in body]
    assert balances == [D("750"), D("650"), D("599.50")]
    assert balances[-1] == D(api_budget["remaining_money"])

    # per-day allowance at the last point matches the API (all added today)
    assert D(str(body[-1][4])) == D(api_budget["per_day_today"])

    # dates are YYYY-MM-DD strings; comments preserved (blank for None —
    # openpyxl reads empty cells back as None)
    assert all(r[0] == start.isoformat() for r in body)
    assert [r[2] or "" for r in body] == ["groceries", "", "coffee"]


async def test_export_404_when_no_period(client):
    resp = await client.get("/export.xlsx")
    assert resp.status_code == 404
