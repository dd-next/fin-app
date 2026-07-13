"""Telegram Mini App auth: validate `Telegram.WebApp.initData`.

Telegram signs initData with HMAC-SHA256 using a key derived from the bot
token (documented scheme). The frontend sends it as `Authorization:
tma <initData>`; this module verifies the signature, freshness, and that
the user is the single owner (`OWNER_TELEGRAM_ID`).

Disabled by default (`TELEGRAM_AUTH_ENABLED=false`) so local browser use
keeps working without Telegram.
"""

import hashlib
import hmac
import json
import os
import time
from urllib.parse import parse_qsl

from fastapi import Header, HTTPException

MAX_AGE_SECONDS = 300  # reject initData older than a few minutes


def enabled() -> bool:
    """Read at call time so tests and .env changes take effect directly."""
    flag = os.environ.get("TELEGRAM_AUTH_ENABLED", "").strip().lower()
    return (
        flag in ("1", "true", "yes", "on")
        and bool(os.environ.get("TELEGRAM_BOT_TOKEN"))
        and bool(os.environ.get("OWNER_TELEGRAM_ID"))
    )


def validate_init_data(
    init_data: str,
    bot_token: str,
    owner_id: int,
    max_age_seconds: int = MAX_AGE_SECONDS,
    now: float | None = None,
) -> dict:
    """Validate a raw initData string; return the parsed user dict.

    Raises ValueError on any problem (bad signature, stale, wrong user).
    """
    try:
        fields = dict(parse_qsl(init_data, keep_blank_values=True))
    except Exception as exc:
        raise ValueError(f"unparseable initData: {exc}")

    received_hash = fields.pop("hash", None)
    if not received_hash:
        raise ValueError("missing hash")

    # data-check-string: all fields (except hash) as k=v, sorted, \n-joined
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(fields.items())
    )
    secret_key = hmac.new(
        b"WebAppData", bot_token.encode(), hashlib.sha256
    ).digest()
    expected_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected_hash, received_hash):
        raise ValueError("bad signature")

    try:
        auth_date = int(fields["auth_date"])
    except (KeyError, ValueError):
        raise ValueError("missing or invalid auth_date")
    now = time.time() if now is None else now
    if now - auth_date > max_age_seconds:
        raise ValueError("initData expired")

    try:
        user = json.loads(fields["user"])
        user_id = int(user["id"])
    except (KeyError, ValueError, TypeError):
        raise ValueError("missing or invalid user")
    if user_id != owner_id:
        raise ValueError("not the owner")

    return user


async def require_telegram_auth(authorization: str | None = Header(None)):
    """FastAPI dependency for the data endpoints. No-op when disabled."""
    if not enabled():
        return
    if not authorization or not authorization.startswith("tma "):
        raise HTTPException(status_code=401, detail="Telegram auth required")
    try:
        validate_init_data(
            authorization[4:],
            bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
            owner_id=int(os.environ["OWNER_TELEGRAM_ID"]),
        )
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid initData: {exc}")
