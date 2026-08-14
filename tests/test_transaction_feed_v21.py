from base64 import urlsafe_b64encode
from datetime import date
from decimal import Decimal
import json

from sqlalchemy import func, select

from app.models import PlanOccurrence, Transaction, TransactionLeg
from tests.conftest import register, seed_unassigned_transaction
from tests.test_ledger_v2 import create_account
from tests.test_plan_v2 import create_rule, occurrences_for_rule
from tests.test_sharing_v2 import accept, invitation, login


FEED = "/api/v1/transaction-feed"


async def domain_counts(client):
    async with client._finapp_test_sessions() as session:
        return (
            await session.scalar(select(func.count(Transaction.id))),
            await session.scalar(select(func.count(TransactionLeg.id))),
            await session.scalar(select(func.count(PlanOccurrence.id))),
        )


async def spend(client, account_id: int, amount: str, day: str, moment: str):
    response = await client.post(
        "/api/v1/operations/spend",
        json={
            "account_id": account_id,
            "amount": amount,
            "local_date": day,
            "occurred_at": moment,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_feed_openapi_and_strict_query_contract_are_frozen(client):
    await register(client)
    account = await create_account(client, "Feed strict USD", "USD")
    await spend(client, account["id"], "1", "2026-08-10", "2026-08-10T10:00:00Z")
    await spend(client, account["id"], "2", "2026-08-09", "2026-08-09T10:00:00Z")
    before = await domain_counts(client)

    openapi = (await client.get("/openapi.json")).json()
    operation = openapi["paths"][FEED]["get"]
    parameters = {
        item["name"]: item
        for item in operation["parameters"]
        if item["in"] == "query"
    }
    assert set(parameters) == {"filter", "cursor", "limit"}
    assert parameters["filter"]["schema"]["default"] == "all"
    assert set(parameters["filter"]["schema"]["enum"]) == {
        "all",
        "income",
        "expense",
        "transfer",
        "planned",
    }
    assert parameters["limit"]["schema"]["minimum"] == 1
    assert parameters["limit"]["schema"]["maximum"] == 100
    response_ref = operation["responses"]["200"]["content"]["application/json"][
        "schema"
    ]["$ref"]
    page = openapi["components"]["schemas"][response_ref.rsplit("/", 1)[1]]
    assert page["additionalProperties"] is False
    assert set(page["properties"]) == {"items", "next_cursor"}
    assert set(page["required"]) == set(page["properties"])
    assert {branch["type"] for branch in page["properties"]["next_cursor"]["anyOf"]} == {
        "string",
        "null",
    }
    assert {branch["type"] for branch in parameters["cursor"]["schema"]["anyOf"]} == {
        "string",
        "null",
    }
    item_union = page["properties"]["items"]["items"]
    item_ref = next(
        branch["$ref"]
        for branch in item_union["oneOf"]
        if branch["$ref"].endswith("/TransactionFeedTransactionOut")
    )
    item = openapi["components"]["schemas"][item_ref.rsplit("/", 1)[1]]
    assert item["additionalProperties"] is False
    assert set(item["required"]) == set(item["properties"])
    assert set(item["properties"]) == {
        "kind",
        "key",
        "financial_date",
        "mobile_type",
        "transaction_type",
        "transaction",
    }
    assert item["properties"]["kind"]["const"] == "transaction"
    assert set(item["properties"]["mobile_type"]["enum"]) == {
        "income",
        "expense",
        "transfer",
        "adjustment",
    }
    assert set(item["properties"]["transaction_type"]["enum"]) == {
        "income",
        "expense",
        "transfer",
        "exchange",
        "adjustment",
    }
    assert item["properties"]["transaction"]["$ref"].endswith("/TransactionOut")

    detail = openapi["paths"][f"{FEED}/transaction/{{transaction_id}}"]["get"]
    path_parameter = next(
        parameter for parameter in detail["parameters"] if parameter["in"] == "path"
    )
    assert path_parameter["name"] == "transaction_id"
    assert path_parameter["required"] is True
    assert path_parameter["schema"]["type"] == "integer"
    assert path_parameter["schema"]["exclusiveMinimum"] == 0
    assert set(detail["responses"]) >= {"200", "404", "422"}
    assert detail["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": item_ref
    }

    valid_cursor = (await client.get(f"{FEED}?limit=1")).json()["next_cursor"]
    assert isinstance(valid_cursor, str)
    unsupported_payload = json.dumps(
        {
            "v": 2,
            "d": "2026-08-10",
            "s": "2026-08-10T10:00:00.000000",
            "k": 1,
            "i": 1,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    unsupported_cursor = urlsafe_b64encode(unsupported_payload).decode("ascii").rstrip("=")
    invalid_urls = [
        f"{FEED}?unknown=1",
        f"{FEED}?filter=all&filter=income",
        f"{FEED}?filter=unknown",
        f"{FEED}?limit=0",
        f"{FEED}?limit=101",
        f"{FEED}?limit=nope",
        f"{FEED}?cursor=not-a-cursor",
        f"{FEED}?cursor={valid_cursor[:2]}!{valid_cursor[2:]}",
        f"{FEED}?cursor={valid_cursor}===",
        f"{FEED}?cursor={unsupported_cursor}",
    ]
    for url in invalid_urls:
        response = await client.get(url)
        assert response.status_code == 422, (url, response.text)
    planned = await client.get(f"{FEED}?filter=planned")
    assert planned.status_code == 200
    assert planned.json() == {"items": [], "next_cursor": None}
    assert await domain_counts(client) == before


async def test_feed_orders_by_financial_date_and_pages_without_id_bias(client):
    await register(client)
    account = await create_account(client, "Feed order USD", "USD")
    oldest = await spend(
        client, account["id"], "1", "2026-08-09", "2026-08-11T12:00:00Z"
    )
    newest_date_older_id = await spend(
        client, account["id"], "2", "2026-08-11", "2026-08-10T10:00:00Z"
    )
    newest_date_newer_id = await spend(
        client, account["id"], "3", "2026-08-11", "2026-08-10T10:00:00Z"
    )
    middle = await spend(
        client, account["id"], "4", "2026-08-10", "2026-08-12T14:00:00Z"
    )
    expected = [
        newest_date_newer_id["id"],
        newest_date_older_id["id"],
        middle["id"],
        oldest["id"],
    ]

    first = (await client.get(f"{FEED}?limit=2")).json()
    assert [item["transaction"]["id"] for item in first["items"]] == expected[:2]
    assert isinstance(first["next_cursor"], str)
    second = (
        await client.get(f"{FEED}?limit=2&cursor={first['next_cursor']}")
    ).json()
    assert [item["transaction"]["id"] for item in second["items"]] == expected[2:]
    assert second["next_cursor"] is None

    moved = await client.patch(
        f"/api/v1/transactions/{oldest['id']}",
        json={"local_date": "2026-08-12"},
    )
    assert moved.status_code == 200, moved.text
    fresh = (await client.get(FEED)).json()
    assert fresh["items"][0]["transaction"]["id"] == oldest["id"]
    retimed = await client.patch(
        f"/api/v1/transactions/{newest_date_older_id['id']}",
        json={
            "occurred_at": "2026-08-10T11:00:00Z",
            "local_date": "2026-08-11",
        },
    )
    assert retimed.status_code == 200, retimed.text
    retimed_items = (await client.get(FEED)).json()["items"]
    assert [item["transaction"]["id"] for item in retimed_items[:3]] == [
        oldest["id"],
        newest_date_older_id["id"],
        newest_date_newer_id["id"],
    ]
    deleted = await client.post(f"/api/v1/transactions/{middle['id']}/delete")
    assert deleted.status_code == 200, deleted.text
    after_delete = (await client.get(FEED)).json()["items"]
    deleted_item = next(
        item for item in after_delete if item["transaction"]["id"] == middle["id"]
    )
    assert deleted_item["financial_date"] == "2026-08-10"
    assert deleted_item["transaction"]["status"] == "deleted"


async def test_feed_maps_all_domain_types_without_changing_nested_amounts(client):
    await register(client)
    usd = await create_account(client, "Feed mapped USD", "USD", "100")
    other_usd = await create_account(client, "Feed mapped target USD", "USD")
    vnd = await create_account(client, "Feed mapped VND", "VND")
    income = (
        await client.post(
            "/api/v1/operations/add-funds",
            json={"account_id": usd["id"], "amount": "5"},
        )
    ).json()
    expense = (
        await client.post(
            "/api/v1/operations/spend",
            json={"account_id": usd["id"], "amount": "2"},
        )
    ).json()
    transfer = (
        await client.post(
            "/api/v1/operations/transfer",
            json={
                "from_account_id": usd["id"],
                "to_account_id": other_usd["id"],
                "amount": "3",
            },
        )
    ).json()
    exchange = (
        await client.post(
            "/api/v1/operations/exchange",
            json={
                "from_account_id": usd["id"],
                "from_amount": "1",
                "to_account_id": vnd["id"],
                "to_amount": "25000",
            },
        )
    ).json()
    unassigned_id = await seed_unassigned_transaction(client, amount="7")

    items = (await client.get(FEED)).json()["items"]
    by_id = {item["transaction"]["id"]: item for item in items}
    assert by_id[income["id"]]["mobile_type"] == "income"
    assert by_id[expense["id"]]["mobile_type"] == "expense"
    assert by_id[transfer["id"]]["mobile_type"] == "transfer"
    assert by_id[exchange["id"]]["mobile_type"] == "transfer"
    assert by_id[exchange["id"]]["transaction_type"] == "exchange"
    assert {Decimal(leg["amount"]) for leg in by_id[exchange["id"]]["transaction"]["legs"]} == {
        Decimal("-1"),
        Decimal("25000"),
    }
    adjustments = [item for item in items if item["transaction_type"] == "adjustment"]
    assert adjustments and all(item["mobile_type"] == "adjustment" for item in adjustments)
    opening_adjustment = next(
        item
        for item in adjustments
        if item["transaction"]["legs"][0]["account_id"] == usd["id"]
    )
    assert [Decimal(leg["amount"]) for leg in opening_adjustment["transaction"]["legs"]] == [
        Decimal("100")
    ]
    assert by_id[unassigned_id]["transaction"]["status"] == "unassigned"
    transfer_filter = (await client.get(f"{FEED}?filter=transfer")).json()["items"]
    assert [item["transaction_type"] for item in transfer_filter] == ["transfer"]
    assert all(
        item["transaction_type"] == "expense"
        for item in (await client.get(f"{FEED}?filter=expense")).json()["items"]
    )
    income_filter = (await client.get(f"{FEED}?filter=income")).json()["items"]
    assert [item["transaction"]["id"] for item in income_filter] == [income["id"]]


async def test_feed_detail_preserves_plan_link_and_redacts_shared_rows(client):
    context = await register(client)
    shared = await create_account(client, "Feed shared USD", "USD", "100")
    private = await create_account(client, "Feed private USD", "USD")
    expense = (
        await client.post(
            "/api/v1/operations/spend",
            json={"account_id": shared["id"], "amount": "10"},
        )
    ).json()
    hidden = (
        await client.post(
            "/api/v1/operations/spend",
            json={"account_id": private["id"], "amount": "1"},
        )
    ).json()
    mixed = (
        await client.post(
            "/api/v1/operations/transfer",
            json={
                "from_account_id": shared["id"],
                "to_account_id": private["id"],
                "amount": "2",
            },
        )
    ).json()
    rule = (
        await create_rule(client, context["workspace"]["id"], amount="10")
    ).json()
    occurrence = (
        await occurrences_for_rule(client, context["workspace"]["id"], rule["id"])
    )[0]
    linked = await client.post(
        f"/api/v1/workspaces/{context['workspace']['id']}/plan-occurrences/"
        f"{occurrence['id']}/link-transaction",
        json={"transaction_id": expense["id"]},
    )
    assert linked.status_code == 200, linked.text
    owner_detail = await client.get(f"{FEED}/transaction/{expense['id']}")
    assert owner_detail.status_code == 200, owner_detail.text
    assert owner_detail.json()["transaction"]["plan_occurrence_id"] == occurrence["id"]

    token = await invitation(client, shared["id"], "viewer")
    await register(client, "bob")
    await accept(client, token)
    shared_items = (await client.get(FEED)).json()["items"]
    shared_ids = {item["transaction"]["id"] for item in shared_items}
    assert mixed["id"] in shared_ids
    assert hidden["id"] not in shared_ids
    mixed_item = next(item for item in shared_items if item["transaction"]["id"] == mixed["id"])
    assert mixed_item["transaction"]["has_hidden_legs"] is True
    assert len(mixed_item["transaction"]["legs"]) == 1
    assert mixed_item["transaction"]["plan_occurrence_id"] is None
    hidden_detail = await client.get(f"{FEED}/transaction/{hidden['id']}")
    assert hidden_detail.status_code == 404
    assert hidden_detail.json() == {"detail": "Feed item not found"}

    await login(client, "alice")
    compatibility = await client.get("/api/v1/transactions?limit=1")
    assert compatibility.status_code == 200
    assert set(compatibility.json()) == {"items", "next_cursor"}
