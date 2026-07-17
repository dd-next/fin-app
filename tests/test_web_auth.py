"""Local username/password and opaque-cookie authentication tests."""

import pytest


PASSWORD = "correct-horse-battery"


@pytest.fixture
def web_auth(monkeypatch):
    monkeypatch.setenv("WEB_AUTH_ENABLED", "true")
    monkeypatch.setenv("BOOTSTRAP_TOKEN", "setup-secret")


async def bootstrap(client):
    response = await client.post(
        "/auth/bootstrap",
        json={
            "username": "owner",
            "password": PASSWORD,
            "display_name": "Owner",
        },
        headers={"X-Bootstrap-Token": "setup-secret"},
    )
    assert response.status_code == 200
    return response


async def test_web_auth_gate_bootstrap_and_logout(client, web_auth):
    assert (await client.get("/auth/config")).json() == {"enabled": True}
    assert (await client.get("/period")).status_code == 401

    forbidden = await client.post(
        "/auth/bootstrap",
        json={"username": "owner", "password": PASSWORD},
    )
    assert forbidden.status_code == 403

    response = await bootstrap(client)
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert response.json()["display_name"] == "Owner"

    # The AsyncClient retained the cookie from bootstrap.
    assert (await client.get("/period")).status_code == 404
    assert (await client.get("/auth/me")).json()["username"] == "owner"

    duplicate = await client.post(
        "/auth/bootstrap",
        json={"username": "other", "password": PASSWORD},
        headers={"X-Bootstrap-Token": "setup-secret"},
    )
    assert duplicate.status_code == 409

    assert (await client.post("/auth/logout")).status_code == 204
    assert (await client.get("/period")).status_code == 401


async def test_login_success_and_failure(client, web_auth):
    await bootstrap(client)
    await client.post("/auth/logout")

    bad = await client.post(
        "/auth/login", json={"username": "OWNER", "password": "wrong-password"}
    )
    assert bad.status_code == 401

    ok = await client.post(
        "/auth/login", json={"username": "OWNER", "password": PASSWORD}
    )
    assert ok.status_code == 200
    assert ok.json()["username"] == "owner"
    assert (await client.get("/auth/me")).status_code == 200


async def test_auth_disabled_keeps_local_zero_setup(client, monkeypatch):
    monkeypatch.delenv("WEB_AUTH_ENABLED", raising=False)
    assert (await client.get("/auth/config")).json() == {"enabled": False}
    assert (await client.get("/period")).status_code == 404
