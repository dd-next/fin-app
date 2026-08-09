import ast
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.budget import compute_allowance, compute_budget
from app.ledger import account_balance
from app.models import Account, AccountPeriod, Transaction, TransactionLeg, Workspace
from app.periods import current_period_balance_inputs, period_movements
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


async def stored_snapshot(client, period_id):
    async with client._finapp_test_sessions() as session:
        period = await session.get(AccountPeriod, period_id)
        assert period is not None
        return (
            period.snapshot_at,
            period.opening_balance,
            period.closed_at,
            period.closing_balance,
        )


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


async def add_test_leg(client, account_id, amount, created_at, *, status="posted"):
    async with client._finapp_test_sessions() as session:
        account = await session.get(Account, account_id)
        assert account is not None
        transaction = Transaction(
            workspace_id=account.workspace_id,
            created_by_user_id=account.owner_user_id,
            type="adjustment",
            occurred_at=created_at,
            local_date=created_at.replace(tzinfo=UTC).astimezone(
                ZoneInfo("Asia/Ho_Chi_Minh")
            ).date(),
            origin="manual",
            status=status,
        )
        transaction.legs.append(
            TransactionLeg(
                account_id=account.id,
                asset_id=account.asset_id,
                amount=Decimal(amount),
                created_at=created_at,
            )
        )
        session.add(transaction)
        await session.commit()
        return transaction.id


async def test_snapshot_boundary_replay_correction_and_void(client):
    await register(client)
    account = await create_account(client, "Period USD", "USD", "900")
    period = await create_period(client, account["id"], "900")
    assert period["status"] == "current"
    assert period["remaining"] == "900.00"

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
    assert replayed["remaining"] == "875.00"

    corrected = await client.patch(
        f"/api/v1/transactions/{spent.json()['id']}", json={"amount": "40"}
    )
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["legs"][0]["created_at"] == leg_created_at
    replayed = (await client.get(f"/api/v1/account-periods/{period['id']}")).json()
    assert replayed["remaining"] == "860.00"

    voided = await client.post(
        f"/api/v1/transactions/{spent.json()['id']}/delete"
    )
    assert voided.status_code == 200, voided.text
    replayed = (await client.get(f"/api/v1/account-periods/{period['id']}")).json()
    assert replayed["remaining"] == "900.00"


async def test_runtime_snapshot_uses_non_utc_predecessor_boundary_once(client):
    await register(client)
    account = await create_account(client, "Runtime boundary USD", "USD", "200")
    today = local_today()
    predecessor = await create_period(
        client,
        account["id"],
        "999",
        today - timedelta(days=3),
        today - timedelta(days=2),
    )
    successor_start = today - timedelta(days=1)

    async with client._finapp_test_sessions() as session:
        workspace = await session.get(Workspace, account["workspace_id"])
        assert workspace is not None
        timezone = ZoneInfo(workspace.timezone)
        local_boundary = (
            datetime.combine(successor_start, datetime.min.time(), tzinfo=timezone)
            .astimezone(UTC)
            .replace(tzinfo=None)
        )
        selected_boundary = local_boundary + timedelta(hours=2)
        opening_leg = (
            await session.execute(
                select(TransactionLeg)
                .join(Transaction, Transaction.id == TransactionLeg.transaction_id)
                .where(TransactionLeg.account_id == account["id"])
                .order_by(TransactionLeg.id)
            )
        ).scalars().first()
        assert opening_leg is not None
        opening_leg.created_at = local_boundary - timedelta(hours=1)
        predecessor_row = await session.get(AccountPeriod, predecessor["id"])
        assert predecessor_row is not None
        predecessor_row.closed_at = selected_boundary
        predecessor_row.closing_balance = Decimal("150")
        await session.commit()

    await add_test_leg(client, account["id"], "-50", selected_boundary)
    await add_test_leg(
        client, account["id"], "999", selected_boundary, status="voided"
    )
    await add_test_leg(
        client, account["id"], "20", selected_boundary + timedelta(hours=1)
    )
    successor = await create_period(
        client,
        account["id"],
        "777",
        successor_start,
        today + timedelta(days=2),
    )

    assert successor["funding_amount"] == "150.00"
    async with client._finapp_test_sessions() as session:
        successor_row = await session.get(AccountPeriod, successor["id"])
        assert successor_row is not None
        assert successor_row.snapshot_at == selected_boundary
        assert successor_row.opening_balance == Decimal("150")
        assert await period_movements(
            session,
            successor_row,
            reference_time=selected_boundary + timedelta(hours=1),
        ) == [
            (successor_start, Decimal("20"))
        ]


