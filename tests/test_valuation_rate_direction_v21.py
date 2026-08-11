from decimal import Decimal
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import select

from app.models import Asset, ManualValuationRate, Workspace
from tests.conftest import register
from tests.test_ledger_v2 import create_account
from tests.test_sharing_v2 import accept, invitation, login


RATE_KEYS = {
    "id",
    "workspace_id",
    "from_asset",
    "to_asset",
    "rate",
    "source",
    "created_at",
    "updated_at",
}
ASSET_KEYS = {"id", "code", "name", "kind", "decimals", "is_active"}


def test_manual_rate_openapi_is_exact_asset_to_main_contract():
    from app.main import app

    schemas = app.openapi()["components"]["schemas"]
    request = schemas["ManualValuationRateUpsert"]
    response = schemas["ManualValuationRateOut"]

    assert set(request["properties"]) == {"rate"}
    assert request["required"] == ["rate"]
    assert request["properties"]["rate"]["type"] == "string"
    assert request["properties"]["rate"]["pattern"] == (
        r"^(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$"
    )
    assert request["additionalProperties"] is False
    assert set(response["properties"]) == RATE_KEYS
    assert set(response["required"]) == RATE_KEYS
    assert response["properties"]["rate"]["type"] == "string"
    assert response["properties"]["source"]["const"] == "manual"
    assert response["properties"]["id"]["type"] == "integer"
    assert response["properties"]["workspace_id"]["type"] == "integer"
    assert response["properties"]["from_asset"]["$ref"].endswith("/AssetOut")
    assert response["properties"]["to_asset"]["$ref"].endswith("/AssetOut")
    assert response["properties"]["created_at"] == {
        "format": "date-time",
        "title": "Created At",
        "type": "string",
    }
    assert response["properties"]["updated_at"] == {
        "format": "date-time",
        "title": "Updated At",
        "type": "string",
    }
    asset = schemas["AssetOut"]
    assert set(asset["properties"]) == ASSET_KEYS
    assert set(asset["required"]) == ASSET_KEYS
    public = str({"request": request, "response": response})
    for removed in (
        "displayed_rate",
        "effective_valuation_rate",
        "main_asset",
        "active",
    ):
        assert removed not in public


async def test_canonical_rate_round_trips_and_drives_exact_valuation(client):
    context = await register(client)
    workspace_id = context["workspace"]["id"]
    holding = await create_account(client, "Direction VND", "VND", "15258400")
    route = f"/api/v1/workspaces/{workspace_id}/valuation-rates/VND"

    sample = await client.put(route, json={"rate": "0.000038"})
    assert sample.status_code == 200, sample.text
    payload = sample.json()
    assert set(payload) == RATE_KEYS
    assert set(payload["from_asset"]) == ASSET_KEYS
    assert set(payload["to_asset"]) == ASSET_KEYS
    assert payload["from_asset"]["code"] == "VND"
    assert payload["to_asset"]["code"] == "USD"
    assert payload["rate"] == "0.000038"
    assert payload["source"] == "manual"
    assert isinstance(payload["id"], int)
    assert isinstance(payload["workspace_id"], int)
    datetime.fromisoformat(payload["created_at"])
    datetime.fromisoformat(payload["updated_at"])
    sample_account = (await client.get(f"/api/v1/accounts/{holding['id']}")).json()
    assert sample_account["valued_balance"] == "579.82"

    precise = await client.put(route, json={"rate": "0.000038034383082306"})
    assert precise.status_code == 200, precise.text
    assert precise.json()["id"] == payload["id"]
    assert precise.json()["created_at"] == payload["created_at"]
    assert precise.json()["rate"] == "0.000038034383082306"
    account = (await client.get(f"/api/v1/accounts/{holding['id']}")).json()
    assert account["valued_balance"] == "580.34"
    listed = (await client.get(
        f"/api/v1/workspaces/{workspace_id}/valuation-rates"
    )).json()
    assert listed == [precise.json()]

    async with client._finapp_test_sessions() as session:
        stored = await session.get(ManualValuationRate, payload["id"])
        assert stored is not None
        assert stored.rate_value == Decimal("0.000038034383082306")
        assert stored.direction == "asset_to_main"


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"rate": None},
        {"rate": False},
        {"rate": 1},
        {"rate": 0.000038},
        {"rate": "0"},
        {"rate": "-1"},
        {"rate": "+1"},
        {"rate": "1e-6"},
        {"rate": "NaN"},
        {"rate": "Infinity"},
        {"rate": "01"},
        {"rate": "1.0000000000000000000"},
        {"rate": "100000000000000000000"},
        {"displayed_rate": "2"},
        {"rate": "2", "displayed_rate": "2"},
        {"rate": "2", "effective_valuation_rate": "2"},
    ],
)
async def test_invalid_rate_inputs_are_422_and_mutation_neutral(client, body):
    context = await register(client)
    workspace_id = context["workspace"]["id"]
    route = f"/api/v1/workspaces/{workspace_id}/valuation-rates/VND"
    await create_account(client, "Rejected rate VND", "VND", "100")
    saved = await client.put(route, json={"rate": "0.00004"})
    assert saved.status_code == 200, saved.text
    before = saved.json()
    before_summary = (await client.get("/api/v1/accounts/summary")).json()

    rejected = await client.put(route, json=body)
    assert rejected.status_code == 422, rejected.text
    listed = (await client.get(
        f"/api/v1/workspaces/{workspace_id}/valuation-rates"
    )).json()
    assert listed == [before]
    assert (await client.get("/api/v1/accounts/summary")).json() == before_summary


