import asyncio
from datetime import datetime, timedelta
from decimal import Decimal

import pytest_asyncio
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.transfer_quotes as transfer_quotes
from app.assets import seed_default_assets
from app.db import get_session
from app.main import app
from app.models import (
    Account,
    Asset,
    Base,
    ExchangeRate,
    ManualValuationRate,
    OperationsUndoState,
    Transaction,
    TransactionLeg,
    TransferQuote,
    Workspace,
)
from tests.conftest import register
from tests.test_ledger_v2 import create_account
from tests.test_periods_v2 import create_period, local_today
from tests.test_sharing_v2 import accept, invitation, login
from tests.test_transfer_quotes_v21 import quote, save_rate


EXECUTE_PATH = "/api/v1/operations/transfer/quotes/{quote_id}/execute"


async def counts(client):
    async with client._finapp_test_sessions() as session:
        return {
            "transactions": await session.scalar(select(func.count(Transaction.id))),
            "legs": await session.scalar(select(func.count(TransactionLeg.id))),
            "rates": await session.scalar(select(func.count(ExchangeRate.id))),
            "undo": await session.scalar(
                select(func.count(OperationsUndoState.id))
            ),
        }


async def execute(client, quote_id: int, body=None):
    return await client.post(
        EXECUTE_PATH.format(quote_id=quote_id),
        json={} if body is None else body,
    )


async def quote_row(client, quote_id: int) -> TransferQuote:
    async with client._finapp_test_sessions() as session:
        row = await session.get(TransferQuote, quote_id)
        assert row is not None
        session.expunge(row)
        return row


async def net_worth(client) -> Decimal:
    response = await client.get("/api/v1/accounts/summary")
    assert response.status_code == 200, response.text
    return Decimal(response.json()["net_worth"])


async def test_execute_openapi_strict_body_and_path_are_mutation_neutral(client):
    await register(client)
    source = await create_account(client, "Execute strict source", "USD")
    target = await create_account(client, "Execute strict target", "USD")
    created = await quote(client, source, target, "1")
    assert created.status_code == 201, created.text
    quote_id = created.json()["id"]

    openapi = (await client.get("/openapi.json")).json()
    operation = openapi["paths"][EXECUTE_PATH]["post"]
    assert set(operation["responses"]) >= {"201", "404", "409", "422"}
    parameter = operation["parameters"][0]
    assert parameter["name"] == "quote_id"
    assert parameter["required"] is True
    assert parameter["schema"]["type"] == "integer"
    assert parameter["schema"]["exclusiveMinimum"] == 0
    request_ref = operation["requestBody"]["content"]["application/json"][
        "schema"
    ]["$ref"]
    schema = openapi["components"]["schemas"][request_ref.rsplit("/", 1)[1]]
    assert schema["additionalProperties"] is False
    assert set(schema["properties"]) == {
        "local_date",
        "occurred_at",
        "note",
        "counterparty",
        "confirm_ended_period",
    }
    assert schema.get("required", []) == []
    assert schema["properties"]["local_date"]["anyOf"][0] == {
        "type": "string",
        "format": "date",
    }
    assert schema["properties"]["occurred_at"]["anyOf"][0] == {
        "type": "string",
        "format": "date-time",
    }
    for field in ("local_date", "occurred_at", "note", "counterparty"):
        assert {branch["type"] for branch in schema["properties"][field]["anyOf"]} == {
            "string",
            "null",
        }
        assert schema["properties"][field]["default"] is None
    assert schema["properties"]["note"]["anyOf"][0]["maxLength"] == 2000
    assert schema["properties"]["counterparty"]["anyOf"][0]["maxLength"] == 160
    assert schema["properties"]["confirm_ended_period"]["default"] is False
    response_ref = operation["responses"]["201"]["content"]["application/json"][
        "schema"
    ]["$ref"]
    assert response_ref.endswith("/TransactionOut")

    before = await counts(client)
    route = EXECUTE_PATH.format(quote_id=quote_id)
    invalid = [
        None,
        [],
        {"unknown": True},
        {"note": "n" * 2001},
        {"counterparty": "c" * 161},
        {"confirm_ended_period": "true"},
        {"local_date": 0},
        {"occurred_at": 0},
        {"note": 1},
        {"counterparty": True},
        {"from_amount": "1"},
    ]
    assert (await client.post(route)).status_code == 422
    for body in invalid:
        response = await client.post(route, json=body)
        assert response.status_code == 422, (body, response.text)
    assert (await client.post(EXECUTE_PATH.format(quote_id=0), json={})).status_code == 422
    assert await counts(client) == before
    assert (await quote_row(client, quote_id)).status == "open"


