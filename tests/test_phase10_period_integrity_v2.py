"""Phase 10 regressions for immutable and explicitly confirmed period history."""

from datetime import date, timedelta
from decimal import Decimal

from tests.conftest import register
from tests.test_ledger_v2 import create_account
from tests.test_plan_v2 import create_rule
from tests.test_sharing_v2 import accept, invitation, login
from tests.test_tracker_v2 import create_manual_period, occurrence_for_rule


TODAY = date.today()
HISTORICAL_START = TODAY - timedelta(days=20)
HISTORICAL_END = HISTORICAL_START + timedelta(days=4)


async def create_historical_period(client, workspace_id: int):
    response = await create_manual_period(
        client,
        workspace_id,
        start=HISTORICAL_START,
        end=HISTORICAL_END,
        funding="500",
    )
    assert response.status_code == 201, response.text
    return response.json()["period"]


async def test_owner_historical_post_requires_confirmation_and_closed_post_is_rejected(
    client,
):
    context = await register(client)
    workspace_id = context["workspace"]["id"]
    account = await create_account(client, "Period USD", "USD", "1000")
    historical = await create_historical_period(client, workspace_id)
    no_op_period_patch = await client.patch(
        f"/api/v1/workspaces/{workspace_id}/budget-periods/{historical['id']}",
        json={},
    )
    assert no_op_period_patch.status_code == 200, no_op_period_patch.text

    unconfirmed = await client.post(
        "/api/v1/transactions/expense",
        json={
            "account_id": account["id"],
            "amount": "10",
            "local_date": HISTORICAL_START.isoformat(),
        },
    )
    assert unconfirmed.status_code == 409, unconfirmed.text

    confirmed = await client.post(
        "/api/v1/transactions/expense",
        json={
            "account_id": account["id"],
            "amount": "10",
            "local_date": HISTORICAL_START.isoformat(),
            "confirm_ended_period": True,
        },
    )
    assert confirmed.status_code == 201, confirmed.text
    assert confirmed.json()["budget_period_id"] == historical["id"]

    current = await create_manual_period(client, workspace_id)
    assert current.status_code == 201, current.text
    current_period = current.json()["period"]
    closed = await client.post(
        f"/api/v1/workspaces/{workspace_id}/budget-periods/"
        f"{current_period['id']}/close"
    )
    assert closed.status_code == 200, closed.text

    for confirmed_flag in (False, True):
        response = await client.post(
            "/api/v1/transactions/expense",
            json={
                "account_id": account["id"],
                "amount": "5",
                "local_date": TODAY.isoformat(),
                "confirm_ended_period": confirmed_flag,
            },
        )
        assert response.status_code == 409, response.text
    account_after_rejections = await client.get(
        f"/api/v1/accounts/{account['id']}"
    )
    assert account_after_rejections.status_code == 200
    assert Decimal(account_after_rejections.json()["balance"]) == Decimal("990")


