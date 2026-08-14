from tests.conftest import register


async def test_health_is_public(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_spa_entry_document_is_always_revalidated(client):
    """The entry document carries the asset version tokens.

    Served without `Cache-Control`, iOS Safari caches it heuristically and keeps
    loading the previous `style.css`/`app.js` after a deploy.
    """
    for path in ("/", "/index.html"):
        response = await client.get(path)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert response.headers["cache-control"] == "no-cache"
    # Versioned assets stay cacheable; their URL changes when they change.
    asset = await client.get("/style.css")
    assert asset.status_code == 200
    assert "cache-control" not in asset.headers


async def test_financial_foundation_requires_auth(client):
    assert (await client.get("/api/v1/assets")).status_code == 401
    assert (await client.get("/api/v1/workspaces")).status_code == 401


async def test_open_registration_creates_personal_workspace_and_session(client):
    context = await register(client)
    assert context["user"]["username"] == "alice"
    assert context["workspace"]["owner_user_id"] == context["user"]["id"]
    assert context["workspace"]["base_asset"]["code"] == "USD"
    assert (await client.get("/api/v1/auth/me")).status_code == 200
    assets = (await client.get("/api/v1/assets")).json()
    assert {item["code"] for item in assets} == {
        "VND", "USD", "RUB", "EUR", "USDT", "BTC", "ETH", "TRX"
    }


async def test_registration_validates_identity_timezone_and_base_asset(client):
    await register(client)
    duplicate = await client.post(
        "/api/v1/auth/register",
        json={"username": "ALICE", "password": "correct-horse-battery"},
    )
    assert duplicate.status_code == 409
    bad_zone = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "bob",
            "password": "correct-horse-battery",
            "timezone": "Mars/Olympus",
        },
    )
    assert bad_zone.status_code == 422
    bad_asset = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "carol",
            "password": "correct-horse-battery",
            "base_asset_code": "NOPE",
        },
    )
    assert bad_asset.status_code == 422


async def test_login_logout_and_bad_password(client):
    await register(client)
    assert (await client.post("/api/v1/auth/logout")).status_code == 204
    assert (await client.get("/api/v1/auth/me")).status_code == 401
    bad = await client.post(
        "/api/v1/auth/login",
        json={"username": "alice", "password": "definitely-not-correct"},
    )
    assert bad.status_code == 401
    good = await client.post(
        "/api/v1/auth/login",
        json={"username": "Alice", "password": "correct-horse-battery"},
    )
    assert good.status_code == 200


async def test_workspace_settings_and_cross_user_isolation(client):
    alice = await register(client)
    workspace_id = alice["workspace"]["id"]
    updated = await client.patch(
        f"/api/v1/workspaces/{workspace_id}",
        json={"name": "Nomad Finances", "base_asset_code": "VND"},
    )
    assert updated.status_code == 200
    assert updated.json()["base_asset"]["code"] == "VND"
    await client.post("/api/v1/auth/logout")
    await register(client, "bob")
    assert (await client.get(f"/api/v1/workspaces/{workspace_id}")).status_code == 404


async def test_assets_can_be_extended_and_codes_are_unique(client):
    await register(client)
    created = await client.post(
        "/api/v1/assets",
        json={"code": "sol", "name": "Solana", "kind": "crypto", "decimals": 9},
    )
    assert created.status_code == 201
    assert created.json()["code"] == "SOL"
    assert (
        await client.post(
            "/api/v1/assets",
            json={"code": "SOL", "name": "Again", "kind": "crypto", "decimals": 9},
        )
    ).status_code == 409
    invalid = await client.post(
        "/api/v1/assets",
        json={"code": "BAD", "name": "Bad", "kind": "crypto", "decimals": 19},
    )
    assert invalid.status_code == 422


async def test_category_crud_archive_and_uniqueness(client):
    context = await register(client)
    workspace_id = context["workspace"]["id"]
    route = f"/api/v1/workspaces/{workspace_id}/categories"
    created = await client.post(
        route,
        json={"name": "Restaurants", "kind": "expense", "icon": "fork"},
    )
    assert created.status_code == 201
    category_id = created.json()["id"]
    duplicate = await client.post(route, json={"name": " restaurants ", "kind": "both"})
    assert duplicate.status_code == 409
    patched = await client.patch(
        f"{route}/{category_id}", json={"name": "Dining", "color": "#ff9900"}
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "Dining"
    assert (await client.post(f"{route}/{category_id}/archive")).status_code == 200
    assert (await client.get(route)).json() == []
    assert len((await client.get(f"{route}?include_archived=true")).json()) == 1
