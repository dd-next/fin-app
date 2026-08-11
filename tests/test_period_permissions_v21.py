from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select

from app.models import (
    Account,
    AccountPeriod,
    ExchangeRate,
    OperationsUndoState,
    Transaction,
    TransactionLeg,
    User,
    utcnow,
)
from tests.conftest import register, seed_unassigned_transaction
from tests.test_ledger_v2 import create_account
from tests.test_operations_undo_v2 import candidate
from tests.test_periods_v2 import create_period, local_today, stored_snapshot
from tests.test_sharing_v2 import accept, invitation, login


GENERIC_SHARED_CONFIRMATION = (
    "Shared transaction correction requires explicit confirmation"
)


async def period_rows(client):
    async with client._finapp_test_sessions() as session:
        periods = list(
            (
                await session.execute(
                    select(AccountPeriod).order_by(AccountPeriod.id)
                )
            ).scalars()
        )
        return [
            (
                period.id,
                period.account_id,
                period.start_date,
                period.end_date,
                period.snapshot_at,
                period.opening_balance,
                period.closed_at,
                period.closing_balance,
                period.rollover_policy,
            )
            for period in periods
        ]


async def financial_fingerprint(client):
    periods = await period_rows(client)
    async with client._finapp_test_sessions() as session:
        transactions = list(
            (await session.execute(select(Transaction).order_by(Transaction.id))).scalars()
        )
        legs = list(
            (
                await session.execute(
                    select(TransactionLeg).order_by(TransactionLeg.id)
                )
            ).scalars()
        )
        rates = list(
            (
                await session.execute(select(ExchangeRate).order_by(ExchangeRate.id))
            ).scalars()
        )
        undo_states = list(
            (
                await session.execute(
                    select(OperationsUndoState).order_by(OperationsUndoState.id)
                )
            ).scalars()
        )
        return {
            "transactions": [
                (
                    row.id,
                    row.workspace_id,
                    row.created_by_user_id,
                    row.type,
                    row.parent_transaction_id,
                    row.note,
                    row.local_date,
                    row.status,
                    row.voided_at,
                )
                for row in transactions
            ],
            "legs": [
                (
                    row.id,
                    row.transaction_id,
                    row.account_id,
                    row.asset_id,
                    row.amount,
                )
                for row in legs
            ],
            "rates": [
                (
                    row.id,
                    row.workspace_id,
                    row.source_transaction_id,
                    row.base_asset_id,
                    row.quote_asset_id,
                    row.rate,
                    row.captured_at,
                )
                for row in rates
            ],
            "undo": [
                (
                    row.id,
                    row.user_id,
                    row.account_id,
                    row.cursor_transaction_id,
                    row.created_at,
                    row.updated_at,
                    row.consumed_at,
                )
                for row in undo_states
            ],
            "periods": periods,
        }


async def seed_shared_workspace_unassigned(
    client, *, username, account_id, transaction_type, local_date
):
    async with client._finapp_test_sessions() as session:
        user = (
            await session.execute(select(User).where(User.username == username))
        ).scalar_one()
        account = await session.get(Account, account_id)
        assert account is not None
        now = utcnow()
        transaction = Transaction(
            workspace_id=account.workspace_id,
            created_by_user_id=user.id,
            type=transaction_type,
            occurred_at=now,
            local_date=local_date,
            origin="manual",
            status="unassigned",
        )
        transaction.legs.append(
            TransactionLeg(
                account_id=None,
                asset_id=account.asset_id,
                amount=(
                    Decimal("-4")
                    if transaction_type == "expense"
                    else Decimal("4")
                ),
            )
        )
        session.add(transaction)
        await session.commit()
        await session.refresh(transaction)
        return transaction.id


