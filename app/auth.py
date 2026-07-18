"""Always-on web authentication for FinApp v2."""

from datetime import timedelta
import hashlib
import os
import secrets
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import AuthSession, Asset, User, Workspace, utcnow
from app.schemas import AuthContextOut, LoginIn, RegisterIn, UserOut, WorkspaceOut


COOKIE_NAME = "finapp_session"
SESSION_DAYS = 30
_hasher = PasswordHasher()
router = APIRouter(prefix="/auth", tags=["auth"])


def normalize_username(username: str) -> str:
    return username.strip().casefold()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _validate_timezone(value: str) -> str:
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError:
        raise HTTPException(status_code=422, detail="Unknown timezone")
    return value


def _verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def _set_cookie(response: Response, token: str) -> None:
    secure = os.environ.get("COOKIE_SECURE", "").lower() in {"1", "true", "yes", "on"}
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=SESSION_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )


async def _new_session(session: AsyncSession, user: User) -> str:
    raw = secrets.token_urlsafe(32)
    now = utcnow()
    session.add(
        AuthSession(
            user_id=user.id,
            token_hash=_token_hash(raw),
            created_at=now,
            expires_at=now + timedelta(days=SESSION_DAYS),
            last_seen_at=now,
        )
    )
    await session.commit()
    return raw


async def _session_user(session: AsyncSession, raw: str | None) -> User | None:
    if not raw:
        return None
    row = (
        await session.execute(
            select(AuthSession, User)
            .join(User, User.id == AuthSession.user_id)
            .where(AuthSession.token_hash == _token_hash(raw))
        )
    ).first()
    if row is None:
        return None
    auth_session, user = row
    if (
        auth_session.revoked_at is not None
        or auth_session.expires_at <= utcnow()
        or not user.is_active
    ):
        return None
    auth_session.last_seen_at = utcnow()
    await session.commit()
    return user


async def require_user(
    raw: str | None = Cookie(None, alias=COOKIE_NAME),
    session: AsyncSession = Depends(get_session),
) -> User:
    user = await _session_user(session, raw)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


async def primary_workspace(session: AsyncSession, user_id: int) -> Workspace:
    workspace = (
        await session.execute(
            select(Workspace).where(
                Workspace.owner_user_id == user_id,
                Workspace.archived_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace


async def _context(session: AsyncSession, user: User) -> AuthContextOut:
    workspace = await primary_workspace(session, user.id)
    await session.refresh(workspace, attribute_names=["base_asset"])
    return AuthContextOut(
        user=UserOut.model_validate(user),
        workspace=WorkspaceOut(
            id=workspace.id,
            owner_user_id=workspace.owner_user_id,
            name=workspace.name,
            timezone=workspace.timezone,
            base_asset=workspace.base_asset,
            created_at=workspace.created_at,
        ),
    )


@router.post("/register", response_model=AuthContextOut, status_code=201)
async def register(
    body: RegisterIn,
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    timezone = _validate_timezone(body.timezone)
    asset = (
        await session.execute(select(Asset).where(Asset.code == body.base_asset_code))
    ).scalar_one_or_none()
    if asset is None or not asset.is_active:
        raise HTTPException(status_code=422, detail="Unknown base asset")
    username = body.username.strip()
    user = User(
        username=username,
        normalized_username=normalize_username(username),
        display_name=(body.display_name or username).strip(),
        password_hash=_hasher.hash(body.password),
        timezone=timezone,
        is_active=True,
    )
    session.add(user)
    try:
        await session.flush()
        workspace = Workspace(
            owner_user_id=user.id,
            name=f"{user.display_name}'s Finances",
            base_asset_id=asset.id,
            timezone=timezone,
        )
        session.add(workspace)
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Username already exists")
    token = await _new_session(session, user)
    _set_cookie(response, token)
    return await _context(session, user)


@router.post("/login", response_model=AuthContextOut)
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
    if user is None or not user.is_active or not _verify_password(user.password_hash, body.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = await _new_session(session, user)
    _set_cookie(response, token)
    return await _context(session, user)


@router.post("/logout", status_code=204)
async def logout(
    response: Response,
    raw: str | None = Cookie(None, alias=COOKIE_NAME),
    session: AsyncSession = Depends(get_session),
):
    if raw:
        auth_session = (
            await session.execute(
                select(AuthSession).where(AuthSession.token_hash == _token_hash(raw))
            )
        ).scalar_one_or_none()
        if auth_session is not None:
            auth_session.revoked_at = utcnow()
            await session.commit()
    response.delete_cookie(COOKIE_NAME, path="/")


@router.get("/me", response_model=AuthContextOut)
async def me(
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    return await _context(session, user)