async def test_current_balance_reconciliation_uses_one_exact_ledger_cutoff(
    client, monkeypatch
):
    await register(client)
    account = await create_account(client, "Reconcile precision BTC", "BTC", "0")
    today = local_today()
    period = await create_period(client, account["id"], "999", today, today)
    async with client._finapp_test_sessions() as session:
        period_row = await session.get(AccountPeriod, period["id"])
        assert period_row is not None
        snapshot_at = period_row.snapshot_at

    boundary_transaction_id = await add_test_leg(
        client,
        account["id"],
        "0.123456789012345678",
        snapshot_at,
    )
    await add_test_leg(client, account["id"], "-0.02", snapshot_at + timedelta(minutes=1))
    window_transaction_id = await add_test_leg(
        client, account["id"], "0.03", snapshot_at + timedelta(minutes=2)
    )
    await add_test_leg(
        client,
        account["id"],
        "999",
        snapshot_at + timedelta(minutes=2),
        status="voided",
    )
    await add_test_leg(client, account["id"], "1", snapshot_at + timedelta(minutes=3))
    reference_time = snapshot_at + timedelta(minutes=2)

    async with client._finapp_test_sessions() as session:
        period_row = await session.get(AccountPeriod, period["id"])
        assert period_row is not None
        values = await current_period_balance_inputs(
            session, period_row, reference_time=reference_time
        )
        assert values.current_balance == Decimal("0.133456789012345678")
        assert values.current_balance == await account_balance(
            session, account["id"], through=reference_time
        )
        assert values.window_net == Decimal("0.01")
        assert values.reconciliation_delta == Decimal("0.123456789012345678")
        assert values.calculation_opening_balance == Decimal(
            "0.123456789012345678"
        )
        assert (
            values.calculation_opening_balance + values.window_net
            == values.current_balance
        )

        captured_opening = []

        def capture_allowance(opening_balance, *args, **kwargs):
            captured_opening.append(opening_balance)
            return compute_allowance(opening_balance, *args, **kwargs)

        class FrozenDateTime(datetime):
            @classmethod
            def now(cls, timezone=None):
                aware = reference_time.replace(tzinfo=UTC)
                return aware if timezone is None else aware.astimezone(timezone)

        monkeypatch.setattr("app.periods.compute_allowance", capture_allowance)
        monkeypatch.setattr("app.periods.datetime", FrozenDateTime)
        response = await client.get(f"/api/v1/account-periods/{period['id']}")
        assert response.status_code == 200
        assert captured_opening == [Decimal("0.123456789012345678")]

        boundary_transaction = await session.get(Transaction, boundary_transaction_id)
        assert boundary_transaction is not None
        boundary_leg = (
            await session.execute(
                select(TransactionLeg).where(
                    TransactionLeg.transaction_id == boundary_transaction_id
                )
            )
        ).scalar_one()
        boundary_leg.amount = Decimal("0.223456789012345678")
        await session.commit()
        values = await current_period_balance_inputs(
            session, period_row, reference_time=reference_time
        )
        assert values.reconciliation_delta == Decimal("0.223456789012345678")
        assert (
            values.calculation_opening_balance + values.window_net
            == values.current_balance
        )

        boundary_transaction.status = "voided"
        window_transaction = await session.get(Transaction, window_transaction_id)
        assert window_transaction is not None
        window_transaction.status = "voided"
        await session.commit()
        values = await current_period_balance_inputs(
            session, period_row, reference_time=reference_time
        )
        assert values.current_balance == Decimal("-0.02")
        assert values.window_net == Decimal("-0.02")
        assert values.reconciliation_delta == Decimal("0")
        assert (
            values.calculation_opening_balance + values.window_net
            == values.current_balance
        )


