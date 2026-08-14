"""Phase 12 Block 4: cross-cutting privacy and regression coverage.

Verifies period filtering, linking, deletion replay, owner-private Plan and
period data, and obsolete route absence working together.
"""

from datetime import timedelta
from decimal import Decimal

from tests.conftest import register
from tests.test_ledger_v2 import create_account
from tests.test_periods_v2 import create_period, local_today
from tests.test_plan_v2 import create_rule, occurrences_for_rule
from tests.test_sharing_v2 import accept, invitation, login


async def test_deleting_linked_transfer_replays_both_periods_and_reopens_plan(client):
    context = await register(client)
    workspace_id = context["workspace"]["id"]
    source = await create_account(client, "Source USD", "USD", "500")
    reserve = await create_account(client, "Reserve USD", "USD", "0")
    today = local_today()
    source_period = await create_period(
        client,
        source["id"],
        start=today - timedelta(days=1),
        end=today + timedelta(days=1),
    )
    reserve_period = await create_period(
        client,
        reserve["id"],
        start=today - timedelta(days=1),
        end=today + timedelta(days=1),
    )
    rule = (
        await create_rule(
            client,
            workspace_id,
            kind="reserve_transfer",
            name="Monthly reserve",
            amount="120",
            category_id=None,
        )
    ).json()
    occurrence = (await occurrences_for_rule(client, workspace_id, rule["id"]))[0]

    transfer = (
        await client.post(
            "/api/v1/operations/transfer",
            json={
                "from_account_id": source["id"],
                "to_account_id": reserve["id"],
                "amount": "120",
                "local_date": today.isoformat(),
            },
        )
    ).json()
    linked = await client.post(
        f"/api/v1/workspaces/{workspace_id}/plan-occurrences/"
        f"{occurrence['id']}/link-transaction",
        json={"transaction_id": transfer["id"]},
    )
    assert linked.status_code == 200, linked.text

    async def current_balance(period_id):
        response = await client.get(f"/api/v1/account-periods/{period_id}")
        assert response.status_code == 200, response.text
        return Decimal(response.json()["current_balance"])

    assert await current_balance(source_period["id"]) == Decimal("380")
    assert await current_balance(reserve_period["id"]) == Decimal("120")

    # Linking must not move the transaction between periods: the transfer's
    # own legs still decide membership in both period filters.
    for period in (source_period, reserve_period):
        listed = await client.get(
            f"/api/v1/transactions?period_id={period['id']}"
        )
        assert listed.status_code == 200, listed.text
        assert transfer["id"] in [item["id"] for item in listed.json()["items"]]

    deleted = await client.post(f"/api/v1/transactions/{transfer['id']}/delete")
    assert deleted.status_code == 200, deleted.text
    assert await current_balance(source_period["id"]) == Decimal("500")
    assert await current_balance(reserve_period["id"]) == Decimal("0")
    for period in (source_period, reserve_period):
        listed = await client.get(
            f"/api/v1/transactions?period_id={period['id']}"
        )
        items = listed.json()["items"]
        assert transfer["id"] not in {item["id"] for item in items}
        assert all(item["status"] == "posted" for item in items)
        assert all(
            any(leg["account_id"] == period["account_id"] for leg in item["legs"])
            for item in items
        )

    reopened = (await occurrences_for_rule(client, workspace_id, rule["id"]))[0]
    assert reopened["status"] in {"planned", "overdue"}
    assert reopened["transaction_id"] is None
    assert reopened["actual_amount"] is None
    assert reopened["actual_asset"] is None


async def test_shared_account_access_grants_no_plan_visibility(client):
    alice = await register(client)
    alice_workspace = alice["workspace"]["id"]
    shared_account = await create_account(client, "Shared USD", "USD", "300")
    rule = (
        await create_rule(
            client,
            alice_workspace,
            name="Owner-private bill",
            amount="40",
            default_from_account_id=shared_account["id"],
        )
    ).json()
    occurrence = (await occurrences_for_rule(
        client, alice_workspace, rule["id"]
    ))[0]
    visible_spend = (
        await client.post(
            "/api/v1/operations/spend",
            json={"account_id": shared_account["id"], "amount": "40"},
        )
    ).json()
    token = await invitation(client, shared_account["id"], "editor")

    await register(client, "bob")
    await accept(client, token)
    # Bob sees the shared transaction itself.
    assert (
        await client.get(f"/api/v1/transactions/{visible_spend['id']}")
    ).status_code == 200

    # But every Plan surface of the owner's workspace stays hidden: reads,
    # occurrence actions, and the transaction-side link entry point.
    assert (
        await client.get(f"/api/v1/workspaces/{alice_workspace}/plan-rules")
    ).status_code == 404
    assert (
        await client.get(
            f"/api/v1/workspaces/{alice_workspace}/plan-occurrences"
        )
    ).status_code == 404
    assert (
        await client.post(
            f"/api/v1/workspaces/{alice_workspace}/plan-occurrences/"
            f"{occurrence['id']}/skip"
        )
    ).status_code == 404
    assert (
        await client.post(
            f"/api/v1/workspaces/{alice_workspace}/plan-occurrences/"
            f"{occurrence['id']}/link-transaction",
            json={"transaction_id": visible_spend["id"]},
        )
    ).status_code == 404
    linked_via_transaction = await client.post(
        f"/api/v1/transactions/{visible_spend['id']}/link-plan",
        json={"occurrence_id": occurrence["id"]},
    )
    assert linked_via_transaction.status_code == 404
    assert linked_via_transaction.json()["detail"] == "Plan occurrence not found"

    # The occurrence is untouched by the rejected attempts.
    await login(client, "alice")
    untouched = (await occurrences_for_rule(
        client, alice_workspace, rule["id"]
    ))[0]
    assert untouched["status"] in {"planned", "overdue"}
    assert untouched["transaction_id"] is None


async def test_openapi_exposes_only_the_phase12_contract(client):
    await register(client)
    paths = (await client.get("/openapi.json")).json()["paths"]

    forbidden_fragments = (
        "/tracker",
        "/budget-periods",
        "/budget-commitments",
        "/pay",
        "/receive",
        "/void",
    )
    offenders = {
        path
        for path in paths
        if any(fragment in path for fragment in forbidden_fragments)
    }
    assert not offenders, offenders

    for suffix in ("expense", "income", "transfer", "exchange", "adjustment"):
        assert f"/api/v1/transactions/{suffix}" not in paths

    occurrence_actions = {
        path.rsplit("/", 1)[-1]
        for path in paths
        if "/plan-occurrences/{occurrence_id}/" in path
    }
    assert occurrence_actions == {"skip", "link-transaction"}

    transaction_item_actions = {
        path.rsplit("/", 1)[-1]
        for path in paths
        if path.startswith("/api/v1/transactions/{transaction_id}/")
    }
    assert transaction_item_actions == {"delete", "assign-account", "link-plan"}
