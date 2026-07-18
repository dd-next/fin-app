"""Global asset catalogue and idempotent default seeding."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_user
from app.db import get_session
from app.models import Asset, User
from app.schemas import AssetCreate, AssetOut


DEFAULT_ASSETS = (
    ("VND", "Vietnamese dong", "fiat", 0),
    ("USD", "US dollar", "fiat", 2),
    ("RUB", "Russian ruble", "fiat", 2),
    ("EUR", "Euro", "fiat", 2),
    ("USDT", "Tether", "crypto", 6),
    ("BTC", "Bitcoin", "crypto", 8),
    ("ETH", "Ethereum", "crypto", 18),
    ("TRX", "TRON", "crypto", 6),
)


async def seed_default_assets(session: AsyncSession) -> None:
    existing = set((await session.execute(select(Asset.code))).scalars())
    for code, name, kind, decimals in DEFAULT_ASSETS:
        if code not in existing:
            session.add(
                Asset(code=code, name=name, kind=kind, decimals=decimals, is_active=True)
            )
    await session.commit()


async def asset_by_code(session: AsyncSession, code: str) -> Asset | None:
    return (
        await session.execute(select(Asset).where(Asset.code == code.upper()))
    ).scalar_one_or_none()


router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("", response_model=list[AssetOut])
async def list_assets(
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    del user
    return list(
        (
            await session.execute(
                select(Asset).where(Asset.is_active.is_(True)).order_by(Asset.code)
            )
        ).scalars()
    )


@router.post("", response_model=AssetOut, status_code=201)
async def create_asset(
    body: AssetCreate,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    del user
    asset = Asset(
        code=body.code,
        name=body.name.strip(),
        kind=body.kind,
        decimals=body.decimals,
        is_active=True,
    )
    session.add(asset)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Asset code already exists")
    await session.refresh(asset)
    return asset
