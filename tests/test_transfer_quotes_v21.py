from datetime import datetime
from decimal import Decimal, localcontext

import pytest
from sqlalchemy import func, select

import app.transfer_quotes as transfer_quotes
from app.models import (
    Account,
    AccountPeriod,
    ManualValuationRate,
    OperationsUndoState,
    Transaction,
    TransactionLeg,
    TransferQuote,
    Workspace,
)
from tests.conftest import register
from tests.test_ledger_v2 import create_account
from tests.test_sharing_v2 import accept, invitation, login


QUOTE_ROUTE = "/api/v1/operations/transfer/quotes"


async def save_rate(client, workspace_id: int, asset: str, rate: str):
    response = await client.put(
        f"/api/v1/workspaces/{workspace_id}/valuation-rates/{asset}",
        json={"rate": rate},
    )
    assert response.status_code == 200, response.text
    return response.json()


async def quote(client, source, target, amount: str):
    return await client.post(
        QUOTE_ROUTE,
        json={
            "from_account_id": source["id"],
            "to_account_id": target["id"],
            "from_amount": amount,
            "rate_source": "manual",
        },
    )


async def table_counts(client):
    sessions = client._finapp_test_sessions
    async with sessions() as session:
        return {
            "accounts": await session.scalar(select(func.count(Account.id))),
            "quotes": await session.scalar(select(func.count(TransferQuote.id))),
            "transactions": await session.scalar(select(func.count(Transaction.id))),
            "legs": await session.scalar(select(func.count(TransactionLeg.id))),
            "periods": await session.scalar(select(func.count(AccountPeriod.id))),
            "undo": await session.scalar(select(func.count(OperationsUndoState.id))),
            "rates": await session.scalar(
                select(func.count(ManualValuationRate.id))
            ),
        }


