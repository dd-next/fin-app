"""Personal/shared workspace membership, invite, and isolation tests."""

from datetime import date, timedelta

import pytest


OWNER_PASSWORD = "owner-password-123"
WIFE_PASSWORD = "wife-password-1234"


@pytest.fixture
def web_auth(monkeypatch):
    monkeypatch.setenv("WEB_AUTH_ENABLED", "true")
    monkeypatch.setenv("BOOTSTRAP_TOKEN", "setup-secret")


async def create_owner(client):
    response = await client.post(
        "/auth/bootstrap",
        json={
            "username": "owner",
            "password": OWNER_PASSWORD,
            "display_name": "Owner",
        },
        headers={"X-Bootstrap-Token": "setup-secret"},
    )
    assert response.status_code == 200


async def test_personal_shared_invite_and_cross_workspace_isolation(client, web_auth):
    await create_owner(client)
    workspaces = (await client.get("/workspaces")).json()
    assert workspaces == [
        {
            "id": 1,
            "name": "Personal",
            "kind": "personal",
            "timezone": "Asia/Ho_Chi_Minh",
            "role": "owner",
        }
    ]

    family = (await client.post("/workspaces", json={"name": "Family"})).json()
    family_id = family["id"]
    assert family["kind"] == "shared"

    invite_response = await client.post(f"/workspaces/{family_id}/invites")
    assert invite_response.status_code == 200
    token = invite_response.json()["token"]

    await client.post("/auth/logout")
    accepted = await client.post(
        f"/invites/{token}/accept",
        json={
            "username": "wife",
            "password": WIFE_PASSWORD,
            "display_name": "Wife",
        },
    )
    assert accepted.status_code == 200
    assert accepted.json()["workspace"]["id"] == family_id
    assert accepted.json()["workspace"]["role"] == "editor"

    wife_workspaces = (await client.get("/workspaces")).json()
    assert {w["name"] for w in wife_workspaces} == {"Wife's Personal", "Family"}

    # Wife cannot see the owner's personal workspace by changing the query id.
    denied = await client.get("/periods", params={"workspace_id": 1})
    assert denied.status_code == 404
    assert (await client.post(f"/workspaces/{family_id}/invites")).status_code == 403

    today = date.today()
    period = await client.post(
        "/periods",
        params={"workspace_id": family_id},
        json={
            "total_amount": "1000",
            "start_date": today.isoformat(),
            "end_date": (today + timedelta(days=9)).isoformat(),
        },
    )
    assert period.status_code == 200
    period_id = period.json()["period"]["id"]
    assert (
        await client.post(
            f"/periods/{period_id}/operations",
            params={"workspace_id": family_id},
            json={"amount": "75"},
        )
    ).status_code == 200

    await client.post("/auth/logout")
    await client.post(
        "/auth/login",
        json={"username": "owner", "password": OWNER_PASSWORD},
    )
    shared_ops = await client.get(
        f"/periods/{period_id}/operations", params={"workspace_id": family_id}
    )
    assert shared_ops.status_code == 200
    assert shared_ops.json()[0]["amount"] == "75"

    members = (await client.get(f"/workspaces/{family_id}/members")).json()
    assert [(m["user"]["username"], m["role"]) for m in members] == [
        ("owner", "owner"),
        ("wife", "editor"),
    ]

    reused = await client.post(
        f"/invites/{token}/accept",
        json={"username": "other", "password": "other-password-123"},
    )
    assert reused.status_code == 410


async def test_personal_workspace_cannot_issue_invites(client, web_auth):
    await create_owner(client)
    response = await client.post("/workspaces/1/invites")
    assert response.status_code == 409


async def test_category_cannot_cross_workspace_boundary(client, web_auth):
    await create_owner(client)
    family = (await client.post("/workspaces", json={"name": "Family"})).json()
    family_category = await client.post(
        "/categories",
        params={"workspace_id": family["id"]},
        json={"name": "Family food"},
    )
    assert family_category.status_code == 200

    today = date.today()
    personal_period = await client.post(
        "/periods",
        params={"workspace_id": 1},
        json={
            "total_amount": "500",
            "start_date": today.isoformat(),
            "end_date": (today + timedelta(days=4)).isoformat(),
        },
    )
    period_id = personal_period.json()["period"]["id"]
    response = await client.post(
        f"/periods/{period_id}/operations",
        params={"workspace_id": 1},
        json={"amount": "10", "category_id": family_category.json()["id"]},
    )
    assert response.status_code == 422