async def test_every_period_route_and_filter_are_owner_private_for_shared_roles(client):
    await register(client)
    today = local_today()
    ended_account = await create_account(client, "Private ended USD", "USD", "100")
    current_account = await create_account(client, "Private current USD", "USD", "100")
    closed_account = await create_account(client, "Private closed USD", "USD", "100")
    ended = await create_period(
        client,
        ended_account["id"],
        today - timedelta(days=10),
        today - timedelta(days=5),
    )
    current = await create_period(
        client,
        current_account["id"],
        today - timedelta(days=1),
        today + timedelta(days=1),
    )
    closed = await create_period(
        client,
        closed_account["id"],
        today - timedelta(days=1),
        today + timedelta(days=1),
    )
    closed_response = await client.post(
        f"/api/v1/account-periods/{closed['id']}/close"
    )
    assert closed_response.status_code == 200, closed_response.text

    accounts = (ended_account, current_account, closed_account)
    periods = (ended, current, closed)
    invitations = {
        username: [
            await invitation(client, account["id"], role) for account in accounts
        ]
        for username, role in (
            ("period-editor", "editor"),
            ("period-contributor", "contributor"),
            ("period-viewer", "viewer"),
        )
    }
    before = await period_rows(client)

    for username in (*invitations, "period-foreign"):
        await register(client, username)
        for token in invitations.get(username, []):
            await accept(client, token)

        for account in accounts:
            account_id = account["id"]
            for query in ("", "?scope=all", "?scope=current", "?scope=history"):
                response = await client.get(
                    f"/api/v1/accounts/{account_id}/periods{query}"
                )
                assert response.status_code == 404
                assert response.json() == {"detail": "Account not found"}
            current_response = await client.get(
                f"/api/v1/accounts/{account_id}/periods/current"
            )
            assert current_response.status_code == 404
            assert current_response.json() == {"detail": "Account not found"}
            create_response = await client.post(
                f"/api/v1/accounts/{account_id}/periods",
                json={
                    "start_date": today.isoformat(),
                    "end_date": today.isoformat(),
                },
            )
            assert create_response.status_code == 404
            assert create_response.json() == {"detail": "Account not found"}

        for period_id in [*(period["id"] for period in periods), 999_999_999]:
            detail = await client.get(f"/api/v1/account-periods/{period_id}")
            patch = await client.patch(
                f"/api/v1/account-periods/{period_id}",
                json={"end_date": today.isoformat()},
            )
            close = await client.post(
                f"/api/v1/account-periods/{period_id}/close"
            )
            for response in (detail, patch, close):
                assert response.status_code == 404
                assert response.json() == {
                    "detail": "Account period not found"
                }

        matching_account_id = ended_account["id"]
        mismatching_account_id = current_account["id"]
        filter_routes = [
            f"/api/v1/transactions?period_id={ended['id']}",
            (
                f"/api/v1/transactions?period_id={ended['id']}"
                f"&account_id={matching_account_id}"
            ),
            (
                f"/api/v1/transactions?period_id={ended['id']}"
                f"&account_id={mismatching_account_id}"
            ),
            "/api/v1/transactions?period_id=999999999",
        ]
        for route in filter_routes:
            response = await client.get(route)
            assert response.status_code == 404
            assert response.json() == {"detail": "Account period not found"}

    await login(client, "alice")
    assert await period_rows(client) == before