async def test_quote_openapi_and_strict_input_are_frozen(client):
    await register(client)
    source = await create_account(client, "Quote strict source USD", "USD")
    target = await create_account(client, "Quote strict target USD", "USD")

    openapi = (await client.get("/openapi.json")).json()
    operation = openapi["paths"][QUOTE_ROUTE]["post"]
    assert set(operation["responses"]) >= {"201", "422"}
    request_ref = operation["requestBody"]["content"]["application/json"]["schema"][
        "$ref"
    ]
    request_schema = openapi["components"]["schemas"][request_ref.rsplit("/", 1)[1]]
    assert request_schema["additionalProperties"] is False
    assert set(request_schema["properties"]) == {
        "from_account_id",
        "to_account_id",
        "from_amount",
        "rate_source",
    }
    assert set(request_schema["required"]) == set(request_schema["properties"])
    assert request_schema["properties"]["from_account_id"] == {
        "type": "integer",
        "exclusiveMinimum": 0,
        "title": "From Account Id",
    }
    assert request_schema["properties"]["from_amount"]["pattern"] == (
        r"^(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$"
    )
    assert request_schema["properties"]["rate_source"]["const"] == "manual"

    response_ref = operation["responses"]["201"]["content"]["application/json"][
        "schema"
    ]["$ref"]
    response_schema = openapi["components"]["schemas"][response_ref.rsplit("/", 1)[1]]
    assert response_schema["additionalProperties"] is False
    assert set(response_schema["required"]) == set(response_schema["properties"])
    assert set(response_schema["properties"]) == {
        "id",
        "workspace_id",
        "created_by_user_id",
        "from_account",
        "to_account",
        "from_amount",
        "to_amount",
        "rate",
        "rate_source",
        "created_at",
        "expires_at",
    }
    for field in ("id", "workspace_id", "created_by_user_id"):
        assert response_schema["properties"][field]["type"] == "integer"
        assert response_schema["properties"][field]["exclusiveMinimum"] == 0
    for field in ("from_amount", "to_amount", "rate"):
        assert response_schema["properties"][field]["type"] == "string"
        assert response_schema["properties"][field]["pattern"] == (
            r"^(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$"
        )
    assert response_schema["properties"]["rate_source"]["const"] == "manual"
    assert response_schema["properties"]["created_at"]["format"] == "date-time"
    assert response_schema["properties"]["expires_at"]["format"] == "date-time"

    account_ref = response_schema["properties"]["from_account"]["$ref"]
    assert response_schema["properties"]["to_account"]["$ref"] == account_ref
    account_schema = openapi["components"]["schemas"][account_ref.rsplit("/", 1)[1]]
    assert account_schema["additionalProperties"] is False
    assert set(account_schema["properties"]) == {"id", "name", "asset"}
    assert set(account_schema["required"]) == set(account_schema["properties"])
    assert account_schema["properties"]["id"] == {
        "type": "integer",
        "exclusiveMinimum": 0,
        "title": "Id",
    }
    assert account_schema["properties"]["name"]["type"] == "string"

    asset_ref = account_schema["properties"]["asset"]["$ref"]
    asset_schema = openapi["components"]["schemas"][asset_ref.rsplit("/", 1)[1]]
    assert asset_schema["additionalProperties"] is False
    assert set(asset_schema["properties"]) == {
        "id",
        "code",
        "name",
        "kind",
        "decimals",
        "is_active",
    }
    assert set(asset_schema["required"]) == set(asset_schema["properties"])
    assert asset_schema["properties"]["id"]["type"] == "integer"
    assert asset_schema["properties"]["code"]["type"] == "string"
    assert asset_schema["properties"]["name"]["type"] == "string"
    assert set(asset_schema["properties"]["kind"]["enum"]) == {"fiat", "crypto"}
    assert asset_schema["properties"]["decimals"]["type"] == "integer"
    assert asset_schema["properties"]["is_active"]["type"] == "boolean"

    valid = {
        "from_account_id": source["id"],
        "to_account_id": target["id"],
        "from_amount": "1",
        "rate_source": "manual",
    }
    invalid_bodies = [
        {key: value for key, value in valid.items() if key != "from_account_id"},
        {**valid, "extra": True},
        {**valid, "from_account_id": True},
        {**valid, "from_account_id": str(source["id"])},
        {**valid, "from_account_id": 0},
        {**valid, "to_account_id": False},
        {**valid, "from_amount": 1},
        {**valid, "from_amount": "1e2"},
        {**valid, "from_amount": "+1"},
        {**valid, "from_amount": "-1"},
        {**valid, "from_amount": "0"},
        {**valid, "from_amount": None},
        {**valid, "from_amount": "1.0000000000000000001"},
        {**valid, "from_amount": "100000000000000000000"},
        {**valid, "rate_source": "auto"},
    ]
    for body in invalid_bodies:
        response = await client.post(QUOTE_ROUTE, json=body)
        assert response.status_code == 422, (body, response.text)
    assert (await table_counts(client))["quotes"] == 0


async def test_identity_quote_is_normalized_immutable_and_write_neutral(
    client, monkeypatch
):
    context = await register(client)
    source = await create_account(client, "Quote identity source USD", "USD", "100")
    target = await create_account(client, "Quote identity target USD", "USD", "25")
    fixed = datetime(2026, 8, 11, 12, 0, 0)
    monkeypatch.setattr(transfer_quotes, "utcnow", lambda: fixed)
    before = await table_counts(client)

    response = await quote(client, source, target, "10.500")
    assert response.status_code == 201, response.text
    payload = response.json()
    assert set(payload) == {
        "id",
        "workspace_id",
        "created_by_user_id",
        "from_account",
        "to_account",
        "from_amount",
        "to_amount",
        "rate",
        "rate_source",
        "created_at",
        "expires_at",
    }
    assert payload["workspace_id"] == context["workspace"]["id"]
    assert payload["created_by_user_id"] == context["user"]["id"]
    assert payload["from_amount"] == payload["to_amount"] == "10.5"
    assert payload["rate"] == "1"
    assert payload["rate_source"] == "manual"
    assert payload["created_at"] == "2026-08-11T12:00:00"
    assert payload["expires_at"] == "2026-08-11T12:05:00"
    assert set(payload["from_account"]) == {"id", "name", "asset"}
    assert set(payload["from_account"]["asset"]) == {
        "id",
        "code",
        "name",
        "kind",
        "decimals",
        "is_active",
    }

    after = await table_counts(client)
    assert after == {**before, "quotes": before["quotes"] + 1}
    sessions = client._finapp_test_sessions
    async with sessions() as session:
        row = await session.get(TransferQuote, payload["id"])
        assert row is not None
        assert row.status == "open"
        assert row.from_amount == row.to_amount == Decimal("10.5")
        assert row.rate == Decimal("1")
        assert row.main_asset_id == source["asset"]["id"]
        assert row.source_manual_rate_id is None
        assert row.target_manual_rate_id is None
        assert row.executed_at is None
        assert row.executed_transaction_id is None


