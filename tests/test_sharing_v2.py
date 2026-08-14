from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import app.sharing as sharing
from tests.conftest import register
from tests.test_ledger_v2 import create_account


PASSWORD = "correct-horse-battery"


async def login(client, username: str) -> dict:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": PASSWORD},
    )
    assert response.status_code == 200, response.text
    return response.json()


async def invitation(client, account_id: int, role: str) -> str:
    response = await client.post(
        f"/api/v1/accounts/{account_id}/invitations", json={"role": role}
    )
    assert response.status_code == 201, response.text
    return response.json()["token"]


async def accept(client, token: str) -> dict:
    response = await client.post(f"/api/v1/account-invitations/{token}/accept")
    assert response.status_code == 200, response.text
    return response.json()


async def test_invitation_lifecycle_visibility_categories_and_no_total_leakage(
    client, monkeypatch
):
    alice = await register(client)
    shared = await create_account(client, "Shared USD", "USD", "100")
    await create_account(client, "Private USD", "USD", "900")
    category_route = (
        f"/api/v1/workspaces/{alice['workspace']['id']}/categories"
    )
    category = (
        await client.post(category_route, json={"name": "Groceries", "kind": "expense"})
    ).json()
    token = await invitation(client, shared["id"], "viewer")
    expiring_token = await invitation(client, shared["id"], "viewer")

    bob = await register(client, "bob")
    access = await accept(client, token)
    assert access["role"] == "viewer"
    assert (await client.post(f"/api/v1/account-invitations/{token}/accept")).status_code == 410

    accounts = (await client.get("/api/v1/accounts")).json()
    assert [(item["name"], item["access_role"]) for item in accounts] == [
        ("Shared USD", "viewer")
    ]
    summary = (await client.get("/api/v1/accounts/summary")).json()
    assert Decimal(summary["net_worth"]) == Decimal("100")
    assert [item["name"] for item in summary["accounts"]] == ["Shared USD"]
    assert (await client.get(category_route)).json()[0]["id"] == category["id"]
    assert (
        await client.post(category_route, json={"name": "Forbidden", "kind": "expense"})
    ).status_code == 404
    assert (
        await client.post(
            "/api/v1/operations/spend",
            json={"account_id": shared["id"], "amount": "1"},
        )
    ).status_code == 403

    real_now = sharing.utcnow
    monkeypatch.setattr(sharing, "utcnow", lambda: real_now() + timedelta(days=8))
    assert (
        await client.post(f"/api/v1/account-invitations/{expiring_token}/accept")
    ).status_code == 410
    assert (
        await client.post("/api/v1/account-invitations/not-a-real-token/accept")
    ).status_code == 410
    assert bob["workspace"]["id"] != alice["workspace"]["id"]


