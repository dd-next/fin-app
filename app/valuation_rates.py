"""Owner-only workspace manual valuation-rate settings."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.access import require_workspace_owner
from app.db import get_session
from app.ledger import manual_rate_asset_to_main, require_asset_code
from app.models import Asset, ManualValuationRate, Workspace
from app.schemas import (
    AssetOut,
    ManualValuationRateOut,
    ManualValuationRateUpsert,
)


router = APIRouter(
    prefix="/workspaces/{workspace_id}/valuation-rates",
    tags=["financial-settings"],
)


def decimal_string(value: Decimal) -> str:
    """Serialize an exact Decimal without exponent notation or padding."""
    rendered = format(Decimal(value), "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered


async def rate_out(
    session: AsyncSession,
    rate: ManualValuationRate,
    workspace: Workspace,
) -> ManualValuationRateOut:
    main_asset = await session.get(Asset, rate.main_asset_id)
    asset = await session.get(Asset, rate.asset_id)
    assert main_asset is not None and asset is not None
    return ManualValuationRateOut(
        id=rate.id,
        workspace_id=rate.workspace_id,
        from_asset=AssetOut.model_validate(asset),
        to_asset=AssetOut.model_validate(main_asset),
        rate=decimal_string(manual_rate_asset_to_main(rate)),
        source="manual",
        created_at=rate.created_at,
        updated_at=rate.updated_at,
    )


@router.get("", response_model=list[ManualValuationRateOut])
async def list_manual_valuation_rates(
    workspace: Workspace = Depends(require_workspace_owner),
    session: AsyncSession = Depends(get_session),
):
    rates = list(
        (
            await session.execute(
                select(ManualValuationRate)
                .join(Asset, Asset.id == ManualValuationRate.asset_id)
                .where(
                    ManualValuationRate.workspace_id == workspace.id,
                    ManualValuationRate.main_asset_id == workspace.base_asset_id,
                )
                .order_by(Asset.code)
            )
        ).scalars()
    )
    return [await rate_out(session, rate, workspace) for rate in rates]


@router.put("/{asset_code}", response_model=ManualValuationRateOut)
async def save_manual_valuation_rate(
    asset_code: str,
    body: ManualValuationRateUpsert,
    workspace: Workspace = Depends(require_workspace_owner),
    session: AsyncSession = Depends(get_session),
):
    asset = await require_asset_code(session, asset_code)
    if asset.id == workspace.base_asset_id:
        raise HTTPException(
            status_code=422,
            detail="Main currency always values itself at exactly 1",
        )
    canonical_rate = Decimal(body.rate)
    rate = (
        await session.execute(
            select(ManualValuationRate).where(
                ManualValuationRate.workspace_id == workspace.id,
                ManualValuationRate.main_asset_id == workspace.base_asset_id,
                ManualValuationRate.asset_id == asset.id,
            )
        )
    ).scalar_one_or_none()
    if rate is None:
        rate = ManualValuationRate(
            workspace_id=workspace.id,
            main_asset_id=workspace.base_asset_id,
            asset_id=asset.id,
            rate_value=canonical_rate,
            direction="asset_to_main",
        )
        session.add(rate)
    else:
        rate.rate_value = canonical_rate
        rate.direction = "asset_to_main"
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Valuation rate already exists")
    await session.refresh(rate)
    return await rate_out(session, rate, workspace)


@router.delete("/{asset_code}", status_code=204)
async def delete_manual_valuation_rate(
    asset_code: str,
    workspace: Workspace = Depends(require_workspace_owner),
    session: AsyncSession = Depends(get_session),
):
    asset = await require_asset_code(session, asset_code)
    rate = (
        await session.execute(
            select(ManualValuationRate).where(
                ManualValuationRate.workspace_id == workspace.id,
                ManualValuationRate.main_asset_id == workspace.base_asset_id,
                ManualValuationRate.asset_id == asset.id,
            )
        )
    ).scalar_one_or_none()
    if rate is None:
        raise HTTPException(status_code=404, detail="Valuation rate not found")
    await session.delete(rate)
    await session.commit()
    return Response(status_code=204)