async def test_manual_close_captures_exact_immutable_ledger_pair(client, monkeypatch):
    await register(client)
    account = await create_account(client, "Close snapshot USD", "USD", "100")
    period = await create_period(client, account["id"], "999")
    spent = await client.post(
        "/api/v1/operations/spend",
        json={"account_id": account["id"], "amount": "10"},
    )
    assert spent.status_code == 201, spent.text
    fixed = datetime.now(UTC).replace(tzinfo=None, microsecond=0) + timedelta(minutes=5)
    exact_transaction_id = await add_test_leg(client, account["id"], "5", fixed)
    await add_test_leg(client, account["id"], "999", fixed, status="voided")
    await add_test_leg(client, account["id"], "20", fixed + timedelta(hours=1))

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, timezone=None):
            aware = fixed.replace(tzinfo=UTC)
            return aware if timezone is None else aware.astimezone(timezone)

    monkeypatch.setattr("app.periods.datetime", FrozenDateTime)
    closed = await client.post(f"/api/v1/account-periods/{period['id']}/close")
    assert closed.status_code == 200, closed.text
    assert "available_today" not in closed.json()
    assert "current_balance" not in closed.json()

    async with client._finapp_test_sessions() as session:
        closed_row = await session.get(AccountPeriod, period["id"])
        assert closed_row is not None
        assert closed_row.closed_at == fixed
        assert closed_row.closing_balance == Decimal("95")
        exact_leg = (
            await session.execute(
                select(TransactionLeg).where(
                    TransactionLeg.transaction_id == exact_transaction_id
                )
            )
        ).scalar_one()
        exact_leg.amount = Decimal("500")
        await session.commit()
        await session.refresh(closed_row)
        assert closed_row.closed_at == fixed
        assert closed_row.closing_balance == Decimal("95")
    closed_again = await client.get(f"/api/v1/account-periods/{period['id']}")
    assert closed_again.status_code == 200
    assert closed_again.json()["remaining"] == "95.00"
    assert "available_today" not in closed_again.json()
    assert "current_balance" not in closed_again.json()


async def test_ended_period_uses_strict_end_boundary_without_live_reconciliation(client):
    await register(client)
    account = await create_account(client, "Ended cutoff USD", "USD", "0")
    today = local_today()
    period = await create_period(
        client,
        account["id"],
        "999",
        today - timedelta(days=4),
        today - timedelta(days=2),
    )
    async with client._finapp_test_sessions() as session:
        workspace = await session.get(Workspace, account["workspace_id"])
        period_row = await session.get(AccountPeriod, period["id"])
        assert workspace is not None
        assert period_row is not None
        end_boundary = (
            datetime.combine(
                period_row.end_date + timedelta(days=1),
                datetime.min.time(),
                tzinfo=ZoneInfo(workspace.timezone),
            )
            .astimezone(UTC)
            .replace(tzinfo=None)
        )
    await add_test_leg(client, account["id"], "-10", end_boundary - timedelta(seconds=1))
    await add_test_leg(client, account["id"], "100", end_boundary)
    await add_test_leg(client, account["id"], "1000", end_boundary + timedelta(seconds=1))

    response = await client.get(f"/api/v1/account-periods/{period['id']}")
    assert response.status_code == 200
    assert response.json()["status"] == "ended"
    assert response.json()["remaining"] is None
    assert "available_today" not in response.json()
    assert "current_balance" not in response.json()
    async with client._finapp_test_sessions() as session:
        period_row = await session.get(AccountPeriod, period["id"])
        assert period_row is not None
        assert await period_movements(
            session,
            period_row,
            reference_time=end_boundary,
            include_reference_time=False,
        ) == [(period_row.end_date, Decimal("-10"))]


