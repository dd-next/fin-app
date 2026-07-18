from tests.conftest import register
from tests.test_ledger_v2 import create_account
from tests.test_sharing_v2 import accept, invitation, login


async def test_archived_categories_follow_shared_transaction_visibility(client):
    owner = await register(client)
    workspace_id = owner["workspace"]["id"]
    category_route = f"/api/v1/workspaces/{workspace_id}/categories"
    shared_account = await create_account(client, "Shared USD", "USD", "100")
    private_account = await create_account(client, "Private USD", "USD", "100")

    categories = {}
    for name in (
        "Active choice",
        "Visible history",
        "Private history",
        "Voided history",
    ):
        response = await client.post(
            category_route, json={"name": name, "kind": "expense"}
        )
        assert response.status_code == 201, response.text
        categories[name] = response.json()

    visible = await client.post(
        "/api/v1/transactions/expense",
        json={
            "account_id": shared_account["id"],
            "amount": "10",
            "category_id": categories["Visible history"]["id"],
        },
    )
    private = await client.post(
        "/api/v1/transactions/expense",
        json={
            "account_id": private_account["id"],
            "amount": "20",
            "category_id": categories["Private history"]["id"],
        },
    )
    voided = await client.post(
        "/api/v1/transactions/expense",
        json={
            "account_id": shared_account["id"],
            "amount": "5",
            "category_id": categories["Voided history"]["id"],
        },
    )
    assert visible.status_code == private.status_code == voided.status_code == 201
    void_response = await client.post(
        f"/api/v1/transactions/{voided.json()['id']}/void"
    )
    assert void_response.status_code == 200, void_response.text

    for name in ("Visible history", "Private history", "Voided history"):
        archived = await client.post(
            f"{category_route}/{categories[name]['id']}/archive"
        )
        assert archived.status_code == 200, archived.text

    owner_names = {
        item["name"]
        for item in (await client.get(f"{category_route}?include_archived=true")).json()
    }
    assert owner_names == set(categories)

    token = await invitation(client, shared_account["id"], "viewer")
    await register(client, "bob")
    await accept(client, token)

    shared_response = await client.get(f"{category_route}?include_archived=true")
    assert shared_response.status_code == 200, shared_response.text
    assert {item["name"] for item in shared_response.json()} == {
        "Active choice",
        "Visible history",
        "Voided history",
    }
    assert {item["name"] for item in (await client.get(category_route)).json()} == {
        "Active choice"
    }

    private_detail = await client.get(
        f"/api/v1/transactions/{private.json()['id']}"
    )
    assert private_detail.status_code == 404
    voided_detail = await client.get(
        f"/api/v1/transactions/{voided.json()['id']}"
    )
    assert voided_detail.status_code == 200, voided_detail.text
    assert voided_detail.json()["category_id"] == categories["Voided history"]["id"]

    await login(client, "alice")
    owner_again = await client.get(f"{category_route}?include_archived=true")
    assert owner_again.status_code == 200, owner_again.text
    assert {item["name"] for item in owner_again.json()} == set(categories)
