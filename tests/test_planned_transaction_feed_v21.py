from base64 import urlsafe_b64encode
from datetime import UTC, date, datetime, time, timedelta
import json
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from app.models import (
    AccountPeriod,
    Asset,
    ExchangeRate,
    OperationsUndoState,
    PlanOccurrence,
    PlanRule,
    Transaction,
    TransactionLeg,
)
from tests.conftest import register
from tests.test_ledger_v2 import create_account
from tests.test_plan_v2 import create_rule, occurrences_for_rule
from tests.test_sharing_v2 import accept, invitation, login


FEED = "/api/v1/transaction-feed"


def day_boundary(day: date, timezone: str) -> str:
    return (
        datetime.combine(day, time.min, tzinfo=ZoneInfo(timezone))
        .astimezone(UTC)
        .isoformat()
        .replace("+00:00", "Z")
    )


async def domain_counts(client):
    async with client._finapp_test_sessions() as session:
        models = (
            PlanOccurrence,
            Transaction,
            TransactionLeg,
            ExchangeRate,
            AccountPeriod,
            OperationsUndoState,
        )
        counts = []
        for model in models:
            counts.append(await session.scalar(select(func.count(model.id))))
        return tuple(counts)


async def seed_unmaterialized_rule(client, context):
    async with client._finapp_test_sessions() as session:
        asset = (
            await session.execute(select(Asset).where(Asset.code == "USD"))
        ).scalar_one()
        rule = PlanRule(
            workspace_id=context["workspace"]["id"],
            created_by_user_id=context["user"]["id"],
            kind="required_expense",
            name="Unmaterialized",
            amount="12.5",
            asset_id=asset.id,
            recurrence="once",
            first_due_date=date.today(),
            is_required=True,
            is_active=True,
        )
        session.add(rule)
        await session.commit()
        return rule.id