async def test_same_account_current_rejected_cross_account_current_allowed(client):
    await register(client)
    first = await create_account(client, "First period USD", "USD")
    second = await create_account(client, "Second period USD", "USD")
    today = local_today()
    start, end = today - timedelta(days=3), today + timedelta(days=3)
    await create_period(client, first["id"], "100", start, end)

    overlap = await client.post(
        f"/api/v1/accounts/{first['id']}/periods",
        json={
            "start_date": today.isoformat(),
            "end_date": (end + timedelta(days=2)).isoformat(),
            "funding_amount": "100",
        },
    )
    assert overlap.status_code == 409
    assert overlap.json()["detail"] == "Account already has a current period"
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
    assert source_out["remaining"] == "875.00"
    assert target_out["remaining"] == "225.00"


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
    assert usd_out["remaining"] == "910.00"
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
    assert usd_out["remaining"] == "1015.00"
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
    assert current_items[0]["planned"] == "0.00"
    assert current_items[0]["remaining"] == "-7.00"


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
    assert current_patch.status_code == 422
    assert current_patch.json()["detail"] == "Funding amount is not editable"

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
    assert rejected.status_code == 422
    assert rejected.json()["detail"] == "Funding amount is not editable"
    confirmed = await client.patch(
        f"/api/v1/account-periods/{ended['id']}",
        json={"funding_amount": "60", "confirm_ended_period": True},
    )
    assert confirmed.status_code == 422
    assert confirmed.json()["detail"] == "Funding amount is not editable"

    overlap = await client.patch(
        f"/api/v1/account-periods/{ended['id']}",
        json={
            "end_date": today.isoformat(),
            "confirm_ended_period": True,
        },
    )
    assert overlap.status_code == 409

    upcoming = await client.post(
        f"/api/v1/accounts/{account['id']}/periods",
        json={
            "start_date": (today + timedelta(days=5)).isoformat(),
            "end_date": (today + timedelta(days=8)).isoformat(),
            "funding_amount": "70",
        },
    )
    assert upcoming.status_code == 422
    assert "future" in upcoming.json()["detail"].lower()

    closed = await client.post(f"/api/v1/account-periods/{current['id']}/close")
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "closed"
    assert (
        await client.patch(
            f"/api/v1/account-periods/{current['id']}",
            json={"funding_amount": "130", "confirm_ended_period": True},
        )
    ).status_code == 422
    assert (
        await client.post(f"/api/v1/account-periods/{current['id']}/close")
    ).status_code == 409