async def test_role_capabilities_and_owner_access_management(client):
    await register(client)
    viewer = await create_account(client, "Viewer USD", "USD", "100")
    contributor = await create_account(client, "Contributor USD", "USD", "100")
    editor_a = await create_account(client, "Editor A USD", "USD", "100")
    editor_b = await create_account(client, "Editor B USD", "USD", "0")
    tokens = [
        await invitation(client, viewer["id"], "viewer"),
        await invitation(client, contributor["id"], "contributor"),
        await invitation(client, editor_a["id"], "editor"),
        await invitation(client, editor_b["id"], "editor"),
    ]

    bob = await register(client, "bob")
    for token in tokens:
        await accept(client, token)

    assert (await client.get(f"/api/v1/accounts/{viewer['id']}")).status_code == 200
    assert (
        await client.post(
            "/api/v1/operations/spend",
            json={"account_id": viewer["id"], "amount": "1"},
        )
    ).status_code == 403

    expense = await client.post(
        "/api/v1/operations/spend",
        json={"account_id": contributor["id"], "amount": "2"},
    )
    assert expense.status_code == 201, expense.text
    assert (
        await client.post(
            "/api/v1/operations/add-funds",
            json={"account_id": contributor["id"], "amount": "2"},
        )
    ).status_code == 403
    assert (
        await client.patch(
            f"/api/v1/transactions/{expense.json()['id']}", json={"amount": "3"}
        )
    ).status_code == 403
    assert (
        await client.post(f"/api/v1/transactions/{expense.json()['id']}/delete")
    ).status_code == 403
    assert (
        await client.patch(f"/api/v1/accounts/{contributor['id']}", json={"name": "No"})
    ).status_code == 403

    income = await client.post(
        "/api/v1/operations/add-funds",
        json={"account_id": editor_a["id"], "amount": "10"},
    )
    assert income.status_code == 201, income.text
    edited_income = await client.patch(
        f"/api/v1/transactions/{income.json()['id']}",
        json={"amount": "12", "note": "Corrected by editor"},
    )
    assert edited_income.status_code == 409, edited_income.text
    assert edited_income.json()["detail"] == (
        "Shared transaction correction requires explicit confirmation"
    )
    edited_income = await client.patch(
        f"/api/v1/transactions/{income.json()['id']}",
        json={
            "amount": "12",
            "note": "Corrected by editor",
            "confirm_ended_period": True,
        },
    )
    assert edited_income.status_code == 200, edited_income.text
    assert edited_income.json()["note"] == "Corrected by editor"
    unconfirmed_void = await client.post(
        f"/api/v1/transactions/{income.json()['id']}/delete"
    )
    assert unconfirmed_void.status_code == 409
    confirmed_void = await client.post(
        f"/api/v1/transactions/{income.json()['id']}/delete",
        json={"confirm_ended_period": True},
    )
    assert confirmed_void.status_code == 200
    assert (
        await client.patch(f"/api/v1/accounts/{editor_a['id']}", json={"name": "Editor renamed"})
    ).status_code == 200
    assert (
        await client.post(
            "/api/v1/operations/transfer",
            json={
                "from_account_id": editor_a["id"],
                "to_account_id": editor_b["id"],
                "amount": "5",
            },
        )
    ).status_code == 201
    assert (
        await client.post(
            "/api/v1/operations/transfer",
            json={
                "from_account_id": editor_a["id"],
                "to_account_id": contributor["id"],
                "amount": "1",
            },
        )
    ).status_code == 403
    assert (
        await client.post(
            "/api/v1/operations/adjustment",
            json={"account_id": editor_a["id"], "delta": "1"},
        )
    ).status_code in {404, 405}
    assert (
        await client.post(
            f"/api/v1/accounts/{editor_a['id']}/reconcile",
            json={"target_balance": "99"},
        )
    ).status_code == 403
    assert (
        await client.post(f"/api/v1/accounts/{editor_a['id']}/archive")
    ).status_code == 403
    assert (await client.get(f"/api/v1/accounts/{editor_a['id']}/access")).status_code == 403

    await login(client, "alice")
    rows = (await client.get(f"/api/v1/accounts/{viewer['id']}/access")).json()
    assert [row["role"] for row in rows] == ["owner", "viewer"]
    changed = await client.patch(
        f"/api/v1/accounts/{viewer['id']}/access/{bob['user']['id']}",
        json={"role": "contributor"},
    )
    assert changed.status_code == 200
    assert changed.json()["role"] == "contributor"
    removed = await client.delete(
        f"/api/v1/accounts/{viewer['id']}/access/{bob['user']['id']}"
    )
    assert removed.status_code == 204
    await login(client, "bob")
    assert (await client.get(f"/api/v1/accounts/{viewer['id']}")).status_code == 404


async def test_hidden_legs_are_redacted_and_block_multi_account_mutation(client):
    await register(client)
    shared = await create_account(client, "Shared USD", "USD", "100")
    private = await create_account(client, "Private USD", "USD", "0")
    today = datetime.now(UTC).astimezone(ZoneInfo("Asia/Ho_Chi_Minh")).date()
    historical = today - timedelta(days=7)
    period = await client.post(
        f"/api/v1/accounts/{shared['id']}/periods",
        json={
            "start_date": (today - timedelta(days=10)).isoformat(),
            "end_date": (today - timedelta(days=5)).isoformat(),
        },
    )
    assert period.status_code == 201, period.text
    private_expense = (
        await client.post(
            "/api/v1/operations/spend",
            json={"account_id": private["id"], "amount": "1"},
        )
    ).json()
    transfer = (
        await client.post(
            "/api/v1/operations/transfer",
            json={
                "from_account_id": shared["id"],
                "to_account_id": private["id"],
                "amount": "25",
                "local_date": historical.isoformat(),
                "confirm_ended_period": True,
            },
        )
    ).json()
    token = await invitation(client, shared["id"], "editor")

    await register(client, "bob")
    await accept(client, token)
    detail = (await client.get(f"/api/v1/transactions/{transfer['id']}")).json()
    assert detail["has_hidden_legs"] is True
    assert len(detail["legs"]) == 1
    assert detail["legs"][0]["account_id"] == shared["id"]
    history = (await client.get("/api/v1/transactions")).json()["items"]
    history_ids = [item["id"] for item in history]
    assert transfer["id"] in history_ids
    assert private_expense["id"] not in history_ids
    assert next(item for item in history if item["id"] == transfer["id"])[
        "has_hidden_legs"
    ] is True
    assert (await client.get(f"/api/v1/transactions/{private_expense['id']}")).status_code == 404
    blocked_patch = await client.patch(
        f"/api/v1/transactions/{transfer['id']}", json={"note": "Blocked"}
    )
    assert blocked_patch.status_code == 404
    assert blocked_patch.json() == {"detail": "Account not found"}
    blocked_delete = await client.post(
        f"/api/v1/transactions/{transfer['id']}/delete"
    )
    assert blocked_delete.status_code == 404
    assert blocked_delete.json() == {"detail": "Account not found"}
    filtered = (
        await client.get(f"/api/v1/transactions?account_id={shared['id']}")
    ).json()
    assert transfer["id"] in [item["id"] for item in filtered["items"]]
    assert (
        await client.get(f"/api/v1/transactions?account_id={private['id']}")
    ).status_code == 404
