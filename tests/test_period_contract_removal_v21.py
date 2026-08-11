from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from app.models import AccountPeriod, Transaction, TransactionLeg
from tests.conftest import register
from tests.test_ledger_v2 import create_account
from tests.test_periods_v2 import local_today


REMOVED_VALUES = [None, False, 0, "1", "", "not-a-value", [], {}]
COMMON_PERIOD_KEYS = {
    "id",
    "account_id",
    "asset",
    "created_by_user_id",
    "start_date",
    "end_date",
    "snapshot_at",
    "opening_balance",
    "rollover_policy",
    "created_at",
    "status",
    "closed_at",
    "closing_balance",
}
CURRENT_PERIOD_KEYS = COMMON_PERIOD_KEYS | {"current_balance", "available_today"}
REMOVED_PERIOD_MEMBERS = {
    "funding_amount",
    "remaining",
    "planned",
    "confirm_ended_period",
}


async def ledger_rows(client):
    async with client._finapp_test_sessions() as session:
        transactions = list(
            (await session.execute(select(Transaction).order_by(Transaction.id))).scalars()
        )
        legs = list(
            (await session.execute(select(TransactionLeg).order_by(TransactionLeg.id))).scalars()
        )
        return (
            tuple(
                (
                    row.id,
                    row.type,
                    row.status,
                    row.local_date,
                )
                for row in transactions
            ),
            tuple(
                (
                    row.id,
                    row.transaction_id,
                    row.account_id,
                    row.asset_id,
                    str(row.amount),
                    row.created_at,
                )
                for row in legs
            ),
        )


async def period_state(client, period_id):
    async with client._finapp_test_sessions() as session:
        row = await session.get(AccountPeriod, period_id)
        assert row is not None
        return (
            row.start_date,
            row.end_date,
            row.snapshot_at,
            row.opening_balance,
            row.rollover_policy,
            row.closed_at,
            row.closing_balance,
        )


@pytest.mark.parametrize("value", REMOVED_VALUES, ids=repr)
@pytest.mark.parametrize("combined", [False, True], ids=["alone", "combined"])
async def test_create_forbidden_funding_matrix_is_mutation_neutral(
    client, value, combined
):
    await register(client)
    account = await create_account(client, "Forbidden create USD", "USD", "25")
    before_ledger = await ledger_rows(client)
    today = local_today()
    body = {"funding_amount": value}
    if combined:
        body["end_date"] = today.isoformat()

    response = await client.post(
        f"/api/v1/accounts/{account['id']}/periods", json=body
    )

    assert response.status_code == 422, response.text
    assert any(
        error["type"] == "extra_forbidden"
        and error["loc"] == ["body", "funding_amount"]
        for error in response.json()["detail"]
    )
    async with client._finapp_test_sessions() as session:
        assert list((await session.execute(select(AccountPeriod))).scalars()) == []
    assert await ledger_rows(client) == before_ledger


@pytest.mark.parametrize("field", ["funding_amount", "confirm_ended_period"])
@pytest.mark.parametrize("value", REMOVED_VALUES, ids=repr)
@pytest.mark.parametrize("combined", [False, True], ids=["alone", "combined"])
async def test_patch_forbidden_member_matrix_is_mutation_neutral(
    client, field, value, combined
):
    await register(client)
    account = await create_account(client, "Forbidden patch USD", "USD", "25")
    today = local_today()
    created = await client.post(
        f"/api/v1/accounts/{account['id']}/periods",
        json={"end_date": (today + timedelta(days=2)).isoformat()},
    )
    assert created.status_code == 201, created.text
    period_id = created.json()["id"]
    before_period = await period_state(client, period_id)
    before_ledger = await ledger_rows(client)
    body = {field: value}
    if combined:
        body["end_date"] = (today + timedelta(days=3)).isoformat()

    response = await client.patch(
        f"/api/v1/account-periods/{period_id}", json=body
    )

    assert response.status_code == 422, response.text
    assert any(
        error["type"] == "extra_forbidden"
        and error["loc"] == ["body", field]
        for error in response.json()["detail"]
    )
    assert await period_state(client, period_id) == before_period
    assert await ledger_rows(client) == before_ledger