async def test_contributor_historical_post_requires_confirmation_without_elevating_rights(
    client,
):
    alice = await register(client)
    workspace_id = alice["workspace"]["id"]
    shared = await create_account(client, "Shared historical USD", "USD", "1000")
    shared_btc = await create_account(client, "Shared historical BTC", "BTC", "1")
    historical = await create_historical_period(client, workspace_id)
    token = await invitation(client, shared["id"], "contributor")
    btc_token = await invitation(client, shared_btc["id"], "contributor")

    await register(client, "bob")
    await accept(client, token)
    await accept(client, btc_token)
    body = {
        "account_id": shared["id"],
        "amount": "15",
        "local_date": HISTORICAL_START.isoformat(),
        "note": "contributor backdate",
    }
    unconfirmed = await client.post("/api/v1/transactions/expense", json=body)
    assert unconfirmed.status_code == 409, unconfirmed.text
    assert unconfirmed.json()["detail"] == (
        "Historical transaction requires explicit confirmation"
    )
    outside_body = {
        **body,
        "local_date": (HISTORICAL_START - timedelta(days=5)).isoformat(),
        "note": "outside private history",
    }
    outside_unconfirmed = await client.post(
        "/api/v1/transactions/expense",
        json=outside_body,
    )
    assert outside_unconfirmed.status_code == unconfirmed.status_code
    assert outside_unconfirmed.json()["detail"] == unconfirmed.json()["detail"]
    outside_confirmed = await client.post(
        "/api/v1/transactions/expense",
        json={**outside_body, "confirm_ended_period": True},
    )
    assert outside_confirmed.status_code == 201, outside_confirmed.text
    assert outside_confirmed.json()["budget_period_id"] is None
    confirmed = await client.post(
        "/api/v1/transactions/expense",
        json={**body, "confirm_ended_period": True},
    )
    assert confirmed.status_code == 201, confirmed.text
    assert confirmed.json()["budget_period_id"] is None
    assert confirmed.json()["base_amount"] is None
    cross_asset = await client.post(
        "/api/v1/transactions/expense",
        json={
            "account_id": shared_btc["id"],
            "amount": "0.01",
            "local_date": HISTORICAL_START.isoformat(),
            "confirm_ended_period": True,
        },
    )
    assert cross_asset.status_code == 201, cross_asset.text
    assert cross_asset.json()["budget_period_id"] is None
    assert cross_asset.json()["base_amount"] is None

    await login(client, "alice")
    owner_view = await client.get(f"/api/v1/transactions/{confirmed.json()['id']}")
    assert owner_view.status_code == 200, owner_view.text
    assert owner_view.json()["budget_period_id"] is None
    assert owner_view.json()["base_amount"] is None
    cross_asset_owner = await client.get(
        f"/api/v1/transactions/{cross_asset.json()['id']}"
    )
    assert cross_asset_owner.status_code == 200
    assert cross_asset_owner.json()["budget_period_id"] is None
    assert cross_asset_owner.json()["base_amount"] is None
    outside_owner_view = await client.get(
        f"/api/v1/transactions/{outside_confirmed.json()['id']}"
    )
    assert outside_owner_view.status_code == 200
    assert outside_owner_view.json()["budget_period_id"] is None

    current = await create_manual_period(client, workspace_id)
    assert current.status_code == 201, current.text
    current_period = current.json()["period"]
    assert (
        await client.post(
            f"/api/v1/workspaces/{workspace_id}/budget-periods/"
            f"{current_period['id']}/close"
        )
    ).status_code == 200
    await login(client, "bob")
    closed_date_shared = await client.post(
        "/api/v1/transactions/expense",
        json={"account_id": shared["id"], "amount": "5"},
    )
    assert closed_date_shared.status_code == 201, closed_date_shared.text
    assert closed_date_shared.json()["budget_period_id"] is None
    await login(client, "alice")
    closed_date_owner = await client.get(
        f"/api/v1/transactions/{closed_date_shared.json()['id']}"
    )
    assert closed_date_owner.status_code == 200
    assert closed_date_owner.json()["budget_period_id"] is None


async def test_patch_into_ended_destination_requires_confirmation(client):
    context = await register(client)
    workspace_id = context["workspace"]["id"]
    account = await create_account(client, "Move USD", "USD", "1000")
    historical = await create_historical_period(client, workspace_id)
    current = await create_manual_period(client, workspace_id)
    assert current.status_code == 201, current.text
    current_period = current.json()["period"]

    current_expense = await client.post(
        "/api/v1/transactions/expense",
        json={"account_id": account["id"], "amount": "20"},
    )
    assert current_expense.status_code == 201, current_expense.text
    assert current_expense.json()["budget_period_id"] == current_period["id"]

    outside_expense = await client.post(
        "/api/v1/transactions/expense",
        json={
            "account_id": account["id"],
            "amount": "30",
            "local_date": (TODAY + timedelta(days=30)).isoformat(),
        },
    )
    assert outside_expense.status_code == 201, outside_expense.text
    assert outside_expense.json()["budget_period_id"] is None

    for transaction in (current_expense.json(), outside_expense.json()):
        route = f"/api/v1/transactions/{transaction['id']}"
        unconfirmed = await client.patch(
            route,
            json={"local_date": HISTORICAL_START.isoformat()},
        )
        assert unconfirmed.status_code == 409, unconfirmed.text
        unchanged = await client.get(route)
        assert unchanged.status_code == 200, unchanged.text
        assert unchanged.json()["local_date"] == transaction["local_date"]

        confirmed = await client.patch(
            route,
            json={
                "local_date": HISTORICAL_START.isoformat(),
                "confirm_ended_period": True,
            },
        )
        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json()["budget_period_id"] == historical["id"]

    moved_out_without_confirmation = await client.patch(
        f"/api/v1/transactions/{current_expense.json()['id']}",
        json={"local_date": TODAY.isoformat()},
    )
    assert moved_out_without_confirmation.status_code == 409
    moved_out = await client.patch(
        f"/api/v1/transactions/{current_expense.json()['id']}",
        json={
            "local_date": TODAY.isoformat(),
            "confirm_ended_period": True,
        },
    )
    assert moved_out.status_code == 200, moved_out.text
    assert moved_out.json()["budget_period_id"] == current_period["id"]