async def test_shared_mutations_have_one_period_neutral_confirmation_contract(client):
    await register(client)
    today = local_today()
    accounts = {
        "absent": await create_account(client, "Shared absent USD", "USD", "100"),
        "current": await create_account(client, "Shared current USD", "USD", "100"),
        "ended": await create_account(client, "Shared ended USD", "USD", "100"),
        "closed": await create_account(client, "Shared closed USD", "USD", "100"),
    }
    transfer_target = await create_account(
        client, "Shared transfer target USD", "USD", "0"
    )
    exchange_target = await create_account(
        client, "Shared exchange target VND", "VND", "0"
    )
    fee_account = await create_account(client, "Shared exchange fee USD", "USD", "20")
    dates = {
        "absent": today,
        "current": today,
        "ended": today - timedelta(days=7),
        "closed": today,
    }
    await create_period(
        client,
        accounts["current"]["id"],
        today - timedelta(days=1),
        today + timedelta(days=1),
    )
    await create_period(
        client,
        accounts["ended"]["id"],
        today - timedelta(days=10),
        today - timedelta(days=5),
    )
    closed_period = await create_period(
        client,
        accounts["closed"]["id"],
        today - timedelta(days=1),
        today + timedelta(days=1),
    )
    close = await client.post(
        f"/api/v1/account-periods/{closed_period['id']}/close"
    )
    assert close.status_code == 200, close.text
    closed_snapshot = await stored_snapshot(client, closed_period["id"])
    before_periods = await period_rows(client)

    editor_tokens = [
        await invitation(client, account["id"], "editor")
        for account in (*accounts.values(), transfer_target, exchange_target, fee_account)
    ]
    contributor_tokens = [
        await invitation(client, account["id"], "contributor")
        for account in accounts.values()
    ]
    viewer_token = await invitation(client, accounts["ended"]["id"], "viewer")

    await register(client, "period-editor")
    for token in editor_tokens:
        await accept(client, token)

    response_key_sets = {kind: [] for kind in ("spend", "income", "transfer", "exchange")}
    for state, account in accounts.items():
        body = {
            "account_id": account["id"],
            "amount": "2",
            "local_date": dates[state].isoformat(),
        }
        created = await client.post("/api/v1/operations/spend", json=body)
        assert created.status_code == 201, (state, created.text)
        response_key_sets["spend"].append(set(created.json()))
        income = await client.post(
            "/api/v1/operations/add-funds",
            json={
                "account_id": account["id"],
                "amount": "1",
                "local_date": dates[state].isoformat(),
            },
        )
        assert income.status_code == 201, (state, income.text)
        response_key_sets["income"].append(set(income.json()))
        transfer = await client.post(
            "/api/v1/operations/transfer",
            json={
                "from_account_id": account["id"],
                "to_account_id": transfer_target["id"],
                "amount": "1",
                "local_date": dates[state].isoformat(),
            },
        )
        assert transfer.status_code == 201, (state, transfer.text)
        response_key_sets["transfer"].append(set(transfer.json()))
        assert {leg["amount"] for leg in transfer.json()["legs"]} == {"-1", "1"}
        exchange = await client.post(
            "/api/v1/operations/exchange",
            json={
                "from_account_id": account["id"],
                "from_amount": "1",
                "to_account_id": exchange_target["id"],
                "to_amount": "25000",
                "local_date": dates[state].isoformat(),
                "fee": {"account_id": fee_account["id"], "amount": "0.25"},
            },
        )
        assert exchange.status_code == 201, (state, exchange.text)
        response_key_sets["exchange"].append(set(exchange.json()))
        transaction_id = created.json()["id"]

        before_rejected_patch = await financial_fingerprint(client)
        unconfirmed_patch = await client.patch(
            f"/api/v1/transactions/{transaction_id}", json={"amount": "3"}
        )
        assert unconfirmed_patch.status_code == 409
        assert unconfirmed_patch.json() == {
            "detail": GENERIC_SHARED_CONFIRMATION
        }
        assert await financial_fingerprint(client) == before_rejected_patch
        unchanged = await client.get(f"/api/v1/transactions/{transaction_id}")
        assert unchanged.status_code == 200
        assert unchanged.json()["legs"][0]["amount"] == "-2"
        confirmed_patch = await client.patch(
            f"/api/v1/transactions/{transaction_id}",
            json={"amount": "3", "confirm_ended_period": True},
        )
        assert confirmed_patch.status_code == 200, (state, confirmed_patch.text)

        before_rejected_delete = await financial_fingerprint(client)
        unconfirmed_delete = await client.post(
            f"/api/v1/transactions/{transaction_id}/delete"
        )
        assert unconfirmed_delete.status_code == 409
        assert unconfirmed_delete.json() == {
            "detail": GENERIC_SHARED_CONFIRMATION
        }
        assert await financial_fingerprint(client) == before_rejected_delete
        confirmed_delete = await client.post(
            f"/api/v1/transactions/{transaction_id}/delete",
            json={"confirm_ended_period": True},
        )
        assert confirmed_delete.status_code == 200, (state, confirmed_delete.text)

        undo_source = await client.post("/api/v1/operations/spend", json=body)
        assert undo_source.status_code == 201, (state, undo_source.text)
        undo_id = undo_source.json()["id"]
        before_rejected_undo = await financial_fingerprint(client)
        unconfirmed_undo = await client.post(
            f"/api/v1/operations/accounts/{account['id']}/undo",
            json={"transaction_id": undo_id},
        )
        assert unconfirmed_undo.status_code == 409
        assert unconfirmed_undo.json() == {
            "detail": GENERIC_SHARED_CONFIRMATION
        }
        assert await financial_fingerprint(client) == before_rejected_undo
        assert (await candidate(client, account["id"]))["id"] == undo_id
        confirmed_undo = await client.post(
            f"/api/v1/operations/accounts/{account['id']}/undo",
            json={"transaction_id": undo_id, "confirm_ended_period": True},
        )
        assert confirmed_undo.status_code == 200, (state, confirmed_undo.text)

    for key_sets in response_key_sets.values():
        assert all(keys == key_sets[0] for keys in key_sets)
    assert await period_rows(client) == before_periods
    assert await stored_snapshot(client, closed_period["id"]) == closed_snapshot

    await login(client, "alice")
    for state in ("absent", "current", "closed"):
        account = accounts[state]
        account_response = await client.get(f"/api/v1/accounts/{account['id']}")
        assert account_response.status_code == 200
        target = Decimal(account_response.json()["balance"]) + Decimal("1")
        reconciled = await client.post(
            f"/api/v1/accounts/{account['id']}/reconcile",
            json={"target_balance": str(target)},
        )
        assert reconciled.status_code == 200, (state, reconciled.text)
        assert reconciled.json()["type"] == "adjustment"
    assert await stored_snapshot(client, closed_period["id"]) == closed_snapshot

    await register(client, "period-contributor")
    for token in contributor_tokens:
        await accept(client, token)
    contributor_spends = []
    for state, account in accounts.items():
        contributor_spend = await client.post(
            "/api/v1/operations/spend",
            json={
                "account_id": account["id"],
                "amount": "1",
                "local_date": dates[state].isoformat(),
            },
        )
        assert contributor_spend.status_code == 201, (state, contributor_spend.text)
        contributor_spends.append(contributor_spend)
    contributor_spend = contributor_spends[2]
    contributor_id = contributor_spend.json()["id"]
    before_contributor_patch = await financial_fingerprint(client)
    assert (
        await client.patch(
            f"/api/v1/transactions/{contributor_id}", json={"amount": "2"}
        )
    ).status_code == 403
    assert await financial_fingerprint(client) == before_contributor_patch
    before_contributor_delete = await financial_fingerprint(client)
    assert (
        await client.post(f"/api/v1/transactions/{contributor_id}/delete")
    ).status_code == 403
    assert await financial_fingerprint(client) == before_contributor_delete
    contributor_undo = await client.post(
        f"/api/v1/operations/accounts/{accounts['ended']['id']}/undo",
        json={"transaction_id": contributor_id},
    )
    assert contributor_undo.status_code == 409
    assert contributor_undo.json() == {"detail": GENERIC_SHARED_CONFIRMATION}
    confirmed_contributor_undo = await client.post(
        f"/api/v1/operations/accounts/{accounts['ended']['id']}/undo",
        json={"transaction_id": contributor_id, "confirm_ended_period": True},
    )
    assert confirmed_contributor_undo.status_code == 200
    before_contributor_income = await financial_fingerprint(client)
    contributor_income = await client.post(
        "/api/v1/operations/add-funds",
        json={"account_id": accounts["ended"]["id"], "amount": "1"},
    )
    assert contributor_income.status_code == 403
    assert contributor_income.json() == {"detail": "Account permission denied"}
    assert await financial_fingerprint(client) == before_contributor_income

    await register(client, "period-viewer")
    await accept(client, viewer_token)
    before_viewer_spend = await financial_fingerprint(client)
    viewer_spend = await client.post(
        "/api/v1/operations/spend",
        json={"account_id": accounts["ended"]["id"], "amount": "1"},
    )
    assert viewer_spend.status_code == 403
    assert viewer_spend.json() == {"detail": "Account permission denied"}
    assert await financial_fingerprint(client) == before_viewer_spend