async def test_identity_execution_is_atomic_undoable_and_permanently_single_use(
    client, monkeypatch
):
    await register(client)
    source = await create_account(client, "Execute source USD", "USD", "100")
    target = await create_account(client, "Execute target USD", "USD", "25")
    created_at = datetime(2026, 8, 11, 12, 0, 0)
    monkeypatch.setattr(transfer_quotes, "utcnow", lambda: created_at)
    created = await quote(client, source, target, "10.5")
    assert created.status_code == 201, created.text
    quote_id = created.json()["id"]
    capital_before = await net_worth(client)
    before = await counts(client)

    executed_at = created_at + timedelta(minutes=1)
    monkeypatch.setattr(transfer_quotes, "utcnow", lambda: executed_at)
    response = await execute(
        client,
        quote_id,
        {
            "local_date": "2026-08-11",
            "occurred_at": "2026-08-11T12:00:30Z",
            "note": "Bound quote",
            "counterparty": "Self",
        },
    )
    assert response.status_code == 201, response.text
    transaction = response.json()
    assert transaction["type"] == "transfer"
    assert transaction["origin"] == "operations"
    assert transaction["note"] == "Bound quote"
    assert transaction["counterparty"] == "Self"
    assert transaction["local_date"] == "2026-08-11"
    assert {
        (leg["account_id"], Decimal(leg["amount"]))
        for leg in transaction["legs"]
    } == {(source["id"], Decimal("-10.5")), (target["id"], Decimal("10.5"))}
    assert await net_worth(client) == capital_before
    after = await counts(client)
    assert after["transactions"] == before["transactions"] + 1
    assert after["legs"] == before["legs"] + 2
    assert after["rates"] == before["rates"]
    assert after["undo"] == before["undo"] + 2
    stored = await quote_row(client, quote_id)
    assert stored.status == "executed"
    assert stored.executed_at == executed_at
    assert stored.executed_transaction_id == transaction["id"]

    repeated = await execute(client, quote_id)
    assert repeated.status_code == 409
    assert repeated.json() == {"detail": "Transfer quote has already been executed"}
    undone = await client.post(
        f"/api/v1/operations/accounts/{source['id']}/undo",
        json={"transaction_id": transaction["id"]},
    )
    assert undone.status_code == 200, undone.text
    assert undone.json()["status"] == "deleted"
    assert (await quote_row(client, quote_id)).executed_transaction_id == transaction["id"]
    assert (await execute(client, quote_id)).json() == {
        "detail": "Transfer quote has already been executed"
    }


async def test_cross_asset_execution_uses_captured_amounts_and_stales_dependencies(
    client, monkeypatch
):
    context = await register(client)
    source = await create_account(client, "Execute source ETH", "ETH", "2")
    target = await create_account(client, "Execute target BTC", "BTC", "1")
    await save_rate(client, context["workspace"]["id"], "ETH", "2000")
    await save_rate(client, context["workspace"]["id"], "BTC", "40000")
    fixed = datetime(2026, 8, 11, 13, 0, 0)
    monkeypatch.setattr(transfer_quotes, "utcnow", lambda: fixed)
    created = await quote(client, source, target, "1")
    assert created.status_code == 201, created.text
    assert created.json()["to_amount"] == "0.05"
    capital_before = await net_worth(client)

    response = await execute(client, created.json()["id"])
    assert response.status_code == 201, response.text
    transaction = response.json()
    assert transaction["type"] == "exchange"
    assert {
        (leg["account_id"], Decimal(leg["amount"]))
        for leg in transaction["legs"]
    } == {(source["id"], Decimal("-1")), (target["id"], Decimal("0.05"))}
    assert await net_worth(client) == capital_before
    async with client._finapp_test_sessions() as session:
        rates = list(
            (
                await session.execute(
                    select(ExchangeRate).where(
                        ExchangeRate.source_transaction_id == transaction["id"]
                    )
                )
            ).scalars()
        )
    assert {(rate.base_asset_id, rate.quote_asset_id, Decimal(rate.rate)) for rate in rates} == {
        (source["asset"]["id"], target["asset"]["id"], Decimal("0.05")),
        (target["asset"]["id"], source["asset"]["id"], Decimal("20")),
    }

    stale_quote = (await quote(client, source, target, "0.5")).json()
    before = await counts(client)
    await save_rate(client, context["workspace"]["id"], "ETH", "2100")
    stale = await execute(client, stale_quote["id"])
    assert stale.status_code == 409
    assert stale.json() == {"detail": "Transfer quote is stale"}
    assert await counts(client) == before
    assert (await quote_row(client, stale_quote["id"])).status == "open"

    current_quote = (await quote(client, source, target, "0.5")).json()
    async with client._finapp_test_sessions() as session:
        workspace = await session.get(Workspace, context["workspace"]["id"])
        btc = await session.get(Asset, target["asset"]["id"])
        assert workspace is not None and btc is not None
        workspace.base_asset_id = btc.id
        await session.commit()
    switched = await execute(client, current_quote["id"])
    assert switched.status_code == 409
    assert switched.json() == {"detail": "Transfer quote is stale"}
    async with client._finapp_test_sessions() as session:
        workspace = await session.get(Workspace, context["workspace"]["id"])
        usd = (
            await session.execute(select(Asset).where(Asset.code == "USD"))
        ).scalar_one()
        assert workspace is not None
        workspace.base_asset_id = usd.id
        await session.commit()
    switched_back = await execute(client, current_quote["id"])
    assert switched_back.status_code == 201, switched_back.text

    deleted_quote = (await quote(client, source, target, "0.5")).json()
    async with client._finapp_test_sessions() as session:
        target_rate = (
            await session.execute(
                select(ManualValuationRate).where(
                    ManualValuationRate.workspace_id == context["workspace"]["id"],
                    ManualValuationRate.asset_id == target["asset"]["id"],
                )
            )
        ).scalar_one()
        await session.delete(target_rate)
        await session.commit()
    deleted = await execute(client, deleted_quote["id"])
    assert deleted.status_code == 409
    assert deleted.json() == {"detail": "Transfer quote is stale"}

    monkeypatch.setattr(
        transfer_quotes,
        "utcnow",
        lambda: fixed + timedelta(minutes=6),
    )
    executed_wins = await execute(client, created.json()["id"])
    assert executed_wins.json() == {
        "detail": "Transfer quote has already been executed"
    }