async def test_ended_source_correction_and_void_still_require_confirmation(client):
    context = await register(client)
    workspace_id = context["workspace"]["id"]
    account = await create_account(client, "Corrections USD", "USD", "1000")
    await create_historical_period(client, workspace_id)
    created = await client.post(
        "/api/v1/transactions/expense",
        json={
            "account_id": account["id"],
            "amount": "25",
            "local_date": HISTORICAL_START.isoformat(),
            "confirm_ended_period": True,
        },
    )
    assert created.status_code == 201, created.text
    route = f"/api/v1/transactions/{created.json()['id']}"

    no_op = await client.patch(route, json={})
    assert no_op.status_code == 200, no_op.text
    same_amount = await client.patch(route, json={"amount": "25"})
    assert same_amount.status_code == 200, same_amount.text

    correction = await client.patch(route, json={"note": "historical correction"})
    assert correction.status_code == 409, correction.text
    confirmed_correction = await client.patch(
        route,
        json={"note": "historical correction", "confirm_ended_period": True},
    )
    assert confirmed_correction.status_code == 200, confirmed_correction.text

    voided = await client.post(f"{route}/void")
    assert voided.status_code == 409, voided.text
    confirmed_void = await client.post(
        f"{route}/void",
        json={"confirm_ended_period": True},
    )
    assert confirmed_void.status_code == 200, confirmed_void.text


async def test_exchange_void_checks_ended_child_fee_period(client):
    context = await register(client)
    workspace_id = context["workspace"]["id"]
    usd = await create_account(client, "Fee source USD", "USD", "1000")
    btc = await create_account(client, "Fee target BTC", "BTC", "0")
    await create_historical_period(client, workspace_id)
    exchange = await client.post(
        "/api/v1/transactions/exchange",
        json={
            "from_account_id": usd["id"],
            "from_amount": "100",
            "to_account_id": btc["id"],
            "to_amount": "0.01",
            "local_date": HISTORICAL_START.isoformat(),
            "confirm_ended_period": True,
            "fee": {"account_id": usd["id"], "amount": "5"},
        },
    )
    assert exchange.status_code == 201, exchange.text
    route = f"/api/v1/transactions/{exchange.json()['id']}/void"

    unconfirmed = await client.post(route)
    assert unconfirmed.status_code == 409, unconfirmed.text
    usd_after_rejection = await client.get(f"/api/v1/accounts/{usd['id']}")
    assert Decimal(usd_after_rejection.json()["balance"]) == Decimal("895")

    confirmed = await client.post(
        route,
        json={"confirm_ended_period": True},
    )
    assert confirmed.status_code == 200, confirmed.text
    usd_after_void = await client.get(f"/api/v1/accounts/{usd['id']}")
    btc_after_void = await client.get(f"/api/v1/accounts/{btc['id']}")
    assert Decimal(usd_after_void.json()["balance"]) == Decimal("1000")
    assert Decimal(btc_after_void.json()["balance"]) == Decimal("0")