async def test_shared_assign_and_reconcile_keep_workspace_and_role_precedence(client):
    await register(client)
    today = local_today()
    accounts = {
        "absent": await create_account(client, "Assign absent USD", "USD", "100"),
        "current": await create_account(client, "Assign current USD", "USD", "100"),
        "ended": await create_account(client, "Assign ended USD", "USD", "100"),
        "closed": await create_account(client, "Assign closed USD", "USD", "100"),
    }
    asset_mismatch_account = await create_account(
        client, "Assign mismatch VND", "VND", "100000"
    )
    hidden_account = await create_account(client, "Assign hidden USD", "USD", "100")
    dates = {
        "absent": today,
        "current": today,
        "ended": today - timedelta(days=7),
        "closed": today,
    }
    await create_period(
        client,
        accounts["current"]["id"],
        today - timedelta(days=1),
        today + timedelta(days=1),
    )
    await create_period(
        client,
        accounts["ended"]["id"],
        today - timedelta(days=10),
        today - timedelta(days=5),
    )
    await create_period(
        client,
        asset_mismatch_account["id"],
        today - timedelta(days=10),
        today - timedelta(days=5),
    )
    closed_period = await create_period(
        client,
        accounts["closed"]["id"],
        today - timedelta(days=1),
        today + timedelta(days=1),
    )
    close = await client.post(
        f"/api/v1/account-periods/{closed_period['id']}/close"
    )
    assert close.status_code == 200, close.text
    closed_snapshot = await stored_snapshot(client, closed_period["id"])
    before_periods = await period_rows(client)
    editor_tokens = [
        await invitation(client, account["id"], "editor")
        for account in (*accounts.values(), asset_mismatch_account)
    ]
    contributor_tokens = [
        await invitation(client, account["id"], "contributor")
        for account in accounts.values()
    ]
    viewer_token = await invitation(client, accounts["ended"]["id"], "viewer")

    await register(client, "assign-editor")
    for token in editor_tokens:
        await accept(client, token)
    posted_transaction_id = None
    for state, account in accounts.items():
        for transaction_type in ("expense", "income"):
            transaction_id = await seed_shared_workspace_unassigned(
                client,
                username="assign-editor",
                account_id=account["id"],
                transaction_type=transaction_type,
                local_date=dates[state],
            )
            assigned = await client.post(
                f"/api/v1/transactions/{transaction_id}/assign-account",
                json={"account_id": account["id"]},
            )
            assert assigned.status_code == 200, (state, transaction_type, assigned.text)
            assert assigned.json()["status"] == "posted"
            assert assigned.json()["legs"][0]["account_id"] == account["id"]
            posted_transaction_id = posted_transaction_id or transaction_id

    assert posted_transaction_id is not None
    before_posted_retry = await financial_fingerprint(client)
    posted_retry = await client.post(
        f"/api/v1/transactions/{posted_transaction_id}/assign-account",
        json={"account_id": accounts["ended"]["id"]},
    )
    assert posted_retry.status_code == 409
    assert posted_retry.json() == {"detail": "Transaction is not unassigned"}
    assert await financial_fingerprint(client) == before_posted_retry

    mismatch_id = await seed_shared_workspace_unassigned(
        client,
        username="assign-editor",
        account_id=accounts["ended"]["id"],
        transaction_type="expense",
        local_date=dates["ended"],
    )
    before_mismatch = await financial_fingerprint(client)
    mismatch = await client.post(
        f"/api/v1/transactions/{mismatch_id}/assign-account",
        json={"account_id": asset_mismatch_account["id"]},
    )
    assert mismatch.status_code == 422
    assert mismatch.json() == {
        "detail": "Account asset does not match transaction"
    }
    assert await financial_fingerprint(client) == before_mismatch

    hidden_target_id = await seed_shared_workspace_unassigned(
        client,
        username="assign-editor",
        account_id=accounts["ended"]["id"],
        transaction_type="expense",
        local_date=dates["ended"],
    )
    before_hidden_target = await financial_fingerprint(client)
    hidden_target = await client.post(
        f"/api/v1/transactions/{hidden_target_id}/assign-account",
        json={"account_id": hidden_account["id"]},
    )
    assert hidden_target.status_code == 404
    assert hidden_target.json() == {"detail": "Account not found"}
    assert await financial_fingerprint(client) == before_hidden_target

    creator_mismatch_id = await seed_shared_workspace_unassigned(
        client,
        username="alice",
        account_id=accounts["ended"]["id"],
        transaction_type="expense",
        local_date=dates["ended"],
    )
    before_creator_mismatch = await financial_fingerprint(client)
    creator_mismatch = await client.post(
        f"/api/v1/transactions/{creator_mismatch_id}/assign-account",
        json={"account_id": accounts["ended"]["id"]},
    )
    assert creator_mismatch.status_code == 404
    assert creator_mismatch.json() == {"detail": "Transaction not found"}
    assert await financial_fingerprint(client) == before_creator_mismatch

    cross_workspace_id = await seed_unassigned_transaction(
        client,
        username="assign-editor",
        amount="4",
        local_date=dates["ended"],
    )
    before_cross_workspace = await financial_fingerprint(client)
    cross_workspace = await client.post(
        f"/api/v1/transactions/{cross_workspace_id}/assign-account",
        json={"account_id": accounts["ended"]["id"]},
    )
    assert cross_workspace.status_code == 422
    assert cross_workspace.json() == {
        "detail": "Account belongs to another workspace"
    }
    assert await financial_fingerprint(client) == before_cross_workspace
    before_shared_reconcile = await financial_fingerprint(client)
    shared_reconcile = await client.post(
        f"/api/v1/accounts/{accounts['ended']['id']}/reconcile",
        json={"target_balance": "50"},
    )
    assert shared_reconcile.status_code == 403
    assert shared_reconcile.json() == {"detail": "Account permission denied"}
    assert await financial_fingerprint(client) == before_shared_reconcile

    await register(client, "assign-contributor")
    for token in contributor_tokens:
        await accept(client, token)
    for state, account in accounts.items():
        transaction_id = await seed_shared_workspace_unassigned(
            client,
            username="assign-contributor",
            account_id=account["id"],
            transaction_type="expense",
            local_date=dates[state],
        )
        assigned = await client.post(
            f"/api/v1/transactions/{transaction_id}/assign-account",
            json={"account_id": account["id"]},
        )
        assert assigned.status_code == 200, (state, assigned.text)
        assert assigned.json()["status"] == "posted"

    forbidden_income_id = await seed_shared_workspace_unassigned(
        client,
        username="assign-contributor",
        account_id=accounts["ended"]["id"],
        transaction_type="income",
        local_date=dates["ended"],
    )
    before_forbidden_income = await financial_fingerprint(client)
    forbidden_income = await client.post(
        f"/api/v1/transactions/{forbidden_income_id}/assign-account",
        json={"account_id": accounts["ended"]["id"]},
    )
    assert forbidden_income.status_code == 403
    assert forbidden_income.json() == {"detail": "Account permission denied"}
    assert await financial_fingerprint(client) == before_forbidden_income
    before_contributor_reconcile = await financial_fingerprint(client)
    contributor_reconcile = await client.post(
        f"/api/v1/accounts/{accounts['ended']['id']}/reconcile",
        json={"target_balance": "50"},
    )
    assert contributor_reconcile.status_code == 403
    assert contributor_reconcile.json() == {"detail": "Account permission denied"}
    assert await financial_fingerprint(client) == before_contributor_reconcile

    await register(client, "assign-viewer")
    await accept(client, viewer_token)
    viewer_unassigned_id = await seed_shared_workspace_unassigned(
        client,
        username="assign-viewer",
        account_id=accounts["ended"]["id"],
        transaction_type="expense",
        local_date=dates["ended"],
    )
    before_viewer_assign = await financial_fingerprint(client)
    viewer_assign = await client.post(
        f"/api/v1/transactions/{viewer_unassigned_id}/assign-account",
        json={"account_id": accounts["ended"]["id"]},
    )
    assert viewer_assign.status_code == 403
    assert viewer_assign.json() == {"detail": "Account permission denied"}
    assert await financial_fingerprint(client) == before_viewer_assign
    before_viewer_reconcile = await financial_fingerprint(client)
    viewer_reconcile = await client.post(
        f"/api/v1/accounts/{accounts['ended']['id']}/reconcile",
        json={"target_balance": "50"},
    )
    assert viewer_reconcile.status_code == 403
    assert viewer_reconcile.json() == {"detail": "Account permission denied"}
    assert await financial_fingerprint(client) == before_viewer_reconcile

    await register(client, "assign-foreign")
    before_foreign_reconcile = await financial_fingerprint(client)
    foreign_reconcile = await client.post(
        f"/api/v1/accounts/{accounts['ended']['id']}/reconcile",
        json={"target_balance": "50"},
    )
    assert foreign_reconcile.status_code == 404
    assert foreign_reconcile.json() == {"detail": "Account not found"}
    assert await financial_fingerprint(client) == before_foreign_reconcile

    assert await period_rows(client) == before_periods
    assert await stored_snapshot(client, closed_period["id"]) == closed_snapshot