async def test_ended_transaction_confirmation_and_closed_snapshot_edits(client):
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
    ended_out = (
        await client.get(f"/api/v1/account-periods/{ended['id']}")
    ).json()
    assert ended_out["remaining"] is None
    assert "available_today" not in ended_out
    assert "current_balance" not in ended_out

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
    ).json()["remaining"] is None
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
    ).json()["remaining"] is None

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
    corrected_closed = await client.patch(
        f"/api/v1/transactions/{closed_transaction_id}", json={"amount": "20"}
    )
    assert corrected_closed.status_code == 200, corrected_closed.text
    deleted_closed = await client.post(
        f"/api/v1/transactions/{closed_transaction_id}/delete"
    )
    assert deleted_closed.status_code == 200, deleted_closed.text
    later_closed = await client.post(
        "/api/v1/operations/spend",
        json={"account_id": account["id"], "amount": "5"},
    )
    assert later_closed.status_code == 201, later_closed.text


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
        await client.get(f"/api/v1/accounts/{account['id']}/periods/current")
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
    assert hidden_guard.status_code == 201, hidden_guard.text

    await login(client, "alice")
    owner_period = await client.get(f"/api/v1/account-periods/{period['id']}")
    assert owner_period.status_code == 200
    assert owner_period.json()["status"] == "closed"

    await register(client, "charlie")
    foreign_period_routes = (
        ("get", f"/api/v1/accounts/{account['id']}/periods", None),
        ("get", f"/api/v1/accounts/{account['id']}/periods/current", None),
        (
            "post",
            f"/api/v1/accounts/{account['id']}/periods",
            {"end_date": local_today().isoformat()},
        ),
        ("get", f"/api/v1/account-periods/{period['id']}", None),
        (
            "patch",
            f"/api/v1/account-periods/{period['id']}",
            {"end_date": local_today().isoformat()},
        ),
        ("post", f"/api/v1/account-periods/{period['id']}/close", None),
    )
    for method, route, body in foreign_period_routes:
        response = await client.request(method, route, json=body)
        assert response.status_code == 404, (method, route, response.text)


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
    resulting_ended = await client.patch(
        f"/api/v1/account-periods/{state_period['id']}", json=moved_to_ended
    )
    assert resulting_ended.status_code == 200, resulting_ended.text
    assert resulting_ended.json()["status"] == "ended"
    ended_state = (
        await client.get(f"/api/v1/account-periods/{state_period['id']}")
    ).json()
    assert ended_state["start_date"] == moved_to_ended["start_date"]
    assert ended_state["end_date"] == moved_to_ended["end_date"]
    assert ended_state["closed_at"] is None
    confirmed = await client.patch(
        f"/api/v1/account-periods/{state_period['id']}",
        json={**moved_to_ended, "confirm_ended_period": True},
    )
    assert confirmed.status_code == 409
    assert confirmed.json()["detail"] == "Ended account period is read-only"
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
    ).status_code == 409

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
    closed_snapshot = await stored_snapshot(client, closed_period["id"])
    outside = await client.post(
        "/api/v1/operations/spend",
        json={"account_id": plain_account["id"], "amount": "3"},
    )
    assert outside.status_code == 201
    moved_into_closed = await client.patch(
        f"/api/v1/transactions/{outside.json()['id']}",
        json={"account_id": closed_account["id"]},
    )
    assert moved_into_closed.status_code == 200, moved_into_closed.text
    assert moved_into_closed.json()["legs"][0]["account_id"] == closed_account["id"]
    assert await stored_snapshot(client, closed_period["id"]) == closed_snapshot
    moved_out_of_closed = await client.patch(
        f"/api/v1/transactions/{inside_closed.json()['id']}",
        json={"account_id": plain_account["id"]},
    )
    assert moved_out_of_closed.status_code == 200, moved_out_of_closed.text
    moved = (
        await client.get(f"/api/v1/transactions/{inside_closed.json()['id']}")
    ).json()
    assert moved["legs"][0]["account_id"] == plain_account["id"]
    assert await stored_snapshot(client, closed_period["id"]) == closed_snapshot


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
    current_snapshot = await stored_snapshot(client, current_period["id"])
    closed_unassigned_id = await seed_unassigned_transaction(client, amount="3")
    closed_assign = await client.post(
        f"/api/v1/transactions/{closed_unassigned_id}/assign-account",
        json={"account_id": current_account["id"]},
    )
    assert closed_assign.status_code == 200, closed_assign.text
    closed_assignment_state = (
        await client.get(f"/api/v1/transactions/{closed_unassigned_id}")
    ).json()
    assert closed_assignment_state["status"] == "posted"
    assert closed_assignment_state["legs"][0]["account_id"] == current_account["id"]
    assert await stored_snapshot(client, current_period["id"]) == current_snapshot
    reconcile = await client.post(
        f"/api/v1/accounts/{current_account['id']}/reconcile",
        json={"target_balance": "80"},
    )
    assert reconcile.status_code == 200, reconcile.text
    assert Decimal(
        (
            await client.get(f"/api/v1/accounts/{current_account['id']}")
        ).json()["balance"]
    ) == Decimal("80")
    assert await stored_snapshot(client, current_period["id"]) == current_snapshot

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
    ended_close = await client.post(f"/api/v1/account-periods/{ended['id']}/close")
    assert ended_close.status_code == 409
    confirmed_ended_void = await client.post(
        f"/api/v1/transactions/{second_exchange.json()['id']}/delete",
        json={"confirm_ended_period": True},
    )
    assert confirmed_ended_void.status_code == 200, confirmed_ended_void.text
    assert (
        await client.get(f"/api/v1/transactions/{second_exchange.json()['id']}")
    ).json()["status"] == "deleted"
    balance_before_closed_create = Decimal(
        (await client.get(f"/api/v1/accounts/{source['id']}")).json()["balance"]
    )
    closed_exchange = await client.post(
        "/api/v1/operations/exchange",
        json={**exchange_body, "confirm_ended_period": True},
    )
    assert closed_exchange.status_code == 201, closed_exchange.text
    assert Decimal(
        (await client.get(f"/api/v1/accounts/{source['id']}")).json()["balance"]
    ) < balance_before_closed_create


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
    ended_close = await client.post(f"/api/v1/account-periods/{period['id']}/close")
    assert ended_close.status_code == 409
    successor = await create_period(client, fee_account["id"], "100", today, today)
    assert (
        await client.post(f"/api/v1/account-periods/{successor['id']}/close")
    ).status_code == 200
    closed_snapshot = await stored_snapshot(client, successor["id"])
    await login(client, "bob")
    closed_exchange = await client.post(
        "/api/v1/operations/exchange",
        json={**exchange_body, "local_date": today.isoformat()},
    )
    assert closed_exchange.status_code == 201, closed_exchange.text
    assert await stored_snapshot(client, successor["id"]) == closed_snapshot
