from datetime import timedelta
from decimal import Decimal

from tests.conftest import register
from tests.test_ledger_v2 import create_account
from tests.test_periods_v2 import create_period, local_today
from tests.test_sharing_v2 import accept, invitation, login


async def balance(client, account_id: int) -> Decimal:
    response = await client.get(f"/api/v1/accounts/{account_id}")
    assert response.status_code == 200, response.text
    return Decimal(response.json()["balance"])


async def candidate(client, account_id: int):
    response = await client.get(f"/api/v1/operations/accounts/{account_id}/undo")
    assert response.status_code == 200, response.text
    return response.json()


async def test_undo_candidate_survives_reads_ignores_manual_and_never_falls_back(client):
    await register(client)
    account = await create_account(client, "Undo USD", "USD", "100")
    older = await client.post(
        "/api/v1/operations/spend",
        json={"account_id": account["id"], "amount": "10"},
    )
    assert older.status_code == 201, older.text
    manual = await client.post(
        f"/api/v1/accounts/{account['id']}/reconcile",
        json={"target_balance": "95"},
    )
    assert manual.status_code == 200, manual.text

    first_read = await candidate(client, account["id"])
    reload_read = await candidate(client, account["id"])
    assert first_read["id"] == older.json()["id"] == reload_read["id"]
    undone = await client.post(
        f"/api/v1/operations/accounts/{account['id']}/undo",
        json={"transaction_id": older.json()["id"]},
    )
    assert undone.status_code == 200, undone.text
    assert undone.json()["status"] == "deleted"
    assert await balance(client, account["id"]) == Decimal("105")
    assert await candidate(client, account["id"]) is None
    assert await candidate(client, account["id"]) is None

    newer = await client.post(
        "/api/v1/operations/add-funds",
        json={"account_id": account["id"], "amount": "7"},
    )
    assert newer.status_code == 201, newer.text
    assert (await candidate(client, account["id"]))["id"] == newer.json()["id"]


async def test_transfer_undo_consumes_every_root_leg_and_replays_periods(client):
    await register(client)
    source = await create_account(client, "Undo source USD", "USD", "100")
    target = await create_account(client, "Undo target USD", "USD", "0")
    source_period = await create_period(client, source["id"], "100")
    target_period = await create_period(client, target["id"], "0")
    assert (
        await client.post(
            "/api/v1/operations/spend",
            json={"account_id": source["id"], "amount": "1"},
        )
    ).status_code == 201
    assert (
        await client.post(
            "/api/v1/operations/add-funds",
            json={"account_id": target["id"], "amount": "2"},
        )
    ).status_code == 201
    transfer = await client.post(
        "/api/v1/operations/transfer",
        json={
            "from_account_id": source["id"],
            "to_account_id": target["id"],
            "amount": "10",
        },
    )
    assert transfer.status_code == 201, transfer.text
    assert (await candidate(client, source["id"]))["id"] == transfer.json()["id"]
    assert (await candidate(client, target["id"]))["id"] == transfer.json()["id"]

    undone = await client.post(
        f"/api/v1/operations/accounts/{source['id']}/undo",
        json={"transaction_id": transfer.json()["id"]},
    )
    assert undone.status_code == 200, undone.text
    assert await candidate(client, source["id"]) is None
    assert await candidate(client, target["id"]) is None
    assert await balance(client, source["id"]) == Decimal("99")
    assert await balance(client, target["id"]) == Decimal("2")
    assert (
        await client.get(f"/api/v1/account-periods/{source_period['id']}")
    ).json()["remaining"] == "99"
    assert (
        await client.get(f"/api/v1/account-periods/{target_period['id']}")
    ).json()["remaining"] == "2"


