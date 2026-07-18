from datetime import date, timedelta
from decimal import Decimal

from tests.conftest import register
from tests.test_ledger_v2 import create_account
from tests.test_plan_v2 import create_rule
from tests.test_sharing_v2 import accept, invitation, login


D = Decimal
TODAY = date.today()


async def create_manual_period(
    client,
    workspace_id: int,
    *,
    start: date = TODAY,
    end: date | None = None,
    funding: str = "1000",
):
    return await client.post(
        f"/api/v1/workspaces/{workspace_id}/budget-periods",
        json={
            "start_date": start.isoformat(),
            "end_date": (end or (start + timedelta(days=9))).isoformat(),
            "funding_amount": funding,
            "confirmed": True,
        },
    )


async def occurrence_for_rule(client, workspace_id: int, rule_id: int):
    items = (
        await client.get(f"/api/v1/workspaces/{workspace_id}/plan-occurrences")
    ).json()
    return next(item for item in items if item["plan_rule_id"] == rule_id)


async def test_received_income_proposes_and_creates_confirmed_period_with_snapshot(client):
    context = await register(client)
    workspace_id = context["workspace"]["id"]
    main = await create_account(client, "Main USD", "USD", "0")
    await create_rule(
        client,
        workspace_id,
        name="Rent",
        amount="200",
        first_due_date=(TODAY + timedelta(days=1)).isoformat(),
        default_from_account_id=main["id"],
    )
    income_rule = (
        await create_rule(
            client,
            workspace_id,
            kind="income",
            name="Weekly salary",
            amount="1000",
            recurrence="weekly",
            first_due_date=TODAY.isoformat(),
            default_to_account_id=main["id"],
            is_required=False,
        )
    ).json()
    income = await occurrence_for_rule(client, workspace_id, income_rule["id"])
    received = await client.post(
        f"/api/v1/workspaces/{workspace_id}/plan-occurrences/{income['id']}/receive",
        json={},
    )
    assert received.status_code == 200, received.text
    proposal = received.json()["period_proposal"]
    assert proposal["start_date"] == TODAY.isoformat()
    assert proposal["end_date"] == (TODAY + timedelta(days=6)).isoformat()
    assert proposal["needs_end_date"] is False
    assert D(proposal["funding_amount"]) == D("1000")
    assert [(item["name"], D(item["planned_amount"])) for item in proposal["commitments"]] == [
        ("Rent", D("200"))
    ]

    preview = await client.post(
        f"/api/v1/workspaces/{workspace_id}/budget-periods/preview",
        json={"opening_transaction_id": received.json()["transaction_id"]},
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["end_date"] == proposal["end_date"]

    created = await client.post(
        f"/api/v1/workspaces/{workspace_id}/budget-periods",
        json={
            "opening_transaction_id": received.json()["transaction_id"],
            "confirmed": True,
        },
    )
    assert created.status_code == 201, created.text
    summary = created.json()
    assert D(summary["period"]["funding_amount"]) == D("1000")
    assert D(summary["period"]["commitments_total"]) == D("200")
    assert D(summary["period"]["daily_pool"]) == D("800")
    assert D(summary["spent_total"]) == 0
    opening = (
        await client.get(f"/api/v1/transactions/{received.json()['transaction_id']}")
    ).json()
    assert opening["budget_period_id"] == summary["period"]["id"]
    assert D(opening["base_amount"]) == D("1000")

    overlap = await create_manual_period(
        client, workspace_id, start=TODAY + timedelta(days=2)
    )
    assert overlap.status_code == 409

    await client.post("/api/v1/auth/logout")
    await register(client, "bob")
    assert (
        await client.get(f"/api/v1/workspaces/{workspace_id}/tracker/today")
    ).status_code == 404


async def test_commitment_fact_replaces_plan_and_is_not_deducted_twice(client):
    context = await register(client)
    workspace_id = context["workspace"]["id"]
    main = await create_account(client, "Main USD", "USD", "1000")
    rule = (
        await create_rule(
            client,
            workspace_id,
            name="Rent",
            amount="200",
            default_from_account_id=main["id"],
        )
    ).json()
    occurrence = await occurrence_for_rule(client, workspace_id, rule["id"])
    period = await create_manual_period(client, workspace_id)
    assert period.status_code == 201, period.text
    assert D(period.json()["period"]["daily_pool"]) == D("800")

    paid = await client.post(
        f"/api/v1/workspaces/{workspace_id}/plan-occurrences/{occurrence['id']}/pay",
        json={"amount": "250"},
    )
    assert paid.status_code == 200, paid.text
    today = (
        await client.get(f"/api/v1/workspaces/{workspace_id}/tracker/today")
    ).json()
    commitment = today["period"]["commitments"][0]
    assert commitment["status"] == "fulfilled"
    assert D(commitment["planned_amount"]) == D("200")
    assert D(commitment["actual_amount"]) == D("250")
    assert D(today["period"]["daily_pool"]) == D("750")
    assert D(today["spent_total"]) == 0
    assert D(today["available_today"]) == D("75.00")

    voided = await client.post(
        f"/api/v1/transactions/{paid.json()['transaction_id']}/void"
    )
    assert voided.status_code == 200, voided.text
    reopened = (
        await client.get(f"/api/v1/workspaces/{workspace_id}/tracker/today")
    ).json()
    assert reopened["period"]["commitments"][0]["status"] == "reserved"
    assert D(reopened["period"]["daily_pool"]) == D("800")

    manual = await client.post(
        "/api/v1/transactions/expense",
        json={"account_id": main["id"], "amount": "225", "local_date": TODAY.isoformat()},
    )
    assert manual.status_code == 201, manual.text
    before_link = (
        await client.get(f"/api/v1/workspaces/{workspace_id}/tracker/today")
    ).json()
    assert D(before_link["spent_total"]) == D("225")
    linked = await client.post(
        f"/api/v1/workspaces/{workspace_id}/plan-occurrences/{occurrence['id']}/link-transaction",
        json={"transaction_id": manual.json()["id"]},
    )
    assert linked.status_code == 200, linked.text
    after_link = (
        await client.get(f"/api/v1/workspaces/{workspace_id}/tracker/today")
    ).json()
    assert D(after_link["period"]["daily_pool"]) == D("775")
    assert D(after_link["spent_total"]) == 0


async def test_tracker_carry_preview_rebase_history_and_ended_confirmation(client):
    context = await register(client)
    workspace_id = context["workspace"]["id"]
    account = await create_account(client, "Daily USD", "USD", "1000")
    start = TODAY - timedelta(days=1)
    created = await create_manual_period(
        client, workspace_id, start=start, end=TODAY + timedelta(days=8)
    )
    assert created.status_code == 201, created.text
    expense = await client.post(
        "/api/v1/transactions/expense",
        json={
            "account_id": account["id"],
            "amount": "40",
            "local_date": start.isoformat(),
        },
    )
    assert expense.status_code == 201, expense.text
    summary = (
        await client.get(f"/api/v1/workspaces/{workspace_id}/tracker/today")
    ).json()
    assert D(summary["budget_today"]) == D("160.00")
    prompt = (
        await client.get(
            f"/api/v1/workspaces/{workspace_id}/tracker/savings-prompt"
        )
    ).json()
    assert prompt["required"] is True
    assert D(prompt["carry_amount"]) == D("60.00")
    preview = await client.get(
        f"/api/v1/workspaces/{workspace_id}/tracker/preview?pending=30"
    )
    assert preview.status_code == 200
    assert D(preview.json()["available_after"]) == D("130.00")
    rebased = await client.post(
        f"/api/v1/workspaces/{workspace_id}/tracker/savings-decision",
        json={"choice": "redistribute"},
    )
    assert rebased.status_code == 200, rebased.text
    assert D(rebased.json()["budget_today"]) == D("106.67")
    assert (
        await client.get(
            f"/api/v1/workspaces/{workspace_id}/tracker/savings-prompt"
        )
    ).json()["acknowledged"] is True

    historical_start = TODAY - timedelta(days=20)
    historical = await create_manual_period(
        client,
        workspace_id,
        start=historical_start,
        end=historical_start + timedelta(days=4),
        funding="500",
    )
    assert historical.status_code == 201, historical.text
    old_expense = await client.post(
        "/api/v1/transactions/expense",
        json={
            "account_id": account["id"],
            "amount": "50",
            "local_date": historical_start.isoformat(),
        },
    )
    assert old_expense.status_code == 201, old_expense.text
    assert (
        await client.patch(
            f"/api/v1/transactions/{old_expense.json()['id']}",
            json={"amount": "60"},
        )
    ).status_code == 409
    corrected = await client.patch(
        f"/api/v1/transactions/{old_expense.json()['id']}",
        json={"amount": "60", "confirm_ended_period": True},
    )
    assert corrected.status_code == 200, corrected.text
    assert (
        await client.post(f"/api/v1/transactions/{old_expense.json()['id']}/void")
    ).status_code == 409
    assert (
        await client.post(
            f"/api/v1/transactions/{old_expense.json()['id']}/void",
            json={"confirm_ended_period": True},
        )
    ).status_code == 200
    history = (
        await client.get(f"/api/v1/workspaces/{workspace_id}/budget-periods")
    ).json()
    assert len(history) == 2
    assert {item["status"] for item in history} == {"current", "ended"}


async def test_multi_asset_values_freeze_and_missing_rate_requires_equivalent(client):
    context = await register(client)
    workspace_id = context["workspace"]["id"]
    usd = await create_account(client, "USD", "USD", "2000")
    btc = await create_account(client, "BTC", "BTC", "1")
    eth = await create_account(client, "ETH", "ETH", "1")
    first_rate = await client.post(
        "/api/v1/transactions/exchange",
        json={
            "from_account_id": usd["id"],
            "from_amount": "1000",
            "to_account_id": btc["id"],
            "to_amount": "0.01",
        },
    )
    assert first_rate.status_code == 201, first_rate.text
    assert (await create_manual_period(client, workspace_id)).status_code == 201
    btc_expense = await client.post(
        "/api/v1/transactions/expense",
        json={"account_id": btc["id"], "amount": "0.001"},
    )
    assert btc_expense.status_code == 201, btc_expense.text
    assert D(btc_expense.json()["base_amount"]) == D("100")

    second_rate = await client.post(
        "/api/v1/transactions/exchange",
        json={
            "from_account_id": usd["id"],
            "from_amount": "2000",
            "to_account_id": btc["id"],
            "to_amount": "0.01",
        },
    )
    assert second_rate.status_code == 201, second_rate.text
    frozen = await client.get(f"/api/v1/transactions/{btc_expense.json()['id']}")
    assert D(frozen.json()["base_amount"]) == D("100")
    tracker = (
        await client.get(f"/api/v1/workspaces/{workspace_id}/tracker/today")
    ).json()
    assert D(tracker["spent_total"]) == D("100")

    missing = await client.post(
        "/api/v1/transactions/expense",
        json={"account_id": eth["id"], "amount": "0.01"},
    )
    assert missing.status_code == 422
    supplied = await client.post(
        "/api/v1/transactions/expense",
        json={
            "account_id": eth["id"],
            "amount": "0.01",
            "base_amount": "50",
        },
    )
    assert supplied.status_code == 201, supplied.text
    assert D(supplied.json()["base_amount"]) == D("50")


async def test_metadata_patch_preserves_frozen_value_but_amount_patch_revalues(client):
    context = await register(client)
    workspace_id = context["workspace"]["id"]
    usd = await create_account(client, "Rate USD", "USD", "5000")
    btc = await create_account(client, "Rate BTC", "BTC", "1")
    first_rate = await client.post(
        "/api/v1/transactions/exchange",
        json={
            "from_account_id": usd["id"],
            "from_amount": "1000",
            "to_account_id": btc["id"],
            "to_amount": "0.01",
        },
    )
    assert first_rate.status_code == 201, first_rate.text
    assert (await create_manual_period(client, workspace_id)).status_code == 201
    expense = await client.post(
        "/api/v1/transactions/expense",
        json={"account_id": btc["id"], "amount": "0.001"},
    )
    assert expense.status_code == 201, expense.text
    original = expense.json()
    assert D(original["base_amount"]) == D("100")

    latest_rate = await client.post(
        "/api/v1/transactions/exchange",
        json={
            "from_account_id": usd["id"],
            "from_amount": "2000",
            "to_account_id": btc["id"],
            "to_amount": "0.01",
        },
    )
    assert latest_rate.status_code == 201, latest_rate.text
    metadata_patch = await client.patch(
        f"/api/v1/transactions/{original['id']}",
        json={"note": "metadata only"},
    )
    assert metadata_patch.status_code == 200, metadata_patch.text
    metadata = metadata_patch.json()
    assert D(metadata["base_amount"]) == D("100")
    assert metadata["base_rate"] == original["base_rate"]
    assert metadata["rate_source"] == original["rate_source"]
    tracker = (
        await client.get(f"/api/v1/workspaces/{workspace_id}/tracker/today")
    ).json()
    assert D(tracker["spent_total"]) == D("100")

    for no_op_patch in (
        {"amount": "0.001"},
        {"occurred_at": None},
        {"from_amount": "2"},
    ):
        unchanged = await client.patch(
            f"/api/v1/transactions/{original['id']}",
            json=no_op_patch,
        )
        assert unchanged.status_code == 200, unchanged.text
        assert D(unchanged.json()["base_amount"]) == D("100")
        assert unchanged.json()["base_rate"] == original["base_rate"]
        assert unchanged.json()["rate_source"] == original["rate_source"]

    amount_patch = await client.patch(
        f"/api/v1/transactions/{original['id']}",
        json={"amount": "0.002"},
    )
    assert amount_patch.status_code == 200, amount_patch.text
    assert D(amount_patch.json()["base_amount"]) == D("400")
    tracker = (
        await client.get(f"/api/v1/workspaces/{workspace_id}/tracker/today")
    ).json()
    assert D(tracker["spent_total"]) == D("400")


async def test_shared_expense_joins_owner_period_but_tracker_remains_private(client):
    alice = await register(client)
    workspace_id = alice["workspace"]["id"]
    shared = await create_account(client, "Shared USD", "USD", "500")
    assert (await create_manual_period(client, workspace_id)).status_code == 201
    token = await invitation(client, shared["id"], "contributor")
    await register(client, "bob")
    await accept(client, token)
    expense = await client.post(
        "/api/v1/transactions/expense",
        json={"account_id": shared["id"], "amount": "25"},
    )
    assert expense.status_code == 201, expense.text
    assert expense.json()["budget_period_id"] is None
    assert expense.json()["base_amount"] is None
    assert (
        await client.get(f"/api/v1/workspaces/{workspace_id}/tracker/today")
    ).status_code == 404
    await login(client, "alice")
    owner_view = await client.get(f"/api/v1/transactions/{expense.json()['id']}")
    assert owner_view.json()["budget_period_id"] is not None
    assert D(owner_view.json()["base_amount"]) == D("25")
    tracker = (
        await client.get(f"/api/v1/workspaces/{workspace_id}/tracker/today")
    ).json()
    assert D(tracker["spent_total"]) == D("25")


async def test_one_time_income_requires_user_end_date_before_period_creation(client):
    context = await register(client)
    workspace_id = context["workspace"]["id"]
    account = await create_account(client, "Income USD", "USD", "0")
    rule = (
        await create_rule(
            client,
            workspace_id,
            kind="income",
            name="One-time income",
            amount="600",
            recurrence="once",
            default_to_account_id=account["id"],
            is_required=False,
        )
    ).json()
    occurrence = await occurrence_for_rule(client, workspace_id, rule["id"])
    received = await client.post(
        f"/api/v1/workspaces/{workspace_id}/plan-occurrences/{occurrence['id']}/receive",
        json={},
    )
    proposal = received.json()["period_proposal"]
    assert proposal["end_date"] is None
    assert proposal["needs_end_date"] is True
    opening_transaction_id = received.json()["transaction_id"]
    missing_end = await client.post(
        f"/api/v1/workspaces/{workspace_id}/budget-periods",
        json={"opening_transaction_id": opening_transaction_id, "confirmed": True},
    )
    assert missing_end.status_code == 422
    confirmed = await client.post(
        f"/api/v1/workspaces/{workspace_id}/budget-periods",
        json={
            "opening_transaction_id": opening_transaction_id,
            "end_date": (TODAY + timedelta(days=5)).isoformat(),
            "confirmed": True,
        },
    )
    assert confirmed.status_code == 201, confirmed.text


async def test_reserve_commitment_patch_fulfillment_and_close(client):
    context = await register(client)
    workspace_id = context["workspace"]["id"]
    main = await create_account(client, "Main USD", "USD", "1000")
    reserve = await create_account(
        client, "Reserve USD", "USD", "0", purpose="reserve", available=False
    )
    rule = (
        await create_rule(
            client,
            workspace_id,
            kind="reserve_transfer",
            name="Emergency reserve",
            amount="100",
            default_from_account_id=main["id"],
            default_to_account_id=reserve["id"],
            is_required=False,
        )
    ).json()
    occurrence = await occurrence_for_rule(client, workspace_id, rule["id"])
    created = await create_manual_period(client, workspace_id)
    commitment = created.json()["period"]["commitments"][0]
    patched = await client.patch(
        f"/api/v1/workspaces/{workspace_id}/budget-commitments/{commitment['id']}",
        json={"planned_amount": "110"},
    )
    assert patched.status_code == 200, patched.text
    assert D(patched.json()["period"]["daily_pool"]) == D("890")
    paid = await client.post(
        f"/api/v1/workspaces/{workspace_id}/plan-occurrences/{occurrence['id']}/pay",
        json={"amount": "120"},
    )
    assert paid.status_code == 200, paid.text
    summary = (
        await client.get(f"/api/v1/workspaces/{workspace_id}/tracker/today")
    ).json()
    assert D(summary["period"]["daily_pool"]) == D("880")
    assert D(summary["spent_total"]) == 0
    assert (
        await client.delete(
            f"/api/v1/workspaces/{workspace_id}/budget-commitments/{commitment['id']}"
        )
    ).status_code == 409
    closed = await client.post(
        f"/api/v1/workspaces/{workspace_id}/budget-periods/{summary['period']['id']}/close"
    )
    assert closed.status_code == 200
    assert closed.json()["period"]["status"] == "ended"
    assert (
        await client.get(f"/api/v1/workspaces/{workspace_id}/budget-periods/current")
    ).status_code == 404
