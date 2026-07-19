"""Owner-only workspace manual valuation-rate settings."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.access import require_workspace_owner
from app.db import get_session
from app.ledger import decimal_quotient, require_asset_code
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


def reciprocal(displayed_rate: Decimal) -> Decimal:
    """Return the exact high-precision asset-to-main valuation direction."""
    value = Decimal(displayed_rate)
    if not value.is_finite() or value <= 0:
        raise HTTPException(
            status_code=422, detail="Valuation rate must be positive and finite"
        )
    return decimal_quotient(Decimal(1), value)


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
        main_asset=AssetOut.model_validate(main_asset),
        asset=AssetOut.model_validate(asset),
        displayed_rate=rate.displayed_rate,
        effective_valuation_rate=reciprocal(rate.displayed_rate),
        active=rate.main_asset_id == workspace.base_asset_id,
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
    reciprocal(body.displayed_rate)
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
            displayed_rate=body.displayed_rate,
        )
        session.add(rate)
    else:
        rate.displayed_rate = body.displayed_rate
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