async def test_ended_commitment_mutations_require_confirmation_and_closed_rejects_create(
    client,
):
    context = await register(client)
    workspace_id = context["workspace"]["id"]
    account = await create_account(client, "Commitment guard USD", "USD", "1000")
    historical = await create_historical_period(client, workspace_id)
    historical_rule = (
        await create_rule(
            client,
            workspace_id,
            name="Historical manual commitment",
            amount="60",
            first_due_date=HISTORICAL_START.isoformat(),
            default_from_account_id=account["id"],
        )
    ).json()
    historical_occurrence = await occurrence_for_rule(
        client, workspace_id, historical_rule["id"]
    )
    create_route = (
        f"/api/v1/workspaces/{workspace_id}/budget-periods/"
        f"{historical['id']}/commitments"
    )
    unconfirmed_create = await client.post(
        create_route,
        json={"plan_occurrence_id": historical_occurrence["id"]},
    )
    assert unconfirmed_create.status_code == 409, unconfirmed_create.text
    confirmed_create = await client.post(
        create_route,
        json={
            "plan_occurrence_id": historical_occurrence["id"],
            "confirm_ended_period": True,
        },
    )
    assert confirmed_create.status_code == 201, confirmed_create.text
    commitment = next(
        item
        for item in confirmed_create.json()["period"]["commitments"]
        if item["plan_occurrence_id"] == historical_occurrence["id"]
    )
    commitment_route = (
        f"/api/v1/workspaces/{workspace_id}/budget-commitments/"
        f"{commitment['id']}"
    )
    unconfirmed_patch = await client.patch(
        commitment_route,
        json={"name": "Corrected historical commitment"},
    )
    assert unconfirmed_patch.status_code == 409, unconfirmed_patch.text
    confirmed_patch = await client.patch(
        commitment_route,
        json={
            "name": "Corrected historical commitment",
            "confirm_ended_period": True,
        },
    )
    assert confirmed_patch.status_code == 200, confirmed_patch.text
    assert next(
        item
        for item in confirmed_patch.json()["period"]["commitments"]
        if item["id"] == commitment["id"]
    )["name"] == "Corrected historical commitment"

    unconfirmed_cancel = await client.delete(commitment_route)
    assert unconfirmed_cancel.status_code == 409, unconfirmed_cancel.text
    confirmed_cancel = await client.request(
        "DELETE",
        commitment_route,
        json={"confirm_ended_period": True},
    )
    assert confirmed_cancel.status_code == 200, confirmed_cancel.text
    assert next(
        item
        for item in confirmed_cancel.json()["period"]["commitments"]
        if item["id"] == commitment["id"]
    )["status"] == "cancelled"

    current = await create_manual_period(client, workspace_id)
    assert current.status_code == 201, current.text
    current_period = current.json()["period"]
    assert (
        await client.post(
            f"/api/v1/workspaces/{workspace_id}/budget-periods/"
            f"{current_period['id']}/close"
        )
    ).status_code == 200
    closed_rule = (
        await create_rule(
            client,
            workspace_id,
            name="Closed new commitment",
            amount="70",
            first_due_date=TODAY.isoformat(),
            default_from_account_id=account["id"],
        )
    ).json()
    closed_occurrence = await occurrence_for_rule(
        client, workspace_id, closed_rule["id"]
    )
    closed_create = await client.post(
        f"/api/v1/workspaces/{workspace_id}/budget-periods/"
        f"{current_period['id']}/commitments",
        json={
            "plan_occurrence_id": closed_occurrence["id"],
            "confirm_ended_period": True,
        },
    )
    assert closed_create.status_code == 409, closed_create.text


async def test_plan_execution_cannot_create_transaction_in_closed_commitment_period(
    client,
):
    context = await register(client)
    workspace_id = context["workspace"]["id"]
    account = await create_account(client, "Plan closed USD", "USD", "1000")
    rule = (
        await create_rule(
            client,
            workspace_id,
            name="Closed-period bill",
            amount="50",
            first_due_date=TODAY.isoformat(),
            default_from_account_id=account["id"],
        )
    ).json()
    occurrence = await occurrence_for_rule(client, workspace_id, rule["id"])
    created = await create_manual_period(client, workspace_id)
    assert created.status_code == 201, created.text
    period = created.json()["period"]
    assert any(
        item["plan_occurrence_id"] == occurrence["id"]
        for item in period["commitments"]
    )
    closed = await client.post(
        f"/api/v1/workspaces/{workspace_id}/budget-periods/{period['id']}/close"
    )
    assert closed.status_code == 200, closed.text

    executed = await client.post(
        f"/api/v1/workspaces/{workspace_id}/plan-occurrences/"
        f"{occurrence['id']}/pay",
        json={"local_date": TODAY.isoformat(), "confirm_ended_period": True},
    )
    assert executed.status_code == 409, executed.text
    refreshed = await occurrence_for_rule(client, workspace_id, rule["id"])
    assert refreshed["status"] in {"planned", "overdue"}
    assert refreshed["transaction_id"] is None