async def test_cross_asset_quotes_use_canonical_manual_paths_and_snapshots(client):
    context = await register(client)
    workspace_id = context["workspace"]["id"]
    usd = await create_account(client, "Quote main USD", "USD")
    vnd = await create_account(client, "Quote target VND", "VND")
    btc = await create_account(client, "Quote target BTC", "BTC")
    vnd_rate = await save_rate(client, workspace_id, "VND", "0.00004")
    btc_rate = await save_rate(client, workspace_id, "BTC", "60000")

    main_to_vnd = await quote(client, usd, vnd, "10")
    assert main_to_vnd.status_code == 201, main_to_vnd.text
    assert main_to_vnd.json()["to_amount"] == "250000"
    assert main_to_vnd.json()["rate"] == "25000"

    vnd_to_main = await quote(client, vnd, usd, "250000")
    assert vnd_to_main.status_code == 201, vnd_to_main.text
    assert vnd_to_main.json()["to_amount"] == "10"
    assert vnd_to_main.json()["rate"] == "0.00004"

    with localcontext() as context_decimal:
        context_decimal.prec = 6
        canonical_to_canonical = await quote(client, vnd, btc, "1500000000")
    assert canonical_to_canonical.status_code == 201, canonical_to_canonical.text
    assert canonical_to_canonical.json()["to_amount"] == "1"
    assert canonical_to_canonical.json()["rate"] == "0.000000000666666667"

    sessions = client._finapp_test_sessions
    async with sessions() as session:
        row = await session.get(
            TransferQuote, canonical_to_canonical.json()["id"]
        )
        assert row is not None
        assert row.source_manual_rate_id == vnd_rate["id"]
        assert row.source_manual_rate_value == Decimal("0.00004")
        assert row.source_manual_rate_direction == "asset_to_main"
        assert row.target_manual_rate_id == btc_rate["id"]
        assert row.target_manual_rate_value == Decimal("60000")
        snapshots = (
            row.source_manual_rate_value,
            row.source_manual_rate_updated_at,
            row.target_manual_rate_value,
            row.target_manual_rate_updated_at,
        )

    await save_rate(client, workspace_id, "VND", "0.00005")
    await client.delete(
        f"/api/v1/workspaces/{workspace_id}/valuation-rates/BTC"
    )
    async with sessions() as session:
        row = await session.get(
            TransferQuote, canonical_to_canonical.json()["id"]
        )
        assert row is not None
        assert (
            row.source_manual_rate_value,
            row.source_manual_rate_updated_at,
            row.target_manual_rate_value,
            row.target_manual_rate_updated_at,
        ) == snapshots