@pytest.mark.parametrize(
    "value",
    [
        "1",
        "0.000000000000000001",
        "99999999999999999999.999999999999999999",
        "0.123456789012345678",
    ],
)
async def test_canonical_numeric_boundaries_round_trip(client, value):
    context = await register(client)
    workspace_id = context["workspace"]["id"]
    response = await client.put(
        f"/api/v1/workspaces/{workspace_id}/valuation-rates/ETH",
        json={"rate": value},
    )
    assert response.status_code == 200, response.text
    assert response.json()["rate"] == value


async def test_legacy_row_is_read_without_rewrite_and_converts_on_update(client):
    context = await register(client)
    workspace_id = context["workspace"]["id"]
    holding = await create_account(client, "Legacy VND", "VND", "15258400")

    async with client._finapp_test_sessions() as session:
        workspace = await session.get(Workspace, workspace_id)
        vnd = await session.scalar(select(Asset).where(Asset.code == "VND"))
        assert workspace is not None and vnd is not None
        legacy = ManualValuationRate(
            workspace_id=workspace_id,
            main_asset_id=workspace.base_asset_id,
            asset_id=vnd.id,
            rate_value=Decimal("26292"),
            direction="main_to_asset_legacy",
        )
        session.add(legacy)
        await session.commit()
        legacy_id = legacy.id

    route = f"/api/v1/workspaces/{workspace_id}/valuation-rates/VND"
    listed = (await client.get(
        f"/api/v1/workspaces/{workspace_id}/valuation-rates"
    )).json()
    assert listed[0]["id"] == legacy_id
    assert listed[0]["rate"] == "0.000038034383082306"
    account = (await client.get(f"/api/v1/accounts/{holding['id']}")).json()
    assert account["valued_balance"] == "580.34"

    updated = await client.put(route, json={"rate": "0.00004"})
    assert updated.status_code == 200, updated.text
    assert updated.json()["id"] == legacy_id
    async with client._finapp_test_sessions() as session:
        stored = await session.get(ManualValuationRate, legacy_id)
        assert stored is not None
        assert stored.rate_value == Decimal("0.00004")
        assert stored.direction == "asset_to_main"


@pytest.mark.parametrize("role", ["editor", "contributor", "viewer", None])
async def test_owner_rate_routes_are_private_for_every_shared_role_and_foreign_user(
    client, role
):
    alice = await register(client)
    workspace_id = alice["workspace"]["id"]
    shared = await create_account(client, "Private rate BTC", "BTC", "1")
    route = f"/api/v1/workspaces/{workspace_id}/valuation-rates/BTC"
    saved = await client.put(route, json={"rate": "50000"})
    assert saved.status_code == 200, saved.text
    token = await invitation(client, shared["id"], role) if role else None

    await register(client, "bob")
    if token is not None:
        await accept(client, token)
    for response in (
        await client.get(
            f"/api/v1/workspaces/{workspace_id}/valuation-rates"
        ),
        await client.put(route, json={"rate": "2"}),
        await client.delete(route),
    ):
        assert response.status_code == 404, response.text
        assert response.json() == {"detail": "Workspace not found"}

    await login(client, "alice")
    assert (await client.get(
        f"/api/v1/workspaces/{workspace_id}/valuation-rates"
    )).json() == [saved.json()]


async def test_unknown_and_inactive_source_assets_share_the_accepted_422(client):
    context = await register(client)
    workspace_id = context["workspace"]["id"]
    unknown = await client.put(
        f"/api/v1/workspaces/{workspace_id}/valuation-rates/NOPE",
        json={"rate": "1"},
    )
    assert unknown.status_code == 422
    assert unknown.json() == {"detail": "Unknown asset"}

    async with client._finapp_test_sessions() as session:
        trx = await session.scalar(select(Asset).where(Asset.code == "TRX"))
        assert trx is not None
        trx.is_active = False
        await session.commit()
    inactive = await client.put(
        f"/api/v1/workspaces/{workspace_id}/valuation-rates/TRX",
        json={"rate": "1"},
    )
    assert inactive.status_code == 422
    assert inactive.json() == {"detail": "Unknown asset"}


def test_manual_rate_source_has_no_float_or_old_unconditional_divide():
    root = Path(__file__).parents[1]
    source_files = {
        path: (root / path).read_text(encoding="utf-8")
        for path in ("app/schemas.py", "app/valuation_rates.py", "app/ledger.py")
    }
    sources = "\n".join(source_files.values())
    assert "float(" not in sources
    assert "manual_rate.displayed_rate" not in sources
    assert "decimal_quotient(balance, manual_rate" not in sources
    assert source_files["app/ledger.py"].count("rate.direction ==") == 2
    assert source_files["app/ledger.py"].count(
        "operation, value = manual_rate_semantics(rate)"
    ) == 2
    assert "decimal_product(balance, value)" in sources