async def test_closed_period_plan_link_requires_confirmation(client):
    context = await register(client)
    workspace_id = context["workspace"]["id"]
    account = await create_account(client, "Plan history USD", "USD", "1000")
    rule = (
        await create_rule(
            client,
            workspace_id,
            name="Closed-period linked bill",
            amount="40",
            first_due_date=TODAY.isoformat(),
            default_from_account_id=account["id"],
        )
    ).json()
    occurrence = await occurrence_for_rule(client, workspace_id, rule["id"])
    created = await create_manual_period(client, workspace_id)
    assert created.status_code == 201, created.text
    period = created.json()["period"]
    expense = await client.post(
        "/api/v1/transactions/expense",
        json={
            "account_id": account["id"],
            "amount": "45",
            "local_date": TODAY.isoformat(),
        },
    )
    assert expense.status_code == 201, expense.text
    closed = await client.post(
        f"/api/v1/workspaces/{workspace_id}/budget-periods/{period['id']}/close"
    )
    assert closed.status_code == 200, closed.text
    outside = await client.post(
        "/api/v1/transactions/expense",
        json={
            "account_id": account["id"],
            "amount": "5",
            "local_date": (TODAY + timedelta(days=30)).isoformat(),
        },
    )
    assert outside.status_code == 201, outside.text
    route = (
        f"/api/v1/workspaces/{workspace_id}/plan-occurrences/"
        f"{occurrence['id']}/link-transaction"
    )
    outside_period = await client.post(
        route,
        json={
            "transaction_id": outside.json()["id"],
            "confirm_ended_period": True,
        },
    )
    assert outside_period.status_code == 422, outside_period.text
    assert "outside the linked budget period" in outside_period.json()["detail"]
    unconfirmed = await client.post(
        route,
        json={"transaction_id": expense.json()["id"]},
    )
    assert unconfirmed.status_code == 409, unconfirmed.text
    confirmed = await client.post(
        route,
        json={
            "transaction_id": expense.json()["id"],
            "confirm_ended_period": True,
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["transaction_id"] == expense.json()["id"]


async def test_period_date_patch_rejects_orphaned_linked_transaction(client):
    context = await register(client)
    workspace_id = context["workspace"]["id"]
    account = await create_account(client, "Range transaction USD", "USD", "1000")
    period_response = await create_manual_period(client, workspace_id)
    assert period_response.status_code == 201, period_response.text
    period = period_response.json()["period"]
    transaction_date = TODAY + timedelta(days=8)
    expense = await client.post(
        "/api/v1/transactions/expense",
        json={
            "account_id": account["id"],
            "amount": "20",
            "local_date": transaction_date.isoformat(),
        },
    )
    assert expense.status_code == 201, expense.text
    assert expense.json()["budget_period_id"] == period["id"]

    patched = await client.patch(
        f"/api/v1/workspaces/{workspace_id}/budget-periods/{period['id']}",
        json={"end_date": (transaction_date - timedelta(days=1)).isoformat()},
    )
    assert patched.status_code == 409, patched.text
    unchanged = await client.get(
        f"/api/v1/workspaces/{workspace_id}/budget-periods/{period['id']}"
    )
    assert unchanged.status_code == 200, unchanged.text
    assert unchanged.json()["period"]["end_date"] == period["end_date"]

    original_commitment_ids = {
        item["id"] for item in unchanged.json()["period"]["commitments"]
    }
    expanded = await client.patch(
        f"/api/v1/workspaces/{workspace_id}/budget-periods/{period['id']}",
        json={
            "end_date": (
                date.fromisoformat(period["end_date"]) + timedelta(days=5)
            ).isoformat()
        },
    )
    assert expanded.status_code == 200, expanded.text
    assert {
        item["id"] for item in expanded.json()["period"]["commitments"]
    } == original_commitment_ids


async def test_period_date_patch_rejects_orphaned_commitment_due_date(client):
    context = await register(client)
    workspace_id = context["workspace"]["id"]
    account = await create_account(client, "Range commitment USD", "USD", "1000")
    due_date = TODAY + timedelta(days=8)
    rule = (
        await create_rule(
            client,
            workspace_id,
            name="Late-period commitment",
            amount="75",
            first_due_date=due_date.isoformat(),
            default_from_account_id=account["id"],
        )
    ).json()
    occurrence = await occurrence_for_rule(client, workspace_id, rule["id"])
    period_response = await create_manual_period(client, workspace_id)
    assert period_response.status_code == 201, period_response.text
    period = period_response.json()["period"]
    assert any(
        item["plan_occurrence_id"] == occurrence["id"]
        for item in period["commitments"]
    )

    patched = await client.patch(
        f"/api/v1/workspaces/{workspace_id}/budget-periods/{period['id']}",
        json={"end_date": (due_date - timedelta(days=1)).isoformat()},
    )
    assert patched.status_code == 409, patched.text
    unchanged = await client.get(
        f"/api/v1/workspaces/{workspace_id}/budget-periods/{period['id']}"
    )
    assert unchanged.status_code == 200, unchanged.text
    assert unchanged.json()["period"]["end_date"] == period["end_date"]