async def test_missing_repeating_underflow_and_aggregate_neutrality_failures_write_nothing(
    client
):
    context = await register(client)
    workspace_id = context["workspace"]["id"]
    rub = await create_account(client, "Quote source RUB", "RUB", "1")
    vnd = await create_account(client, "Quote target VND", "VND")
    btc = await create_account(client, "Quote source BTC", "BTC")
    eth = await create_account(client, "Quote target ETH", "ETH")
    await create_account(client, "Quote unrelated EUR", "EUR", "0.01")
    await save_rate(client, workspace_id, "EUR", "0.1")
    before = await table_counts(client)

    before_missing = await table_counts(client)
    missing = await quote(client, btc, eth, "1")
    assert missing.status_code == 422
    assert missing.json()["detail"] == (
        "Missing manual valuation rates for transfer quoting: "
        "BTC → USD, ETH → USD"
    )
    assert await table_counts(client) == before_missing

    await save_rate(client, workspace_id, "RUB", "0.014")
    await save_rate(client, workspace_id, "VND", "0.01")
    summary_before = (await client.get("/api/v1/accounts/summary")).json()
    rounded_only = await quote(client, rub, vnd, "1")
    assert rounded_only.status_code == 422
    assert rounded_only.json()["detail"] == (
        "Transfer amount cannot preserve Total capital"
    )
    assert (await client.get("/api/v1/accounts/summary")).json() == summary_before

    await save_rate(client, workspace_id, "BTC", "0.000000000000000001")
    await save_rate(client, workspace_id, "ETH", "10000000000000000000")
    with localcontext() as context_decimal:
        context_decimal.prec = 6
        underflow = await quote(client, btc, eth, "10000000000000000000")
    assert underflow.status_code == 422
    assert underflow.json()["detail"] == (
        "Exchange rate is below the supported 18-decimal precision"
    )

    after = await table_counts(client)
    assert after["quotes"] == before["quotes"]
    assert after["transactions"] == before["transactions"]
    assert after["legs"] == before["legs"]
    assert after["periods"] == before["periods"]
    assert after["undo"] == before["undo"]


async def test_quote_amount_product_quotient_and_rate_precision_boundaries(client):
    context = await register(client)
    workspace_id = context["workspace"]["id"]
    eth_source = await create_account(client, "Quote precision source ETH", "ETH")
    eth_target = await create_account(client, "Quote precision target ETH", "ETH")
    btc = await create_account(client, "Quote precision target BTC", "BTC")
    usd = await create_account(client, "Quote precision main USD", "USD")

    maximum = "99999999999999999999.123456789012345678"
    identity = await quote(client, eth_source, eth_target, maximum)
    assert identity.status_code == 201, identity.text
    assert identity.json()["from_amount"] == identity.json()["to_amount"] == maximum

    maximum_rate = "99999999999999999999"
    minimum_rate = "0.000000000000000001"
    await save_rate(client, workspace_id, "ETH", maximum_rate)
    product_overflow = await quote(
        client, eth_source, usd, "99999999999999999999"
    )
    assert product_overflow.status_code == 422
    assert product_overflow.json()["detail"] == (
        "Transfer calculation exceeds supported precision"
    )

    await save_rate(client, workspace_id, "BTC", minimum_rate)
    quotient_overflow = await quote(client, usd, btc, "99999999999999999999")
    assert quotient_overflow.status_code == 422
    assert quotient_overflow.json()["detail"] == (
        "Transfer calculation exceeds supported precision"
    )

    rate_overflow = await quote(
        client, eth_source, btc, "0.000000000000000001"
    )
    assert rate_overflow.status_code == 422
    assert rate_overflow.json()["detail"] == "Exchange rate has too many digits"

    await save_rate(client, workspace_id, "ETH", minimum_rate)
    zero_after_quantization = await quote(client, eth_source, usd, "1")
    assert zero_after_quantization.status_code == 422
    assert zero_after_quantization.json()["detail"] == "Amount must not be zero"

    assert (await table_counts(client))["quotes"] == 1