async def test_hidden_fee_and_visible_role_failures_precede_period_confirmation(client):
    await register(client)
    today = local_today()
    historical = today - timedelta(days=7)
    hidden_source = await create_account(client, "Hidden fee source USD", "USD", "100")
    hidden_target = await create_account(client, "Hidden fee target VND", "VND", "0")
    hidden_fee = await create_account(client, "Hidden fee USD", "USD", "10")
    private_target = await create_account(client, "Private target VND", "VND", "0")
    private_fee = await create_account(client, "Private fee USD", "USD", "10")
    private_source = await create_account(client, "Private source USD", "USD", "100")
    insufficient_source = await create_account(
        client, "Contributor source USD", "USD", "100"
    )
    denied_source = await create_account(client, "Denied fee source USD", "USD", "100")
    denied_target = await create_account(client, "Denied fee target VND", "VND", "0")
    denied_fee = await create_account(client, "Denied fee USD", "USD", "10")
    for account in (hidden_source, hidden_fee, denied_source, denied_fee):
        await create_period(
            client,
            account["id"],
            today - timedelta(days=10),
            today - timedelta(days=5),
        )
    tokens = [
        await invitation(client, account["id"], "editor")
        for account in (
            hidden_source,
            hidden_target,
            hidden_fee,
            denied_source,
            denied_target,
            denied_fee,
        )
    ]
    insufficient_source_token = await invitation(
        client, insufficient_source["id"], "contributor"
    )
    bob = await register(client, "fee-editor")
    for token in tokens:
        await accept(client, token)
    await accept(client, insufficient_source_token)

    def exchange_body(source, target, fee):
        return {
            "from_account_id": source["id"],
            "from_amount": "2",
            "to_account_id": target["id"],
            "to_amount": "50000",
            "local_date": historical.isoformat(),
            "fee": {"account_id": fee["id"], "amount": "0.25"},
        }

    for source, expected_status, expected_detail in (
        (insufficient_source, 403, "Account permission denied"),
        (private_source, 404, "Account not found"),
    ):
        before = await financial_fingerprint(client)
        rejected_source = await client.post(
            "/api/v1/operations/exchange",
            json=exchange_body(source, hidden_target, hidden_fee),
        )
        assert rejected_source.status_code == expected_status
        assert rejected_source.json() == {"detail": expected_detail}
        assert await financial_fingerprint(client) == before

    for target, fee in (
        (private_target, hidden_fee),
        (hidden_target, private_fee),
    ):
        before = await financial_fingerprint(client)
        rejected_create = await client.post(
            "/api/v1/operations/exchange",
            json=exchange_body(hidden_source, target, fee),
        )
        assert rejected_create.status_code == 404
        assert rejected_create.json() == {"detail": "Account not found"}
        assert await financial_fingerprint(client) == before

    hidden_exchange = await client.post(
        "/api/v1/operations/exchange",
        json=exchange_body(hidden_source, hidden_target, hidden_fee),
    )
    assert hidden_exchange.status_code == 201, hidden_exchange.text
    hidden_id = hidden_exchange.json()["id"]
    for method, route, body in (
        ("patch", f"/api/v1/transactions/{hidden_id}", {"note": "blocked"}),
        ("post", f"/api/v1/transactions/{hidden_id}/delete", None),
        (
            "post",
            f"/api/v1/operations/accounts/{hidden_source['id']}/undo",
            {"transaction_id": hidden_id},
        ),
    ):
        before = await financial_fingerprint(client)
        response = await client.request(method, route, json=body)
        assert response.status_code == 409
        assert response.json() == {"detail": GENERIC_SHARED_CONFIRMATION}
        assert await financial_fingerprint(client) == before

    denied_exchange = await client.post(
        "/api/v1/operations/exchange",
        json=exchange_body(denied_source, denied_target, denied_fee),
    )
    assert denied_exchange.status_code == 201, denied_exchange.text
    denied_id = denied_exchange.json()["id"]

    await login(client, "alice")
    removed = await client.delete(
        f"/api/v1/accounts/{hidden_fee['id']}/access/{bob['user']['id']}"
    )
    assert removed.status_code == 204, removed.text
    downgraded = await client.patch(
        f"/api/v1/accounts/{denied_fee['id']}/access/{bob['user']['id']}",
        json={"role": "viewer"},
    )
    assert downgraded.status_code == 200, downgraded.text
    await login(client, "fee-editor")

    for method, route, body in (
        ("patch", f"/api/v1/transactions/{hidden_id}", {"note": "hidden"}),
        ("post", f"/api/v1/transactions/{hidden_id}/delete", None),
        (
            "post",
            f"/api/v1/operations/accounts/{hidden_source['id']}/undo",
            {"transaction_id": hidden_id},
        ),
    ):
        before = await financial_fingerprint(client)
        response = await client.request(method, route, json=body)
        assert response.status_code == 404
        assert response.json() == {"detail": "Account not found"}
        assert await financial_fingerprint(client) == before

    for method, route, body in (
        ("patch", f"/api/v1/transactions/{denied_id}", {"note": "denied"}),
        ("post", f"/api/v1/transactions/{denied_id}/delete", None),
        (
            "post",
            f"/api/v1/operations/accounts/{denied_source['id']}/undo",
            {"transaction_id": denied_id},
        ),
    ):
        before = await financial_fingerprint(client)
        response = await client.request(method, route, json=body)
        assert response.status_code == 403, (method, route, response.text)
        assert response.json() == {"detail": "Account permission denied"}
        assert await financial_fingerprint(client) == before