def test_openapi_period_components_are_exact_and_unrelated_contracts_remain():
    from app.main import app

    schemas = app.openapi()["components"]["schemas"]
    assert set(schemas["AccountPeriodCreate"]["properties"]) == {
        "start_date",
        "end_date",
        "rollover_policy",
    }
    assert schemas["AccountPeriodCreate"]["required"] == ["end_date"]
    assert set(schemas["AccountPeriodPatch"]["properties"]) == {
        "start_date",
        "end_date",
        "rollover_policy",
    }
    assert "required" not in schemas["AccountPeriodPatch"]
    assert set(schemas["AccountPeriodCurrentOut"]["properties"]) == (
        CURRENT_PERIOD_KEYS
    )
    for name in ("AccountPeriodEndedOut", "AccountPeriodClosedOut"):
        assert set(schemas[name]["properties"]) == COMMON_PERIOD_KEYS
    for name in (
        "AccountPeriodCreate",
        "AccountPeriodPatch",
        "AccountPeriodCurrentOut",
        "AccountPeriodEndedOut",
        "AccountPeriodClosedOut",
    ):
        assert REMOVED_PERIOD_MEMBERS.isdisjoint(schemas[name]["properties"])
    assert "planned_amount" in schemas["PlanOccurrenceOut"]["properties"]
    for name in (
        "OperationsSingleIn",
        "TransferIn",
        "ExchangeIn",
        "TransactionPatch",
        "DeleteTransactionIn",
        "OperationsUndoIn",
        "AssignAccountIn",
    ):
        assert "confirm_ended_period" in schemas[name]["properties"]


async def test_every_period_route_uses_only_final_lifecycle_shapes(client):
    await register(client)
    account = await create_account(client, "Route shapes USD", "USD", "100")
    today = local_today()
    created = await client.post(
        f"/api/v1/accounts/{account['id']}/periods",
        json={"end_date": (today + timedelta(days=2)).isoformat()},
    )
    assert created.status_code == 201, created.text
    period_id = created.json()["id"]
    current_responses = [
        created,
        await client.get(f"/api/v1/accounts/{account['id']}/periods/current"),
        await client.get(f"/api/v1/account-periods/{period_id}"),
        await client.patch(
            f"/api/v1/account-periods/{period_id}",
            json={"end_date": (today + timedelta(days=3)).isoformat()},
        ),
    ]
    for response in current_responses:
        assert response.status_code in {200, 201}, response.text
        assert set(response.json()) == CURRENT_PERIOD_KEYS
    listed = await client.get(f"/api/v1/accounts/{account['id']}/periods")
    assert listed.status_code == 200
    assert [set(item) for item in listed.json()] == [CURRENT_PERIOD_KEYS]

    closed = await client.post(f"/api/v1/account-periods/{period_id}/close")
    assert closed.status_code == 200, closed.text
    assert set(closed.json()) == COMMON_PERIOD_KEYS
    assert closed.json()["status"] == "closed"
    detail = await client.get(f"/api/v1/account-periods/{period_id}")
    assert set(detail.json()) == COMMON_PERIOD_KEYS

    ended_account = await create_account(client, "Ended route shape USD", "USD", "5")
    ended = await client.post(
        f"/api/v1/accounts/{ended_account['id']}/periods",
        json={
            "start_date": (today - timedelta(days=3)).isoformat(),
            "end_date": (today - timedelta(days=1)).isoformat(),
        },
    )
    assert ended.status_code == 201, ended.text
    assert set(ended.json()) == COMMON_PERIOD_KEYS
    assert ended.json()["status"] == "ended"


def test_desktop_period_consumer_has_no_removed_contract_references():
    html = Path("app/static/index.html").read_text()
    javascript = Path("app/static/app.js").read_text()
    for removed in (
        "period-funding",
        "operations-period-remaining",
        "operations-period-planned",
    ):
        assert removed not in html
        assert removed not in javascript
    for removed in (
        "period.funding_amount",
        "period.remaining",
        "current.remaining",
        "current.planned",
        "This period needs explicit confirmation. Continue?",
    ):
        assert removed not in javascript
    assert "operations-period-current-balance" in html
    assert "current.current_balance" in javascript
    assert "period.opening_balance" in javascript
    assert "period.closing_balance" in javascript
    assert "occurrence.planned_amount" in javascript
    assert "apiWithEndedPeriodConfirmation" in javascript