async def test_legacy_rows_require_explicit_owner_resave_for_identity_and_cross(client):
    context = await register(client)
    workspace_id = context["workspace"]["id"]
    vnd_source = await create_account(client, "Quote legacy source VND", "VND")
    vnd_target = await create_account(client, "Quote legacy target VND", "VND")
    usd = await create_account(client, "Quote legacy main USD", "USD")

    sessions = client._finapp_test_sessions
    async with sessions() as session:
        workspace = await session.get(Workspace, workspace_id)
        assert workspace is not None
        rate = ManualValuationRate(
            workspace_id=workspace_id,
            main_asset_id=workspace.base_asset_id,
            asset_id=vnd_source["asset"]["id"],
            rate_value=Decimal("25000"),
            direction="main_to_asset_legacy",
        )
        session.add(rate)
        await session.commit()

    for target in (vnd_target, usd):
        rejected = await quote(client, vnd_source, target, "25000")
        assert rejected.status_code == 422
        assert rejected.json()["detail"] == (
            "Manual valuation rate must be resaved before transfer quoting: VND → USD"
        )
    assert (await table_counts(client))["quotes"] == 0

    await save_rate(client, workspace_id, "VND", "0.00004")
    identity = await quote(client, vnd_source, vnd_target, "25000")
    cross = await quote(client, vnd_source, usd, "25000")
    assert identity.status_code == 201, identity.text
    assert cross.status_code == 201, cross.text
    assert cross.json()["to_amount"] == "1"


async def test_quote_is_owner_private_for_every_shared_role_and_unrelated_users(client):
    alice = await register(client)
    workspace_id = alice["workspace"]["id"]
    pairs = {}
    tokens = []
    for role in ("editor", "contributor", "viewer"):
        same_source = await create_account(
            client, f"Quote {role} same source USD", "USD"
        )
        same_target = await create_account(
            client, f"Quote {role} same target USD", "USD"
        )
        cross_source = await create_account(
            client, f"Quote {role} cross source USD", "USD"
        )
        cross_target = await create_account(
            client, f"Quote {role} cross target VND", "VND"
        )
        pairs[role] = (same_source, same_target, cross_source, cross_target)
        for account in pairs[role]:
            tokens.append(await invitation(client, account["id"], role))
    private_source = await create_account(client, "Quote private source USD", "USD")
    private_target = await create_account(client, "Quote private target USD", "USD")
    await save_rate(client, workspace_id, "VND", "0.00004")

    owner_same = await quote(client, private_source, private_target, "1")
    owner_cross = await quote(client, pairs["editor"][2], pairs["editor"][3], "1")
    assert owner_same.status_code == owner_cross.status_code == 201
    owner_quote_count = (await table_counts(client))["quotes"]

    await register(client, "bob")
    for token in tokens:
        await accept(client, token)
    for role, (same_source, same_target, cross_source, cross_target) in pairs.items():
        for source, target in (
            (same_source, same_target),
            (cross_source, cross_target),
        ):
            response = await quote(client, source, target, "1")
            assert response.status_code == 404, (role, response.text)
            assert response.json() == {"detail": "Workspace not found"}

    await register(client, "charlie")
    unrelated = await quote(client, private_source, private_target, "1")
    assert unrelated.status_code == 404
    assert unrelated.json() == {"detail": "Workspace not found"}
    unrelated_cross = await quote(
        client, pairs["editor"][2], pairs["editor"][3], "1"
    )
    assert unrelated_cross.status_code == 404
    assert unrelated_cross.json() == {"detail": "Workspace not found"}
    assert (await table_counts(client))["quotes"] == owner_quote_count


async def test_archived_distinct_and_source_precision_failures_are_neutral(client):
    await register(client)
    source = await create_account(client, "Quote validation source USD", "USD")
    target = await create_account(client, "Quote validation target USD", "USD")
    vnd = await create_account(client, "Quote validation VND", "VND")
    before = await table_counts(client)

    same = await quote(client, source, source, "1")
    assert same.status_code == 422
    assert same.json()["detail"] == "Transfer accounts must be distinct"

    bad_precision = await quote(client, vnd, source, "1.5")
    assert bad_precision.status_code == 422
    assert bad_precision.json()["detail"] == "VND supports at most 0 decimal places"

    archived = await client.post(f"/api/v1/accounts/{target['id']}/archive")
    assert archived.status_code == 200
    hidden = await quote(client, source, target, "1")
    assert hidden.status_code == 404
    assert hidden.json() == {"detail": "Workspace not found"}

    after = await table_counts(client)
    assert after["quotes"] == before["quotes"]
    assert after["transactions"] == before["transactions"]
    assert after["legs"] == before["legs"]
    assert after["periods"] == before["periods"]
    assert after["undo"] == before["undo"]
