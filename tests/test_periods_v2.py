import ast
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from app.budget import compute_budget
from tests.conftest import register, seed_unassigned_transaction
from tests.test_ledger_v2 import create_account
from tests.test_sharing_v2 import accept, invitation, login


def local_today():
    return datetime.now(UTC).astimezone(ZoneInfo("Asia/Ho_Chi_Minh")).date()


async def create_period(client, account_id, funding, start=None, end=None):
    today = local_today()
    response = await client.post(
        f"/api/v1/accounts/{account_id}/periods",
        json={
            "start_date": (start or today - timedelta(days=2)).isoformat(),
            "end_date": (end or today + timedelta(days=2)).isoformat(),
            "funding_amount": funding,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def create_plan_rule(
    client,
    workspace_id,
    *,
    name,
    amount,
    due_date,
    from_account_id=None,
    to_account_id=None,
    kind="required_expense",
):
    response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/plan-rules",
        json={
            "kind": kind,
            "name": name,
            "amount": amount,
            "asset_code": "USD",
            "recurrence": "once",
            "first_due_date": due_date.isoformat(),
            "default_from_account_id": from_account_id,
            "default_to_account_id": to_account_id,
            "is_required": kind == "required_expense",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_snapshot_boundary_replay_correction_and_void(client):
    await register(client)
    account = await create_account(client, "Period USD", "USD", "900")
    period = await create_period(client, account["id"], "900")
    assert period["status"] == "current"
    assert period["remaining"] == "900"

    spent = await client.post(
        "/api/v1/operations/spend",
        json={
            "account_id": account["id"],
            "amount": "25",
            "local_date": local_today().isoformat(),
        },
    )
    assert spent.status_code == 201, spent.text
    leg_created_at = spent.json()["legs"][0]["created_at"]
    replayed = (await client.get(f"/api/v1/account-periods/{period['id']}")).json()
    assert replayed["remaining"] == "875"

    corrected = await client.patch(
        f"/api/v1/transactions/{spent.json()['id']}", json={"amount": "40"}
    )
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["legs"][0]["created_at"] == leg_created_at
    replayed = (await client.get(f"/api/v1/account-periods/{period['id']}")).json()
    assert replayed["remaining"] == "860"

    voided = await client.post(
        f"/api/v1/transactions/{spent.json()['id']}/delete"
    )
    assert voided.status_code == 200, voided.text
    replayed = (await client.get(f"/api/v1/account-periods/{period['id']}")).json()
    assert replayed["remaining"] == "900"


async def test_same_account_overlap_rejected_cross_account_overlap_allowed(client):
    await register(client)
    first = await create_account(client, "First period USD", "USD")
    second = await create_account(client, "Second period USD", "USD")
    today = local_today()
    start, end = today - timedelta(days=3), today + timedelta(days=3)
    await create_period(client, first["id"], "100", start, end)

    overlap = await client.post(
        f"/api/v1/accounts/{first['id']}/periods",
        json={
            "start_date": end.isoformat(),
            "end_date": (end + timedelta(days=2)).isoformat(),
            "funding_amount": "100",
        },
    )
    assert overlap.status_code == 409
    assert "overlap" in overlap.json()["detail"].lower()
    await create_period(client, second["id"], "50", start, end)


async def test_transfer_replays_signed_legs_in_both_account_periods(client):
    await register(client)
    source = await create_account(client, "Period source USD", "USD", "1000")
    target = await create_account(client, "Period target USD", "USD", "100")
    source_period = await create_period(client, source["id"], "1000")
    target_period = await create_period(client, target["id"], "100")

    transfer = await client.post(
        "/api/v1/operations/transfer",
        json={
            "from_account_id": source["id"],
            "to_account_id": target["id"],
            "amount": "125",
            "local_date": local_today().isoformat(),
        },
    )
    assert transfer.status_code == 201, transfer.text
    source_out = (
        await client.get(f"/api/v1/account-periods/{source_period['id']}")
    ).json()
    target_out = (
        await client.get(f"/api/v1/account-periods/{target_period['id']}")
    ).json()
    assert source_out["remaining"] == "875"
    assert target_out["remaining"] == "225"


async def test_income_adjustments_exchange_fee_and_root_void_replay(client):
    await register(client)
    usd = await create_account(client, "Replay USD", "USD", "1000")
    vnd = await create_account(client, "Replay VND", "VND", "10000")
    usd_period = await create_period(client, usd["id"], "1000")
    vnd_period = await create_period(client, vnd["id"], "10000")
    today = local_today().isoformat()

    exchange = await client.post(
        "/api/v1/operations/exchange",
        json={
            "from_account_id": usd["id"],
            "from_amount": "100",
            "to_account_id": vnd["id"],
            "to_amount": "2500000",
            "local_date": today,
            "fee": {"account_id": usd["id"], "amount": "5"},
        },
    )
    assert exchange.status_code == 201, exchange.text
    income = await client.post(
        "/api/v1/operations/add-funds",
        json={"account_id": usd["id"], "amount": "20", "local_date": today},
    )
    assert income.status_code == 201, income.text
    positive = await client.post(
        f"/api/v1/accounts/{usd['id']}/reconcile",
        json={"target_balance": "925"},
    )
    assert positive.status_code == 200, positive.text
    negative = await client.post(
        f"/api/v1/accounts/{usd['id']}/reconcile",
        json={"target_balance": "910"},
    )
    assert negative.status_code == 200, negative.text

    usd_out = (
        await client.get(f"/api/v1/account-periods/{usd_period['id']}")
    ).json()
    vnd_out = (
        await client.get(f"/api/v1/account-periods/{vnd_period['id']}")
    ).json()
    assert usd_out["remaining"] == "910"
    assert vnd_out["remaining"] == "2510000"

    voided = await client.post(
        f"/api/v1/transactions/{exchange.json()['id']}/delete"
    )
    assert voided.status_code == 200, voided.text
    usd_out = (
        await client.get(f"/api/v1/account-periods/{usd_period['id']}")
    ).json()
    vnd_out = (
        await client.get(f"/api/v1/account-periods/{vnd_period['id']}")
    ).json()
    assert usd_out["remaining"] == "1015"
    assert vnd_out["remaining"] == "10000"


async def test_current_history_and_planned_is_informational(client):
    context = await register(client)
    workspace_id = context["workspace"]["id"]
    account = await create_account(client, "Planned period USD", "USD")
    other_account = await create_account(client, "Other planned USD", "USD")
    today = local_today()
    past = await create_period(
        client,
        account["id"],
        "80",
        today - timedelta(days=10),
        today - timedelta(days=5),
    )
    current = await create_period(
        client, account["id"], "100", today - timedelta(days=2), today + timedelta(days=2)
    )
    overdue_rule = await create_plan_rule(
        client,
        workspace_id,
        name="Source in range",
        amount="30",
        due_date=today - timedelta(days=1),
        from_account_id=account["id"],
    )
    planned_rule = await create_plan_rule(
        client,
        workspace_id,
        name="Target in range",
        amount="40",
        due_date=today,
        to_account_id=account["id"],
        kind="income",
    )
    await create_plan_rule(
        client,
        workspace_id,
        name="Other account",
        amount="50",
        due_date=today,
        from_account_id=other_account["id"],
    )
    await create_plan_rule(
        client,
        workspace_id,
        name="Out of range",
        amount="60",
        due_date=today + timedelta(days=5),
        from_account_id=account["id"],
    )
    skipped_rule = await create_plan_rule(
        client,
        workspace_id,
        name="Skipped in range",
        amount="71",
        due_date=today,
        from_account_id=account["id"],
    )
    completed_rule = await create_plan_rule(
        client,
        workspace_id,
        name="Completed in range",
        amount="7",
        due_date=today,
        from_account_id=account["id"],
    )
    occurrences = (
        await client.get(f"/api/v1/workspaces/{workspace_id}/plan-occurrences")
    ).json()
    by_rule = {item["plan_rule_id"]: item for item in occurrences}
    assert by_rule[overdue_rule["id"]]["status"] == "overdue"
    assert by_rule[planned_rule["id"]]["status"] == "planned"
    assert by_rule[skipped_rule["id"]]["status"] == "planned"
    skipped = await client.post(
        f"/api/v1/workspaces/{workspace_id}/plan-occurrences/"
        f"{by_rule[skipped_rule['id']]['id']}/skip"
    )
    assert skipped.status_code == 200, skipped.text
    paid = await client.post(
        "/api/v1/operations/spend",
        json={"account_id": account["id"], "amount": "7"},
    )
    assert paid.status_code == 201, paid.text
    completed = await client.post(
        f"/api/v1/workspaces/{workspace_id}/plan-occurrences/"
        f"{by_rule[completed_rule['id']]['id']}/link-transaction",
        json={"transaction_id": paid.json()["id"]},
    )
    assert completed.status_code == 200, completed.text

    current_items = (
        await client.get(f"/api/v1/accounts/{account['id']}/periods?scope=current")
    ).json()
    history_items = (
        await client.get(f"/api/v1/accounts/{account['id']}/periods?scope=history")
    ).json()
    assert [item["id"] for item in current_items] == [current["id"]]
    assert [item["id"] for item in history_items] == [past["id"]]
    assert current_items[0]["planned"] == "70"
    assert current_items[0]["remaining"] == "93"


def test_budget_replay_is_pure_and_preserves_full_decimal_precision():
    tree = ast.parse(Path("app/budget.py").read_text())
    imported_roots = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_roots.update(
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )
    assert not imported_roots.intersection({"app", "fastapi", "sqlalchemy"})

    today = local_today()
    result = compute_budget(
        Decimal("99999999999999999999.123456789012345678"),
        today,
        today,
        [(today, Decimal("0.000000000000000001"))],
        today=today,
        quantum=Decimal("0.000000000000000001"),
    )
    assert result.remaining_money == Decimal(
        "99999999999999999999.123456789012345677"
    )


async def test_period_lifecycle_confirmation_overlap_and_closed_guards(client):
    await register(client)
    account = await create_account(client, "Lifecycle USD", "USD")
    today = local_today()
    current = await create_period(
        client, account["id"], "100", today - timedelta(days=1), today + timedelta(days=2)
    )
    current_patch = await client.patch(
        f"/api/v1/account-periods/{current['id']}",
        json={"funding_amount": "120"},
    )
    assert current_patch.status_code == 200, current_patch.text
    assert current_patch.json()["funding_amount"] == "120"

    immutable = await client.patch(
        f"/api/v1/account-periods/{current['id']}",
        json={"account_id": account["id"], "asset_id": current["asset"]["id"]},
    )
    assert immutable.status_code == 422

    ended = await create_period(
        client,
        account["id"],
        "50",
        today - timedelta(days=10),
        today - timedelta(days=5),
    )
    rejected = await client.patch(
        f"/api/v1/account-periods/{ended['id']}",
        json={"funding_amount": "60"},
    )
    assert rejected.status_code == 409
    assert "confirmation" in rejected.json()["detail"].lower()
    confirmed = await client.patch(
        f"/api/v1/account-periods/{ended['id']}",
        json={"funding_amount": "60", "confirm_ended_period": True},
    )
    assert confirmed.status_code == 200, confirmed.text

    overlap = await client.patch(
        f"/api/v1/account-periods/{ended['id']}",
        json={
            "end_date": today.isoformat(),
            "confirm_ended_period": True,
        },
    )
    assert overlap.status_code == 409

    upcoming = await create_period(
        client,
        account["id"],
        "70",
        today + timedelta(days=5),
        today + timedelta(days=8),
    )
    upcoming_patch = await client.patch(
        f"/api/v1/account-periods/{upcoming['id']}",
        json={"funding_amount": "75"},
    )
    assert upcoming_patch.status_code == 200, upcoming_patch.text

    closed = await client.post(f"/api/v1/account-periods/{current['id']}/close")
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "closed"
    assert (
        await client.patch(
            f"/api/v1/account-periods/{current['id']}",
            json={"funding_amount": "130", "confirm_ended_period": True},
        )
    ).status_code == 409
    assert (
        await client.post(f"/api/v1/account-periods/{current['id']}/close")
    ).status_code == 409


async def test_ended_transaction_confirmation_and_closed_record_rejection(client):
    await register(client)
    account = await create_account(client, "Guarded USD", "USD")
    today = local_today()
    ended = await create_period(
        client,
        account["id"],
        "100",
        today - timedelta(days=10),
        today - timedelta(days=5),
    )
    historical_date = (today - timedelta(days=7)).isoformat()
    rejected_create = await client.post(
        "/api/v1/operations/spend",
        json={
            "account_id": account["id"],
            "amount": "10",
            "local_date": historical_date,
        },
    )
    assert rejected_create.status_code == 409
    posted = await client.post(
        "/api/v1/operations/spend",
        json={
            "account_id": account["id"],
            "amount": "10",
            "local_date": historical_date,
            "confirm_ended_period": True,
        },
    )
    assert posted.status_code == 201, posted.text
    transaction_id = posted.json()["id"]
    assert (
        await client.get(f"/api/v1/account-periods/{ended['id']}")
    ).json()["remaining"] == "90"

    rejected_patch = await client.patch(
        f"/api/v1/transactions/{transaction_id}", json={"amount": "20"}
    )
    assert rejected_patch.status_code == 409
    confirmed_patch = await client.patch(
        f"/api/v1/transactions/{transaction_id}",
        json={"amount": "20", "confirm_ended_period": True},
    )
    assert confirmed_patch.status_code == 200, confirmed_patch.text
    assert (
        await client.get(f"/api/v1/account-periods/{ended['id']}")
    ).json()["remaining"] == "80"
    assert (
        await client.post(f"/api/v1/transactions/{transaction_id}/delete")
    ).status_code == 409
    confirmed_void = await client.post(
        f"/api/v1/transactions/{transaction_id}/delete",
        json={"confirm_ended_period": True},
    )
    assert confirmed_void.status_code == 200, confirmed_void.text
    assert (
        await client.get(f"/api/v1/account-periods/{ended['id']}")
    ).json()["remaining"] == "100"

    current = await create_period(
        client, account["id"], "100", today - timedelta(days=1), today + timedelta(days=1)
    )
    current_expense = await client.post(
        "/api/v1/operations/spend",
        json={"account_id": account["id"], "amount": "10"},
    )
    assert current_expense.status_code == 201, current_expense.text
    assert (
        await client.post(f"/api/v1/account-periods/{current['id']}/close")
    ).status_code == 200
    closed_transaction_id = current_expense.json()["id"]
    assert (
        await client.patch(
            f"/api/v1/transactions/{closed_transaction_id}",
            json={"amount": "20", "confirm_ended_period": True},
        )
    ).status_code == 409
    assert (
        await client.post(
            f"/api/v1/transactions/{closed_transaction_id}/delete",
            json={"confirm_ended_period": True},
        )
    ).status_code == 409
    assert (
        await client.post(
            "/api/v1/operations/spend",
            json={
                "account_id": account["id"],
                "amount": "5",
                "confirm_ended_period": True,
            },
        )
    ).status_code == 409


async def test_shared_users_cannot_discover_owner_private_periods(client):
    await register(client)
    account = await create_account(client, "Private period USD", "USD")
    period = await create_period(client, account["id"], "100")
    assert (
        await client.post(f"/api/v1/account-periods/{period['id']}/close")
    ).status_code == 200
    token = await invitation(client, account["id"], "editor")

    await register(client, "bob")
    await accept(client, token)
    assert (
        await client.get(f"/api/v1/accounts/{account['id']}/periods")
    ).status_code == 404
    assert (
        await client.post(
            f"/api/v1/accounts/{account['id']}/periods",
            json={
                "start_date": local_today().isoformat(),
                "end_date": local_today().isoformat(),
                "funding_amount": "1",
            },
        )
    ).status_code == 404
    assert (
        await client.get(f"/api/v1/account-periods/{period['id']}")
    ).status_code == 404
    assert (
        await client.patch(
            f"/api/v1/account-periods/{period['id']}",
            json={"funding_amount": "1", "confirm_ended_period": True},
        )
    ).status_code == 404
    assert (
        await client.post(f"/api/v1/account-periods/{period['id']}/close")
    ).status_code == 404
    hidden_guard = await client.post(
        "/api/v1/operations/spend",
        json={
            "account_id": account["id"],
            "amount": "1",
            "confirm_ended_period": True,
        },
    )
    assert hidden_guard.status_code == 409
    assert hidden_guard.json()["detail"] == "Transaction cannot be changed"

    await login(client, "alice")
    owner_period = await client.get(f"/api/v1/account-periods/{period['id']}")
    assert owner_period.status_code == 200
    assert owner_period.json()["status"] == "closed"


async def test_resulting_period_state_and_moved_leg_membership_are_guarded(client):
    await register(client)
    today = local_today()
    state_account = await create_account(client, "State guard USD", "USD")
    state_period = await create_period(
        client,
        state_account["id"],
        "100",
        today - timedelta(days=1),
        today + timedelta(days=1),
    )
    moved_to_ended = {
        "start_date": (today - timedelta(days=4)).isoformat(),
        "end_date": (today - timedelta(days=2)).isoformat(),
    }
    rejected = await client.patch(
        f"/api/v1/account-periods/{state_period['id']}", json=moved_to_ended
    )
    assert rejected.status_code == 409
    unchanged = (
        await client.get(f"/api/v1/account-periods/{state_period['id']}")
    ).json()
    assert unchanged["end_date"] == (today + timedelta(days=1)).isoformat()
    confirmed = await client.patch(
        f"/api/v1/account-periods/{state_period['id']}",
        json={**moved_to_ended, "confirm_ended_period": True},
    )
    assert confirmed.status_code == 200, confirmed.text
    moved_to_future = {
        "start_date": (today + timedelta(days=3)).isoformat(),
        "end_date": (today + timedelta(days=5)).isoformat(),
    }
    assert (
        await client.patch(
            f"/api/v1/account-periods/{state_period['id']}", json=moved_to_future
        )
    ).status_code == 409
    assert (
        await client.patch(
            f"/api/v1/account-periods/{state_period['id']}",
            json={**moved_to_future, "confirm_ended_period": True},
        )
    ).status_code == 200

    ended_account = await create_account(client, "Move ended USD", "USD")
    plain_account = await create_account(client, "Move plain USD", "USD")
    await create_period(
        client,
        ended_account["id"],
        "100",
        today - timedelta(days=10),
        today - timedelta(days=5),
    )
    historical = (today - timedelta(days=7)).isoformat()
    transaction = await client.post(
        "/api/v1/operations/spend",
        json={"account_id": plain_account["id"], "amount": "10", "local_date": historical},
    )
    assert transaction.status_code == 201, transaction.text
    transaction_id = transaction.json()["id"]
    assert (
        await client.patch(
            f"/api/v1/transactions/{transaction_id}",
            json={"account_id": ended_account["id"]},
        )
    ).status_code == 409
    unchanged = (await client.get(f"/api/v1/transactions/{transaction_id}")).json()
    assert unchanged["legs"][0]["account_id"] == plain_account["id"]
    assert (
        await client.patch(
            f"/api/v1/transactions/{transaction_id}",
            json={"account_id": ended_account["id"], "confirm_ended_period": True},
        )
    ).status_code == 200
    assert (
        await client.patch(
            f"/api/v1/transactions/{transaction_id}",
            json={"account_id": plain_account["id"]},
        )
    ).status_code == 409
    still_ended = (await client.get(f"/api/v1/transactions/{transaction_id}")).json()
    assert still_ended["legs"][0]["account_id"] == ended_account["id"]
    assert (
        await client.patch(
            f"/api/v1/transactions/{transaction_id}",
            json={"account_id": plain_account["id"], "confirm_ended_period": True},
        )
    ).status_code == 200

    closed_account = await create_account(client, "Move closed USD", "USD")
    closed_period = await create_period(client, closed_account["id"], "100")
    inside_closed = await client.post(
        "/api/v1/operations/spend",
        json={"account_id": closed_account["id"], "amount": "10"},
    )
    assert inside_closed.status_code == 201
    assert (
        await client.post(f"/api/v1/account-periods/{closed_period['id']}/close")
    ).status_code == 200
    outside = await client.post(
        "/api/v1/operations/spend",
        json={"account_id": plain_account["id"], "amount": "3"},
    )
    assert outside.status_code == 201
    assert (
        await client.patch(
            f"/api/v1/transactions/{outside.json()['id']}",
            json={"account_id": closed_account["id"], "confirm_ended_period": True},
        )
    ).status_code == 409
    assert (
        await client.get(f"/api/v1/transactions/{outside.json()['id']}")
    ).json()["legs"][0]["account_id"] == plain_account["id"]
    assert (
        await client.patch(
            f"/api/v1/transactions/{inside_closed.json()['id']}",
            json={"account_id": plain_account["id"], "confirm_ended_period": True},
        )
    ).status_code == 409
    still_closed = (
        await client.get(f"/api/v1/transactions/{inside_closed.json()['id']}")
    ).json()
    assert still_closed["legs"][0]["account_id"] == closed_account["id"]


async def test_assign_reconcile_and_fee_only_exchange_guards_roll_back(client):
    await register(client)
    today = local_today()
    guarded = await create_account(client, "Assign guarded USD", "USD", "100")
    ended = await create_period(
        client,
        guarded["id"],
        "100",
        today - timedelta(days=10),
        today - timedelta(days=5),
    )
    historical = (today - timedelta(days=7)).isoformat()
    unassigned_id = await seed_unassigned_transaction(
        client, amount="5", local_date=today - timedelta(days=7)
    )
    rejected_assign = await client.post(
        f"/api/v1/transactions/{unassigned_id}/assign-account",
        json={"account_id": guarded["id"]},
    )
    assert rejected_assign.status_code == 409
    unchanged = (await client.get(f"/api/v1/transactions/{unassigned_id}")).json()
    assert unchanged["status"] == "unassigned"
    assert unchanged["legs"][0]["account_id"] is None
    confirmed_assign = await client.post(
        f"/api/v1/transactions/{unassigned_id}/assign-account",
        json={"account_id": guarded["id"], "confirm_ended_period": True},
    )
    assert confirmed_assign.status_code == 200, confirmed_assign.text

    current_account = await create_account(client, "Reconcile closed USD", "USD", "100")
    current_period = await create_period(client, current_account["id"], "100")
    assert (
        await client.post(f"/api/v1/account-periods/{current_period['id']}/close")
    ).status_code == 200
    closed_unassigned_id = await seed_unassigned_transaction(client, amount="3")
    rejected_closed_assign = await client.post(
        f"/api/v1/transactions/{closed_unassigned_id}/assign-account",
        json={"account_id": current_account["id"], "confirm_ended_period": True},
    )
    assert rejected_closed_assign.status_code == 409
    closed_assignment_state = (
        await client.get(f"/api/v1/transactions/{closed_unassigned_id}")
    ).json()
    assert closed_assignment_state["status"] == "unassigned"
    assert closed_assignment_state["legs"][0]["account_id"] is None
    reconcile = await client.post(
        f"/api/v1/accounts/{current_account['id']}/reconcile",
        json={"target_balance": "80"},
    )
    assert reconcile.status_code == 409
    assert Decimal(
        (
            await client.get(f"/api/v1/accounts/{current_account['id']}")
        ).json()["balance"]
    ) == Decimal("100")

    source = await create_account(client, "Fee root USD", "USD", "1000")
    target = await create_account(client, "Fee root VND", "VND", "0")
    exchange_body = {
        "from_account_id": source["id"],
        "from_amount": "10",
        "to_account_id": target["id"],
        "to_amount": "250000",
        "local_date": historical,
        "fee": {"account_id": guarded["id"], "amount": "2"},
    }
    rejected_exchange = await client.post(
        "/api/v1/operations/exchange", json=exchange_body
    )
    assert rejected_exchange.status_code == 409
    assert Decimal(
        (await client.get(f"/api/v1/accounts/{source['id']}")).json()["balance"]
    ) == Decimal("1000")
    exchange = await client.post(
        "/api/v1/operations/exchange",
        json={**exchange_body, "confirm_ended_period": True},
    )
    assert exchange.status_code == 201, exchange.text
    exchange_id = exchange.json()["id"]
    assert (
        await client.post(f"/api/v1/transactions/{exchange_id}/delete")
    ).status_code == 409
    assert (await client.get(f"/api/v1/transactions/{exchange_id}")).json()["status"] == "posted"
    assert (
        await client.post(
            f"/api/v1/transactions/{exchange_id}/delete",
            json={"confirm_ended_period": True},
        )
    ).status_code == 200
    second_exchange = await client.post(
        "/api/v1/operations/exchange",
        json={**exchange_body, "confirm_ended_period": True},
    )
    assert second_exchange.status_code == 201, second_exchange.text
    assert (
        await client.post(f"/api/v1/account-periods/{ended['id']}/close")
    ).status_code == 200
    rejected_closed_void = await client.post(
        f"/api/v1/transactions/{second_exchange.json()['id']}/delete",
        json={"confirm_ended_period": True},
    )
    assert rejected_closed_void.status_code == 409
    assert (
        await client.get(f"/api/v1/transactions/{second_exchange.json()['id']}")
    ).json()["status"] == "posted"
    balance_before_closed_create = Decimal(
        (await client.get(f"/api/v1/accounts/{source['id']}")).json()["balance"]
    )
    closed_exchange = await client.post(
        "/api/v1/operations/exchange",
        json={**exchange_body, "confirm_ended_period": True},
    )
    assert closed_exchange.status_code == 409
    assert Decimal(
        (await client.get(f"/api/v1/accounts/{source['id']}")).json()["balance"]
    ) == balance_before_closed_create


async def test_shared_ended_and_hidden_fee_guards_are_generic(client):
    await register(client)
    today = local_today()
    fee_account = await create_account(client, "Shared fee USD", "USD", "100")
    source = await create_account(client, "Shared root USD", "USD", "1000")
    target = await create_account(client, "Shared root VND", "VND", "0")
    unshared = await create_account(client, "Unshared target USD", "USD", "0")
    unshared_vnd = await create_account(client, "Unshared target VND", "VND", "0")
    period = await create_period(
        client,
        fee_account["id"],
        "100",
        today - timedelta(days=10),
        today - timedelta(days=5),
    )
    historical = (today - timedelta(days=7)).isoformat()
    hidden_unassigned_id = await seed_unassigned_transaction(
        client, amount="4", local_date=today - timedelta(days=7)
    )
    tokens = [
        await invitation(client, account["id"], "editor")
        for account in (fee_account, source, target)
    ]

    await register(client, "bob")
    for token in tokens:
        await accept(client, token)
    generic = "Transaction change requires explicit confirmation"
    rejected_create = await client.post(
        "/api/v1/operations/spend",
        json={"account_id": fee_account["id"], "amount": "5", "local_date": historical},
    )
    assert rejected_create.status_code == 409
    assert rejected_create.json()["detail"] == generic
    shared_transaction = await client.post(
        "/api/v1/operations/spend",
        json={
            "account_id": fee_account["id"],
            "amount": "5",
            "local_date": historical,
            "confirm_ended_period": True,
        },
    )
    assert shared_transaction.status_code == 201, shared_transaction.text
    transaction_id = shared_transaction.json()["id"]
    rejected_patch = await client.patch(
        f"/api/v1/transactions/{transaction_id}", json={"amount": "6"}
    )
    assert rejected_patch.status_code == 409
    assert rejected_patch.json()["detail"] == generic
    assert (
        await client.patch(
            f"/api/v1/transactions/{transaction_id}",
            json={"amount": "6", "confirm_ended_period": True},
        )
    ).status_code == 200
    rejected_void = await client.post(f"/api/v1/transactions/{transaction_id}/delete")
    assert rejected_void.status_code == 409
    assert rejected_void.json()["detail"] == generic
    assert (
        await client.post(
            f"/api/v1/transactions/{transaction_id}/delete",
            json={"confirm_ended_period": True},
        )
    ).status_code == 200
    assert (
        await client.post(
            f"/api/v1/transactions/{hidden_unassigned_id}/assign-account",
            json={"account_id": fee_account["id"], "confirm_ended_period": True},
        )
    ).status_code == 404

    exchange_body = {
        "from_account_id": source["id"],
        "from_amount": "10",
        "to_account_id": target["id"],
        "to_amount": "250000",
        "local_date": historical,
        "fee": {"account_id": fee_account["id"], "amount": "2"},
    }
    rejected_exchange = await client.post(
        "/api/v1/operations/exchange", json=exchange_body
    )
    assert rejected_exchange.status_code == 409
    assert rejected_exchange.json()["detail"] == generic
    assert (
        await client.post(
            "/api/v1/operations/transfer",
            json={
                "from_account_id": source["id"],
                "to_account_id": unshared["id"],
                "amount": "1",
                "confirm_ended_period": True,
            },
        )
    ).status_code == 404
    assert (
        await client.post(
            "/api/v1/operations/exchange",
            json={
                "from_account_id": source["id"],
                "from_amount": "1",
                "to_account_id": unshared_vnd["id"],
                "to_amount": "25000",
                "confirm_ended_period": True,
            },
        )
    ).status_code == 404

    await login(client, "alice")
    assert (
        await client.post(f"/api/v1/account-periods/{period['id']}/close")
    ).status_code == 200
    await login(client, "bob")
    closed_exchange = await client.post(
        "/api/v1/operations/exchange",
        json={**exchange_body, "confirm_ended_period": True},
    )
    assert closed_exchange.status_code == 409
    assert closed_exchange.json()["detail"] == "Transaction cannot be changed"