async def test_undo_rejects_a_stale_candidate_confirmed_in_another_tab(client):
    await register(client)
    account = await create_account(client, "Stale candidate USD", "USD", "100")
    first = await client.post(
        "/api/v1/operations/spend",
        json={"account_id": account["id"], "amount": "1"},
    )
    assert first.status_code == 201, first.text
    stale_id = (await candidate(client, account["id"]))["id"]
    newer = await client.post(
        "/api/v1/operations/add-funds",
        json={"account_id": account["id"], "amount": "2"},
    )
    assert newer.status_code == 201, newer.text

    rejected = await client.post(
        f"/api/v1/operations/accounts/{account['id']}/undo",
        json={"transaction_id": stale_id, "confirm_ended_period": True},
    )
    assert rejected.status_code == 409
    assert rejected.json()["detail"] == "Undo candidate changed"
    assert (await candidate(client, account["id"]))["id"] == newer.json()["id"]
    assert (
        await client.get(f"/api/v1/transactions/{first.json()['id']}")
    ).json()["status"] == "posted"
    assert (
        await client.get(f"/api/v1/transactions/{newer.json()['id']}")
    ).json()["status"] == "posted"

    accepted = await client.post(
        f"/api/v1/operations/accounts/{account['id']}/undo",
        json={"transaction_id": newer.json()["id"], "confirm_ended_period": True},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["id"] == newer.json()["id"]


async def test_correction_reindexes_root_and_consumes_removed_account_cursor(client):
    await register(client)
    source = await create_account(client, "Correction source USD", "USD", "100")
    target = await create_account(client, "Correction target USD", "USD", "100")
    older_target = await client.post(
        "/api/v1/operations/spend",
        json={"account_id": target["id"], "amount": "1"},
    )
    newer_source = await client.post(
        "/api/v1/operations/spend",
        json={"account_id": source["id"], "amount": "2"},
    )
    assert older_target.status_code == newer_source.status_code == 201

    corrected = await client.patch(
        f"/api/v1/transactions/{newer_source.json()['id']}",
        json={"account_id": target["id"]},
    )
    assert corrected.status_code == 200, corrected.text
    assert {leg["account_id"] for leg in corrected.json()["legs"]} == {target["id"]}
    assert await candidate(client, source["id"]) is None
    assert (await candidate(client, target["id"]))["id"] == newer_source.json()["id"]
    assert await balance(client, source["id"]) == Decimal("100")
    assert await balance(client, target["id"]) == Decimal("97")

    undone = await client.post(
        f"/api/v1/operations/accounts/{target['id']}/undo",
        json={"transaction_id": newer_source.json()["id"]},
    )
    assert undone.status_code == 200, undone.text
    assert await candidate(client, source["id"]) is None
    assert await candidate(client, target["id"]) is None
    assert await balance(client, target["id"]) == Decimal("99")


async def test_operations_root_unassignment_and_assignment_reindex_cursor(client):
    await register(client)
    source = await create_account(client, "Assignment source USD", "USD", "100")
    target = await create_account(client, "Assignment target USD", "USD", "0")
    operation = await client.post(
        "/api/v1/operations/spend",
        json={"account_id": source["id"], "amount": "3"},
    )
    assert operation.status_code == 201, operation.text
    unassigned = await client.patch(
        f"/api/v1/transactions/{operation.json()['id']}",
        json={"account_id": None},
    )
    assert unassigned.status_code == 200, unassigned.text
    assert unassigned.json()["status"] == "unassigned"
    assert await candidate(client, source["id"]) is None

    assigned = await client.post(
        f"/api/v1/transactions/{operation.json()['id']}/assign-account",
        json={"account_id": target["id"]},
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["status"] == "posted"
    assert await candidate(client, source["id"]) is None
    assert (await candidate(client, target["id"]))["id"] == operation.json()["id"]


async def test_undo_voids_exchange_fee_but_keeps_fee_accounts_own_candidate(client):
    await register(client)
    source = await create_account(client, "Undo exchange USD", "USD", "100")
    target = await create_account(client, "Undo exchange VND", "VND", "0")
    fee_account = await create_account(client, "Undo fee USD", "USD", "50")
    fee_candidate = await client.post(
        "/api/v1/operations/spend",
        json={"account_id": fee_account["id"], "amount": "1"},
    )
    assert fee_candidate.status_code == 201, fee_candidate.text
    exchange = await client.post(
        "/api/v1/operations/exchange",
        json={
            "from_account_id": source["id"],
            "from_amount": "10",
            "to_account_id": target["id"],
            "to_amount": "250000",
            "fee": {"account_id": fee_account["id"], "amount": "2"},
        },
    )
    assert exchange.status_code == 201, exchange.text
    assert (await candidate(client, fee_account["id"]))["id"] == fee_candidate.json()["id"]

    undone = await client.post(
        f"/api/v1/operations/accounts/{source['id']}/undo",
        json={"transaction_id": exchange.json()["id"]},
    )
    assert undone.status_code == 200, undone.text
    page = (await client.get("/api/v1/transactions?limit=20")).json()["items"]
    child = next(
        item for item in page if item["parent_transaction_id"] == exchange.json()["id"]
    )
    assert child["status"] == "deleted"
    assert (await client.get("/api/v1/exchange-rates")).json() == []
    assert await balance(client, source["id"]) == Decimal("100")
    assert await balance(client, target["id"]) == Decimal("0")
    assert await balance(client, fee_account["id"]) == Decimal("49")
    assert (await candidate(client, fee_account["id"]))["id"] == fee_candidate.json()["id"]


async def test_undoing_older_multi_account_root_preserves_a_later_candidate(client):
    await register(client)
    source = await create_account(client, "Cursor source USD", "USD", "100")
    target = await create_account(client, "Cursor target USD", "USD", "0")
    transfer = await client.post(
        "/api/v1/operations/transfer",
        json={
            "from_account_id": source["id"],
            "to_account_id": target["id"],
            "amount": "10",
        },
    )
    later = await client.post(
        "/api/v1/operations/spend",
        json={"account_id": target["id"], "amount": "2"},
    )
    assert transfer.status_code == later.status_code == 201
    assert (await candidate(client, source["id"]))["id"] == transfer.json()["id"]
    assert (await candidate(client, target["id"]))["id"] == later.json()["id"]

    assert (
        await client.post(
            f"/api/v1/operations/accounts/{source['id']}/undo",
            json={"transaction_id": transfer.json()["id"]},
        )
    ).status_code == 200
    assert await candidate(client, source["id"]) is None
    assert (await candidate(client, target["id"]))["id"] == later.json()["id"]


async def test_undo_is_creator_scoped_and_rechecks_shared_account_rights(client):
    await register(client)
    shared = await create_account(client, "Creator scoped USD", "USD", "100")
    alice_operation = await client.post(
        "/api/v1/operations/spend",
        json={"account_id": shared["id"], "amount": "1"},
    )
    token = await invitation(client, shared["id"], "editor")
    bob = await register(client, "bob")
    await accept(client, token)
    assert await candidate(client, shared["id"]) is None
    bob_operation = await client.post(
        "/api/v1/operations/spend",
        json={"account_id": shared["id"], "amount": "2"},
    )
    assert bob_operation.status_code == 201, bob_operation.text
    assert (await candidate(client, shared["id"]))["id"] == bob_operation.json()["id"]

    await login(client, "alice")
    assert (await candidate(client, shared["id"]))["id"] == alice_operation.json()["id"]
    downgraded = await client.patch(
        f"/api/v1/accounts/{shared['id']}/access/{bob['user']['id']}",
        json={"role": "viewer"},
    )
    assert downgraded.status_code == 200, downgraded.text
    await login(client, "bob")
    rejected = await client.get(f"/api/v1/operations/accounts/{shared['id']}/undo")
    assert rejected.status_code == 403
    rejected = await client.post(
        f"/api/v1/operations/accounts/{shared['id']}/undo",
        json={
            "transaction_id": bob_operation.json()["id"],
            "confirm_ended_period": True,
        },
    )
    assert rejected.status_code == 403


async def test_undo_period_guards_do_not_consume_rejected_candidate(client):
    await register(client)
    account = await create_account(client, "Undo historical USD", "USD", "100")
    ended_date = local_today() - timedelta(days=7)
    period = await create_period(
        client,
        account["id"],
        "100",
        ended_date - timedelta(days=1),
        ended_date + timedelta(days=1),
    )
    operation = await client.post(
        "/api/v1/operations/spend",
        json={
            "account_id": account["id"],
            "amount": "5",
            "local_date": ended_date.isoformat(),
            "confirm_ended_period": True,
        },
    )
    assert operation.status_code == 201, operation.text
    rejected = await client.post(
        f"/api/v1/operations/accounts/{account['id']}/undo",
        json={"transaction_id": operation.json()["id"]},
    )
    assert rejected.status_code == 409
    assert "explicit confirmation" in rejected.json()["detail"]
    assert (await candidate(client, account["id"]))["id"] == operation.json()["id"]
    assert (
        await client.get(f"/api/v1/transactions/{operation.json()['id']}")
    ).json()["status"] == "posted"
    confirmed = await client.post(
        f"/api/v1/operations/accounts/{account['id']}/undo",
        json={
            "transaction_id": operation.json()["id"],
            "confirm_ended_period": True,
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    assert await candidate(client, account["id"]) is None

    closed_account = await create_account(client, "Undo closed USD", "USD", "50")
    closed_period = await create_period(client, closed_account["id"], "50")
    closed_operation = await client.post(
        "/api/v1/operations/spend",
        json={"account_id": closed_account["id"], "amount": "3"},
    )
    assert closed_operation.status_code == 201, closed_operation.text
    assert (
        await client.post(f"/api/v1/account-periods/{closed_period['id']}/close")
    ).status_code == 200
    closed_rejected = await client.post(
        f"/api/v1/operations/accounts/{closed_account['id']}/undo",
        json={
            "transaction_id": closed_operation.json()["id"],
            "confirm_ended_period": True,
        },
    )
    assert closed_rejected.status_code == 409
    assert closed_rejected.json()["detail"] == "Closed account period is read-only"
    assert (await candidate(client, closed_account["id"]))["id"] == closed_operation.json()["id"]
    assert (
        await client.get(f"/api/v1/account-periods/{period['id']}")
    ).status_code == 200