async def test_planned_openapi_and_invalid_queries_precede_materialization(client):
    context = await register(client)
    rule_id = await seed_unmaterialized_rule(client, context)
    before = await domain_counts(client)

    unsupported = urlsafe_b64encode(
        json.dumps(
            {
                "v": 2,
                "d": date.today().isoformat(),
                "s": "2026-01-01T00:00:00.000000",
                "k": 0,
                "i": 1,
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    ).decode("ascii").rstrip("=")
    for url in (
        f"{FEED}?filter=planned&filter=all",
        f"{FEED}?unknown=1",
        f"{FEED}?cursor=bad!cursor",
        f"{FEED}?cursor={unsupported}",
    ):
        response = await client.get(url)
        assert response.status_code == 422, (url, response.text)
        assert await domain_counts(client) == before

    openapi = (await client.get("/openapi.json")).json()
    operation = openapi["paths"][FEED]["get"]
    filter_schema = next(
        item["schema"] for item in operation["parameters"] if item["name"] == "filter"
    )
    assert set(filter_schema["enum"]) == {
        "all",
        "income",
        "expense",
        "transfer",
        "planned",
    }
    page_ref = operation["responses"]["200"]["content"]["application/json"][
        "schema"
    ]["$ref"]
    page = openapi["components"]["schemas"][page_ref.rsplit("/", 1)[1]]
    union = page["properties"]["items"]["items"]
    assert union["discriminator"]["propertyName"] == "kind"
    assert set(union["discriminator"]["mapping"]) == {"transaction", "planned"}
    planned_ref = union["discriminator"]["mapping"]["planned"]
    planned = openapi["components"]["schemas"][planned_ref.rsplit("/", 1)[1]]
    assert planned["additionalProperties"] is False
    assert set(planned["required"]) == set(planned["properties"])
    assert set(planned["properties"]) == {
        "kind",
        "key",
        "financial_date",
        "mobile_type",
        "mobile_status",
        "occurrence",
    }
    assert planned["properties"]["kind"]["const"] == "planned"
    assert planned["properties"]["mobile_type"]["const"] == "planned"
    assert set(planned["properties"]["mobile_status"]["enum"]) == {
        "planned",
        "required",
        "overdue",
    }
    assert planned["properties"]["occurrence"]["$ref"].endswith(
        "/PlanOccurrenceOut"
    )
    detail = openapi["paths"][f"{FEED}/planned/{{occurrence_id}}"]["get"]
    path = next(item for item in detail["parameters"] if item["in"] == "path")
    assert path["schema"]["exclusiveMinimum"] == 0
    assert set(detail["responses"]) >= {"200", "404", "422"}
    detail_ref = detail["responses"]["200"]["content"]["application/json"][
        "schema"
    ]["$ref"]
    detail_schema = openapi["components"]["schemas"][detail_ref.rsplit("/", 1)[1]]
    assert detail_schema["additionalProperties"] is False
    assert set(detail_schema["required"]) == set(detail_schema["properties"])
    assert set(detail_schema["properties"]) == set(planned["properties"]) | {
        "available_actions"
    }
    actions = detail_schema["properties"]["available_actions"]
    assert [item["const"] for item in actions["prefixItems"]] == [
        "edit_rule",
        "skip",
        "link_transaction",
    ]

    valid = await client.get(f"{FEED}?filter=planned")
    assert valid.status_code == 200, valid.text
    assert [item["occurrence"]["plan_rule_id"] for item in valid.json()["items"]] == [
        rule_id
    ]


async def test_union_paginates_interleaved_items_without_ledger_mutation(client):
    context = await register(client)
    workspace_id = context["workspace"]["id"]
    account = await create_account(client, "Planned union USD", "USD")
    today_value = date.today()
    today = today_value.isoformat()
    transaction = (
        await client.post(
            "/api/v1/operations/spend",
            json={
                "account_id": account["id"],
                "amount": "3",
                "local_date": today,
                "occurred_at": day_boundary(
                    today_value, context["workspace"]["timezone"]
                ),
            },
        )
    ).json()
    optional_rule = (
        await create_rule(
            client,
            workspace_id,
            name="Optional",
            amount="5.25",
            is_required=False,
        )
    ).json()
    required_rule = (
        await create_rule(client, workspace_id, name="Required", amount="7.75")
    ).json()
    overdue_rule = (
        await create_rule(
            client,
            workspace_id,
            name="Overdue",
            amount="8.5",
            first_due_date=(today_value - timedelta(days=1)).isoformat(),
        )
    ).json()
    before_repeat = await domain_counts(client)

    expected_keys = []
    cursor = None
    while True:
        suffix = f"&cursor={cursor}" if cursor else ""
        page = (await client.get(f"{FEED}?limit=1{suffix}")).json()
        expected_keys.extend(item["key"] for item in page["items"])
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert len(expected_keys) == len(set(expected_keys)) == 4
    assert expected_keys[0] == f"transaction:{transaction['id']}"
    assert set(expected_keys[1:]) == {
        f"planned:{(await occurrences_for_rule(client, workspace_id, optional_rule['id']))[0]['id']}",
        f"planned:{(await occurrences_for_rule(client, workspace_id, required_rule['id']))[0]['id']}",
        f"planned:{(await occurrences_for_rule(client, workspace_id, overdue_rule['id']))[0]['id']}",
    }
    planned = (await client.get(f"{FEED}?filter=planned")).json()["items"]
    assert {item["mobile_status"] for item in planned} == {
        "planned",
        "required",
        "overdue",
    }
    assert all(item["kind"] == "planned" for item in planned)
    assert (await client.get(f"{FEED}?filter=expense")).json()["items"][0][
        "kind"
    ] == "transaction"
    await client.get(FEED)
    assert await domain_counts(client) == before_repeat


async def test_planned_detail_actions_and_existing_commands_change_fresh_feed(client):
    context = await register(client)
    workspace_id = context["workspace"]["id"]
    account = await create_account(client, "Planned actions USD", "USD", "100")
    skip_rule = (await create_rule(client, workspace_id, name="Skip me")).json()
    skipped = (await occurrences_for_rule(client, workspace_id, skip_rule["id"]))[0]
    detail = await client.get(f"{FEED}/planned/{skipped['id']}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["available_actions"] == [
        "edit_rule",
        "skip",
        "link_transaction",
    ]
    await client.post(
        f"/api/v1/workspaces/{workspace_id}/plan-occurrences/{skipped['id']}/skip"
    )
    assert (await client.get(f"{FEED}/planned/{skipped['id']}")).status_code == 404

    linked_rule = (
        await create_rule(
            client,
            workspace_id,
            name="Link me",
            default_from_account_id=account["id"],
        )
    ).json()
    occurrence = (await occurrences_for_rule(client, workspace_id, linked_rule["id"]))[0]
    transaction = (
        await client.post(
            "/api/v1/operations/spend",
            json={
                "account_id": account["id"],
                "amount": "10",
                "local_date": date.today().isoformat(),
                "occurred_at": day_boundary(
                    date.today(), context["workspace"]["timezone"]
                ),
            },
        )
    ).json()
    linked = await client.post(
        f"/api/v1/workspaces/{workspace_id}/plan-occurrences/{occurrence['id']}/link-transaction",
        json={"transaction_id": transaction["id"]},
    )
    assert linked.status_code == 200, linked.text
    assert (await client.get(f"{FEED}/planned/{occurrence['id']}")).status_code == 404
    deleted = await client.post(f"/api/v1/transactions/{transaction['id']}/delete")
    assert deleted.status_code == 200, deleted.text
    all_items = (await client.get(FEED)).json()["items"]
    keys = [item["key"] for item in all_items]
    assert f"transaction:{transaction['id']}" in keys
    assert f"planned:{occurrence['id']}" in keys
    assert keys.index(f"transaction:{transaction['id']}") < keys.index(
        f"planned:{occurrence['id']}"
    )
    deleted_item = next(item for item in all_items if item["key"] == f"transaction:{transaction['id']}")
    assert deleted_item["transaction"]["status"] == "deleted"

    archive_rule = (await create_rule(client, workspace_id, name="Archive me")).json()
    archived_occurrence = (
        await occurrences_for_rule(client, workspace_id, archive_rule["id"])
    )[0]
    await client.post(
        f"/api/v1/workspaces/{workspace_id}/plan-rules/{archive_rule['id']}/archive"
    )
    assert (
        await client.get(f"{FEED}/planned/{archived_occurrence['id']}")
    ).status_code == 404
    assert f"planned:{archived_occurrence['id']}" not in {
        item["key"] for item in (await client.get(FEED)).json()["items"]
    }


async def test_planned_rows_are_owner_private_while_shared_transactions_remain(client):
    context = await register(client)
    workspace_id = context["workspace"]["id"]
    shared = await create_account(client, "Planned private USD", "USD", "100")
    rule = (await create_rule(client, workspace_id, name="Owner only")).json()
    occurrence = (await occurrences_for_rule(client, workspace_id, rule["id"]))[0]
    transaction = (
        await client.post(
            "/api/v1/operations/spend",
            json={"account_id": shared["id"], "amount": "1"},
        )
    ).json()
    token = await invitation(client, shared["id"], "viewer")
    await register(client, "bob")
    await accept(client, token)
    assert (await client.get(f"{FEED}?filter=planned")).json()["items"] == []
    bob_keys = {item["key"] for item in (await client.get(FEED)).json()["items"]}
    assert f"transaction:{transaction['id']}" in bob_keys
    assert f"planned:{occurrence['id']}" not in bob_keys
    hidden = await client.get(f"{FEED}/planned/{occurrence['id']}")
    assert hidden.status_code == 404
    assert hidden.json() == {"detail": "Feed item not found"}

    await register(client, "charlie")
    assert (await client.get(f"{FEED}?filter=planned")).json()["items"] == []
    assert (await client.get(f"{FEED}/planned/{occurrence['id']}")).status_code == 404
    await login(client, "alice")
