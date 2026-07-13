"""Telegram initData validation tests. Signatures are generated locally
with Telegram's documented algorithm — no network, no real bot."""

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest

from app.telegram_auth import validate_init_data

BOT_TOKEN = "1234567890:TEST-FAKE-TOKEN-abcdef"
OWNER_ID = 424242


def sign_init_data(
    bot_token: str = BOT_TOKEN,
    user_id: int = OWNER_ID,
    auth_date: int | None = None,
) -> str:
    """Build an initData string signed exactly like Telegram does."""
    fields = {
        "auth_date": str(int(time.time()) if auth_date is None else auth_date),
        "query_id": "AAF9tZEeAAAAAH21kR4qmY2z",
        "user": json.dumps(
            {"id": user_id, "first_name": "Test", "username": "tester"}
        ),
    }
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(fields.items())
    )
    secret_key = hmac.new(
        b"WebAppData", bot_token.encode(), hashlib.sha256
    ).digest()
    fields["hash"] = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()
    return urlencode(fields)


# ---- unit tests: the validation itself ----------------------------------------


def test_valid_init_data_passes():
    user = validate_init_data(sign_init_data(), BOT_TOKEN, OWNER_ID)
    assert user["id"] == OWNER_ID


def test_tampered_init_data_rejected():
    init_data = sign_init_data()
    tampered = init_data.replace("tester", "attacker")
    with pytest.raises(ValueError, match="bad signature"):
        validate_init_data(tampered, BOT_TOKEN, OWNER_ID)


def test_wrong_bot_token_rejected():
    with pytest.raises(ValueError, match="bad signature"):
        validate_init_data(sign_init_data(), "9999:other-token", OWNER_ID)


def test_expired_init_data_rejected():
    stale = sign_init_data(auth_date=int(time.time()) - 3600)
    with pytest.raises(ValueError, match="expired"):
        validate_init_data(stale, BOT_TOKEN, OWNER_ID)


def test_wrong_owner_rejected():
    init_data = sign_init_data(user_id=13)  # correctly signed, wrong person
    with pytest.raises(ValueError, match="not the owner"):
        validate_init_data(init_data, BOT_TOKEN, OWNER_ID)


def test_missing_hash_rejected():
    with pytest.raises(ValueError, match="missing hash"):
        validate_init_data("auth_date=123&user=%7B%7D", BOT_TOKEN, OWNER_ID)


# ---- API gate ------------------------------------------------------------------


@pytest.fixture
def auth_enabled(monkeypatch):
    monkeypatch.setenv("TELEGRAM_AUTH_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", BOT_TOKEN)
    monkeypatch.setenv("OWNER_TELEGRAM_ID", str(OWNER_ID))


async def test_data_endpoints_require_auth(client, auth_enabled):
    resp = await client.get("/budget")
    assert resp.status_code == 401
    resp = await client.post("/expenses", json={"amount": "10"})
    assert resp.status_code == 401
    resp = await client.get("/export.xlsx")
    assert resp.status_code == 401


async def test_health_stays_open(client, auth_enabled):
    resp = await client.get("/health")
    assert resp.status_code == 200


async def test_valid_header_grants_access(client, auth_enabled):
    headers = {"Authorization": f"tma {sign_init_data()}"}
    resp = await client.get("/period", headers=headers)
    assert resp.status_code == 404  # authenticated; there is just no period

    from datetime import date, timedelta

    start = date.today()
    resp = await client.post(
        "/period",
        json={
            "total_amount": "100",
            "start_date": start.isoformat(),
            "end_date": (start + timedelta(days=4)).isoformat(),
        },
        headers=headers,
    )
    assert resp.status_code == 200


async def test_bad_header_rejected(client, auth_enabled):
    resp = await client.get("/budget", headers={"Authorization": "tma junk"})
    assert resp.status_code == 401
    resp = await client.get(
        "/budget", headers={"Authorization": "Bearer whatever"}
    )
    assert resp.status_code == 401


async def test_disabled_by_default_no_header_needed(client, monkeypatch):
    monkeypatch.delenv("TELEGRAM_AUTH_ENABLED", raising=False)
    resp = await client.get("/health")
    assert resp.status_code == 200
    resp = await client.get("/period")
    assert resp.status_code == 404  # no auth wall, just no period yet