async def test_expiry_precedes_stale_and_same_asset_legacy_is_stale(client, monkeypatch):
    context = await register(client)
    eth = await create_account(client, "Expiry ETH", "ETH")
    btc = await create_account(client, "Expiry BTC", "BTC")
    other_eth = await create_account(client, "Legacy ETH", "ETH")
    await save_rate(client, context["workspace"]["id"], "ETH", "2000")
    await save_rate(client, context["workspace"]["id"], "BTC", "40000")
    fixed = datetime(2026, 8, 11, 14, 0, 0)
    monkeypatch.setattr(transfer_quotes, "utcnow", lambda: fixed)
    expiring = (await quote(client, eth, btc, "1")).json()
    after_boundary = (await quote(client, eth, btc, "1")).json()
    just_before = (await quote(client, eth, other_eth, "1")).json()
    identity = (await quote(client, eth, other_eth, "1")).json()
    monkeypatch.setattr(
        transfer_quotes,
        "utcnow",
        lambda: fixed + timedelta(minutes=5) - timedelta(microseconds=1),
    )
    before = await execute(client, just_before["id"])
    assert before.status_code == 201, before.text

    await save_rate(client, context["workspace"]["id"], "ETH", "2100")
    monkeypatch.setattr(
        transfer_quotes,
        "utcnow",
        lambda: fixed + timedelta(minutes=5),
    )
    counts_at_boundary = await counts(client)
    expired = await execute(client, expiring["id"])
    assert expired.status_code == 409
    assert expired.json() == {"detail": "Transfer quote has expired"}
    assert await counts(client) == counts_at_boundary
    assert (await quote_row(client, expiring["id"])).status == "open"

    monkeypatch.setattr(
        transfer_quotes,
        "utcnow",
        lambda: fixed + timedelta(minutes=5, microseconds=1),
    )
    counts_after_boundary = await counts(client)
    after = await execute(client, after_boundary["id"])
    assert after.status_code == 409
    assert after.json() == {"detail": "Transfer quote has expired"}
    assert await counts(client) == counts_after_boundary
    assert (await quote_row(client, after_boundary["id"])).status == "open"

    async with client._finapp_test_sessions() as session:
        rate = (
            await session.execute(
                select(ManualValuationRate).where(
                    ManualValuationRate.workspace_id == context["workspace"]["id"],
                    ManualValuationRate.asset_id == eth["asset"]["id"],
                )
            )
        ).scalar_one()
        rate.direction = "main_to_asset_legacy"
        await session.commit()
    monkeypatch.setattr(
        transfer_quotes,
        "utcnow",
        lambda: fixed + timedelta(minutes=1),
    )
    legacy = await execute(client, identity["id"])
    assert legacy.status_code == 409
    assert legacy.json() == {"detail": "Transfer quote is stale"}