async def test_contributor_viewer_and_creator_undo_boundaries_ignore_hidden_periods(client):
    await register(client)
    today = local_today()
    historical = today - timedelta(days=7)
    income = await create_account(client, "Denied income USD", "USD", "0")
    transfer_source = await create_account(client, "Denied transfer source USD", "USD", "100")
    transfer_target = await create_account(client, "Denied transfer target USD", "USD", "0")
    exchange_source = await create_account(client, "Denied exchange source USD", "USD", "100")
    exchange_target = await create_account(client, "Denied exchange target VND", "VND", "0")
    exchange_fee = await create_account(client, "Denied exchange fee USD", "USD", "10")
    creator_account = await create_account(client, "Creator scope USD", "USD", "100")
    all_accounts = (
        income,
        transfer_source,
        transfer_target,
        exchange_source,
        exchange_target,
        exchange_fee,
        creator_account,
    )
    for account in (income, transfer_source, exchange_source, exchange_fee, creator_account):
        await create_period(
            client,
            account["id"],
            today - timedelta(days=10),
            today - timedelta(days=5),
        )
    tokens = [
        await invitation(client, account["id"], "editor") for account in all_accounts
    ]
    bob = await register(client, "undo-editor")
    for token in tokens:
        await accept(client, token)

    income_transaction = await client.post(
        "/api/v1/operations/add-funds",
        json={
            "account_id": income["id"],
            "amount": "2",
            "local_date": historical.isoformat(),
        },
    )
    transfer_transaction = await client.post(
        "/api/v1/operations/transfer",
        json={
            "from_account_id": transfer_source["id"],
            "to_account_id": transfer_target["id"],
            "amount": "2",
            "local_date": historical.isoformat(),
        },
    )
    exchange_transaction = await client.post(
        "/api/v1/operations/exchange",
        json={
            "from_account_id": exchange_source["id"],
            "from_amount": "2",
            "to_account_id": exchange_target["id"],
            "to_amount": "50000",
            "local_date": historical.isoformat(),
            "fee": {"account_id": exchange_fee["id"], "amount": "0.25"},
        },
    )
    for response in (income_transaction, transfer_transaction, exchange_transaction):
        assert response.status_code == 201, response.text

    for account, transaction_id in (
        (transfer_source, transfer_transaction.json()["id"]),
        (exchange_source, exchange_transaction.json()["id"]),
    ):
        for method, route, body in (
            ("patch", f"/api/v1/transactions/{transaction_id}", {"note": "blocked"}),
            ("post", f"/api/v1/transactions/{transaction_id}/delete", None),
            (
                "post",
                f"/api/v1/operations/accounts/{account['id']}/undo",
                {"transaction_id": transaction_id},
            ),
        ):
            before = await financial_fingerprint(client)
            response = await client.request(method, route, json=body)
            assert response.status_code == 409
            assert response.json() == {"detail": GENERIC_SHARED_CONFIRMATION}
            assert await financial_fingerprint(client) == before

    await login(client, "alice")
    owner_transaction = await client.post(
        "/api/v1/operations/spend",
        json={
            "account_id": creator_account["id"],
            "amount": "1",
            "local_date": historical.isoformat(),
            "confirm_ended_period": True,
        },
    )
    assert owner_transaction.status_code == 201, owner_transaction.text
    for account in all_accounts[:-1]:
        changed = await client.patch(
            f"/api/v1/accounts/{account['id']}/access/{bob['user']['id']}",
            json={"role": "contributor"},
        )
        assert changed.status_code == 200, changed.text
    await login(client, "undo-editor")

    denied_undos = (
        (income, income_transaction.json()["id"]),
        (transfer_source, transfer_transaction.json()["id"]),
        (exchange_source, exchange_transaction.json()["id"]),
    )
    for account, transaction_id in denied_undos:
        before = await financial_fingerprint(client)
        response = await client.post(
            f"/api/v1/operations/accounts/{account['id']}/undo",
            json={"transaction_id": transaction_id},
        )
        assert response.status_code == 403
        assert response.json() == {"detail": "Account permission denied"}
        assert await financial_fingerprint(client) == before

    before_contributor_patch = await financial_fingerprint(client)
    contributor_patch = await client.patch(
        f"/api/v1/transactions/{exchange_transaction.json()['id']}",
        json={"note": "contributor denied"},
    )
    assert contributor_patch.status_code == 403
    assert contributor_patch.json() == {"detail": "Account permission denied"}
    assert await financial_fingerprint(client) == before_contributor_patch
    before_contributor_delete = await financial_fingerprint(client)
    contributor_delete = await client.post(
        f"/api/v1/transactions/{exchange_transaction.json()['id']}/delete"
    )
    assert contributor_delete.status_code == 403
    assert contributor_delete.json() == {"detail": "Account permission denied"}
    assert await financial_fingerprint(client) == before_contributor_delete

    await login(client, "alice")
    viewer = await client.patch(
        f"/api/v1/accounts/{exchange_source['id']}/access/{bob['user']['id']}",
        json={"role": "viewer"},
    )
    assert viewer.status_code == 200, viewer.text
    await login(client, "undo-editor")
    for method, route, body in (
        (
            "patch",
            f"/api/v1/transactions/{exchange_transaction.json()['id']}",
            {"note": "viewer denied"},
        ),
        (
            "post",
            f"/api/v1/transactions/{exchange_transaction.json()['id']}/delete",
            None,
        ),
        (
            "post",
            f"/api/v1/operations/accounts/{exchange_source['id']}/undo",
            {"transaction_id": exchange_transaction.json()["id"]},
        ),
    ):
        before = await financial_fingerprint(client)
        response = await client.request(method, route, json=body)
        assert response.status_code == 403
        assert response.json() == {"detail": "Account permission denied"}
        assert await financial_fingerprint(client) == before

    before_creator_scope = await financial_fingerprint(client)
    creator_scope = await client.post(
        f"/api/v1/operations/accounts/{creator_account['id']}/undo",
        json={"transaction_id": owner_transaction.json()["id"]},
    )
    assert creator_scope.status_code == 409
    assert creator_scope.json() == {"detail": "Undo candidate changed"}
    assert await financial_fingerprint(client) == before_creator_scope
