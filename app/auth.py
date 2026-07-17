"""Local web authentication with Argon2id passwords and opaque sessions."""

from datetime import timedelta
import hashlib
import hmac
import os
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import AuthSession, User, utcnow
from app.schemas import BootstrapIn, LoginIn, UserOut
from app import telegram_auth


COOKIE_NAME = "finapp_session"
SESSION_DAYS = 30
_hasher = PasswordHasher()


def web_auth_enabled() -> bool:
    return os.environ.get("WEB_AUTH_ENABLED", "").strip().lower() in {
        "1", "true", "yes", "on"
    }


def normalize_username(username: str) -> str:
    return username.strip().casefold()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def create_user(
    session: AsyncSession, username: str, password: str, display_name: str | None
) -> User:
    username = username.strip()
    user = User(
        username=username,
        normalized_username=normalize_username(username),
        display_name=(display_name or username).strip(),
        password_hash=hash_password(password),
        is_active=True,
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Username already exists")
    await session.refresh(user)
    return user


async def create_session(session: AsyncSession, user: User) -> str:
    raw = secrets.token_urlsafe(32)
    now = utcnow()
    session.add(
        AuthSession(
            user_id=user.id,
            token_hash=_token_hash(raw),
            created_at=now,
            last_seen_at=now,
            expires_at=now + timedelta(days=SESSION_DAYS),
        )
    )
    await session.commit()
    return raw


def set_session_cookie(response: Response, raw_token: str) -> None:
    secure = os.environ.get("COOKIE_SECURE", "").strip().lower() in {
        "1", "true", "yes", "on"
    }
    response.set_cookie(
        COOKIE_NAME,
        raw_token,
        max_age=SESSION_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )


async def _session_user(session: AsyncSession, raw_token: str | None) -> User | None:
    if not raw_token:
        return None
    result = await session.execute(
        select(AuthSession, User)
        .join(User, User.id == AuthSession.user_id)
        .where(AuthSession.token_hash == _token_hash(raw_token))
    )
    row = result.first()
    if row is None:
        return None
    auth_session, user = row
    if (
        auth_session.revoked_at is not None
        or auth_session.expires_at <= utcnow()
        or not user.is_active
    ):
        return None
    return user


async def require_web_user(
    raw_token: str | None = Cookie(None, alias=COOKIE_NAME),
    session: AsyncSession = Depends(get_session),
) -> User:
    user = await _session_user(session, raw_token)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


async def require_auth(
    raw_token: str | None = Cookie(None, alias=COOKIE_NAME),
    authorization: str | None = Header(None),
    session: AsyncSession = Depends(get_session),
) -> User | None:
    """Data gate: web session first, legacy Telegram gate second, local no-op."""
    if web_auth_enabled():
        user = await _session_user(session, raw_token)
        if user is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        return user
    if telegram_auth.enabled():
        await telegram_auth.require_telegram_auth(authorization)
    return None


router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/config")
async def auth_config():
    return {"enabled": web_auth_enabled()}


@router.post("/bootstrap", response_model=UserOut)
async def bootstrap(
    body: BootstrapIn,
    response: Response,
    x_bootstrap_token: str | None = Header(None),
    session: AsyncSession = Depends(get_session),
):
    count = (await session.execute(select(func.count(User.id)))).scalar_one()
    if count:
        raise HTTPException(status_code=409, detail="Owner is already bootstrapped")
    expected = os.environ.get("BOOTSTRAP_TOKEN")
    if web_auth_enabled() and (
        not expected or not x_bootstrap_token or not hmac.compare_digest(expected, x_bootstrap_token)
    ):
        raise HTTPException(status_code=403, detail="Valid bootstrap token required")
    user = await create_user(
        session, body.username, body.password, body.display_name
    )
    raw = await create_session(session, user)
    set_session_cookie(response, raw)
    return UserOut.model_validate(user)


@router.post("/login", response_model=UserOut)
async def login(
    body: LoginIn,
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    user = (
        await session.execute(
            select(User).where(
                User.normalized_username == normalize_username(body.username)
            )
        )
    ).scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(user.password_hash, body.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    raw = await create_session(session, user)
    set_session_cookie(response, raw)
    return UserOut.model_validate(user)


@router.post("/logout", status_code=204)
async def logout(
    response: Response,
    raw_token: str | None = Cookie(None, alias=COOKIE_NAME),
    session: AsyncSession = Depends(get_session),
):
    if raw_token:
        auth_session = (
            await session.execute(
                select(AuthSession).where(
                    AuthSession.token_hash == _token_hash(raw_token)
                )
            )
        ).scalar_one_or_none()
        if auth_session is not None:
            auth_session.revoked_at = utcnow()
            await session.commit()
    response.delete_cookie(COOKIE_NAME, path="/")


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(require_web_user)):
    return UserOut.model_validate(user)