async def test_permission_and_period_failures_leave_quote_retryable(client):
    context = await register(client)
    source = await create_account(client, "Guarded source USD", "USD", "100")
    target = await create_account(client, "Guarded target USD", "USD", "0")
    created = (await quote(client, source, target, "10")).json()
    eth = await create_account(client, "Private source ETH", "ETH")
    btc = await create_account(client, "Private target BTC", "BTC")
    await save_rate(client, context["workspace"]["id"], "ETH", "2000")
    await save_rate(client, context["workspace"]["id"], "BTC", "40000")
    private_cross = (await quote(client, eth, btc, "1")).json()
    tokens = [
        await invitation(client, source["id"], "editor"),
        await invitation(client, target["id"], "editor"),
    ]
    await register(client, "bob")
    for token in tokens:
        await accept(client, token)
    hidden = await execute(client, created["id"])
    assert hidden.status_code == 404
    assert hidden.json() == {"detail": "Transfer quote not found"}
    before_private_cross = await counts(client)
    hidden_cross = await execute(client, private_cross["id"])
    assert hidden_cross.status_code == 404
    assert hidden_cross.json() == {"detail": "Transfer quote not found"}
    assert await counts(client) == before_private_cross
    assert (await quote_row(client, private_cross["id"])).status == "open"

    await login(client, "alice")
    async with client._finapp_test_sessions() as session:
        account = await session.get(Account, source["id"])
        assert account is not None
        account.archived_at = datetime(2026, 8, 11, 15, 0, 0)
        await session.commit()
    archived = await execute(client, created["id"])
    assert archived.status_code == 404
    assert archived.json() == {"detail": "Account not found"}
    async with client._finapp_test_sessions() as session:
        account = await session.get(Account, source["id"])
        assert account is not None
        account.archived_at = None
        await session.commit()

    today = local_today()
    await create_period(
        client,
        source["id"],
        start=today - timedelta(days=10),
        end=today - timedelta(days=5),
    )
    before = await counts(client)
    historical = (today - timedelta(days=7)).isoformat()
    rejected = await execute(client, created["id"], {"local_date": historical})
    assert rejected.status_code == 409
    assert rejected.json() == {
        "detail": "Ended account period change requires explicit confirmation"
    }
    assert await counts(client) == before
    assert (await quote_row(client, created["id"])).status == "open"
    corrected = await execute(
        client,
        created["id"],
        {"local_date": historical, "confirm_ended_period": True},
    )
    assert corrected.status_code == 201, corrected.text


async def test_failure_after_provisional_writes_rolls_back_for_retry(
    client, monkeypatch
):
    await register(client)
    source = await create_account(client, "Rollback source USD", "USD")
    target = await create_account(client, "Rollback target USD", "USD")
    created = (await quote(client, source, target, "1")).json()
    before = await counts(client)
    original = transfer_quotes.record_undo_candidate

    async def injected_failure(session, transaction, user):
        await original(session, transaction, user)
        raise RuntimeError("injected failure after provisional writes")

    monkeypatch.setattr(
        transfer_quotes,
        "record_undo_candidate",
        injected_failure,
    )
    with pytest.raises(RuntimeError, match="injected failure"):
        await execute(client, created["id"])
    assert await counts(client) == before
    assert (await quote_row(client, created["id"])).status == "open"

    monkeypatch.setattr(transfer_quotes, "record_undo_candidate", original)
    corrected = await execute(client, created["id"])
    assert corrected.status_code == 201, corrected.text


@pytest_asyncio.fixture
async def concurrent_client(tmp_path):
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'quote-race.db'}",
        connect_args={"timeout": 10},
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        await seed_default_assets(session)

    async def override_session():
        async with sessions() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        client._finapp_test_sessions = sessions
        yield client
    app.dependency_overrides.clear()
    await engine.dispose()


async def test_concurrent_execution_has_one_database_winner(concurrent_client):
    client = concurrent_client
    await register(client)
    source = await create_account(client, "Race source USD", "USD")
    target = await create_account(client, "Race target USD", "USD")
    created = await quote(client, source, target, "1")
    assert created.status_code == 201, created.text
    before = await counts(client)
    route = EXECUTE_PATH.format(quote_id=created.json()["id"])

    first, second = await asyncio.gather(
        client.post(route, json={}),
        client.post(route, json={}),
    )
    assert sorted((first.status_code, second.status_code)) == [201, 409]
    loser = first if first.status_code == 409 else second
    assert loser.json() == {"detail": "Transfer quote has already been executed"}
    after = await counts(client)
    assert after["transactions"] == before["transactions"] + 1
    assert after["legs"] == before["legs"] + 2
    assert after["undo"] == before["undo"] + 2
    stored = await quote_row(client, created.json()["id"])
    assert stored.status == "executed"
    assert stored.executed_transaction_id is not None
