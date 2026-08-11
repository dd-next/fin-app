"""Owner-private exact transfer quote creation."""

from datetime import timedelta
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import require_user
from app.db import get_session
from app.ledger import (
    MAX_INTEGER_DIGITS,
    decimal_product,
    decimal_quotient,
    quantize_asset_amount,
    quantize_exchange_rate,
    validate_amount,
)
from app.models import (
    Account,
    Asset,
    ManualValuationRate,
    TransferQuote,
    User,
    Workspace,
    utcnow,
)
from app.schemas import (
    AssetOut,
    TransferQuoteAccountOut,
    TransferQuoteCreate,
    TransferQuoteOut,
)


router = APIRouter(prefix="/operations/transfer/quotes", tags=["operations"])

QUOTE_LIFETIME = timedelta(minutes=5)


def decimal_string(value: Decimal) -> str:
    rendered = format(Decimal(value), "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered


def canonical_decimal(value: Decimal) -> Decimal:
    return Decimal(decimal_string(value))


def require_supported_intermediate(value: Decimal) -> Decimal:
    value = Decimal(value)
    if (
        not value.is_finite()
        or value <= 0
        or value.adjusted() + 1 > MAX_INTEGER_DIGITS
    ):
        raise HTTPException(
            status_code=422,
            detail="Transfer calculation exceeds supported precision",
        )
    return value


async def require_owner_quote_context(
    session: AsyncSession,
    user: User,
    from_account_id: int,
    to_account_id: int,
) -> tuple[Workspace, Account, Account]:
    row = (
        await session.execute(
            select(Workspace, Account)
            .join(Account, Account.workspace_id == Workspace.id)
            .options(
                selectinload(Workspace.base_asset),
                selectinload(Account.asset),
            )
            .where(
                Account.id == from_account_id,
                Account.archived_at.is_(None),
                Workspace.archived_at.is_(None),
                Workspace.owner_user_id == user.id,
            )
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    workspace, from_account = row
    to_account = (
        await session.execute(
            select(Account)
            .options(selectinload(Account.asset))
            .where(
                Account.id == to_account_id,
                Account.workspace_id == workspace.id,
                Account.archived_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if to_account is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if from_account.id == to_account.id:
        raise HTTPException(
            status_code=422,
            detail="Transfer accounts must be distinct",
        )
    return workspace, from_account, to_account


async def manual_rate_for_asset(
    session: AsyncSession,
    workspace: Workspace,
    asset: Asset,
) -> ManualValuationRate | None:
    if asset.id == workspace.base_asset_id:
        return None
    return (
        await session.execute(
            select(ManualValuationRate).where(
                ManualValuationRate.workspace_id == workspace.id,
                ManualValuationRate.main_asset_id == workspace.base_asset_id,
                ManualValuationRate.asset_id == asset.id,
            )
        )
    ).scalar_one_or_none()


def canonical_rate_value(
    rate: ManualValuationRate,
    asset: Asset,
    main_asset: Asset,
) -> Decimal:
    if rate.direction != "asset_to_main":
        raise HTTPException(
            status_code=422,
            detail=(
                "Manual valuation rate must be resaved before transfer quoting: "
                f"{asset.code} → {main_asset.code}"
            ),
        )
    value = Decimal(rate.rate_value)
    if (
        not value.is_finite()
        or value <= 0
        or value.adjusted() + 1 > MAX_INTEGER_DIGITS
        or max(-value.as_tuple().exponent, 0) > 18
    ):
        raise HTTPException(
            status_code=422,
            detail=f"Manual valuation rate is invalid: {asset.code} → {main_asset.code}",
        )
    return value


def quote_account_out(account: Account) -> TransferQuoteAccountOut:
    return TransferQuoteAccountOut(
        id=account.id,
        name=account.name,
        asset=AssetOut.model_validate(account.asset),
    )


def quote_out(quote: TransferQuote) -> TransferQuoteOut:
    return TransferQuoteOut(
        id=quote.id,
        workspace_id=quote.workspace_id,
        created_by_user_id=quote.created_by_user_id,
        from_account=quote_account_out(quote.from_account),
        to_account=quote_account_out(quote.to_account),
        from_amount=decimal_string(quote.from_amount),
        to_amount=decimal_string(quote.to_amount),
        rate=decimal_string(quote.rate),
        rate_source="manual",
        created_at=quote.created_at,
        expires_at=quote.expires_at,
    )


@router.post("", response_model=TransferQuoteOut, status_code=201)
async def create_transfer_quote(
    body: TransferQuoteCreate,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    workspace, from_account, to_account = await require_owner_quote_context(
        session,
        user,
        body.from_account_id,
        body.to_account_id,
    )
    main_asset = workspace.base_asset
    from_amount = canonical_decimal(
        validate_amount(Decimal(body.from_amount), from_account.asset)
    )

    source_rate = await manual_rate_for_asset(session, workspace, from_account.asset)
    target_rate = await manual_rate_for_asset(session, workspace, to_account.asset)

    source_rate_value = (
        canonical_rate_value(source_rate, from_account.asset, main_asset)
        if source_rate is not None
        else None
    )
    target_rate_value = (
        canonical_rate_value(target_rate, to_account.asset, main_asset)
        if target_rate is not None
        else None
    )

    if from_account.asset_id == to_account.asset_id:
        to_amount = from_amount
        effective_rate = Decimal("1")
        source_dependency = None
        target_dependency = None
    else:
        missing_assets = []
        if from_account.asset_id != main_asset.id and source_rate is None:
            missing_assets.append(from_account.asset)
        if to_account.asset_id != main_asset.id and target_rate is None:
            missing_assets.append(to_account.asset)
        if missing_assets:
            pairs = ", ".join(
                f"{asset.code} → {main_asset.code}" for asset in missing_assets
            )
            raise HTTPException(
                status_code=422,
                detail=f"Missing manual valuation rates for transfer quoting: {pairs}",
            )

        source_main = require_supported_intermediate(
            from_amount
            if from_account.asset_id == main_asset.id
            else decimal_product(from_amount, source_rate_value)
        )
        exact_target = require_supported_intermediate(
            source_main
            if to_account.asset_id == main_asset.id
            else decimal_quotient(source_main, target_rate_value)
        )
        try:
            to_amount = canonical_decimal(
                validate_amount(
                    quantize_asset_amount(exact_target, to_account.asset),
                    to_account.asset,
                )
            )
            effective_rate = canonical_decimal(
                quantize_exchange_rate(decimal_quotient(to_amount, from_amount))
            )
        except (InvalidOperation, ArithmeticError) as error:
            raise HTTPException(
                status_code=422,
                detail="Transfer calculation exceeds supported precision",
            ) from error

        incoming_main = require_supported_intermediate(
            to_amount
            if to_account.asset_id == main_asset.id
            else decimal_product(to_amount, target_rate_value)
        )
        if source_main != incoming_main:
            raise HTTPException(
                status_code=422,
                detail="Transfer amount cannot preserve Total capital",
            )
        source_dependency = source_rate
        target_dependency = target_rate

    created_at = utcnow()
    quote = TransferQuote(
        workspace_id=workspace.id,
        created_by_user_id=user.id,
        from_account_id=from_account.id,
        to_account_id=to_account.id,
        from_asset_id=from_account.asset_id,
        to_asset_id=to_account.asset_id,
        main_asset_id=main_asset.id,
        from_amount=from_amount,
        to_amount=to_amount,
        rate=effective_rate,
        rate_source="manual",
        source_manual_rate_id=(
            source_dependency.id if source_dependency is not None else None
        ),
        source_manual_rate_value=(
            canonical_decimal(source_rate_value)
            if source_dependency is not None
            else None
        ),
        source_manual_rate_direction=(
            source_dependency.direction if source_dependency is not None else None
        ),
        source_manual_rate_updated_at=(
            source_dependency.updated_at if source_dependency is not None else None
        ),
        target_manual_rate_id=(
            target_dependency.id if target_dependency is not None else None
        ),
        target_manual_rate_value=(
            canonical_decimal(target_rate_value)
            if target_dependency is not None
            else None
        ),
        target_manual_rate_direction=(
            target_dependency.direction if target_dependency is not None else None
        ),
        target_manual_rate_updated_at=(
            target_dependency.updated_at if target_dependency is not None else None
        ),
        status="open",
        created_at=created_at,
        expires_at=created_at + QUOTE_LIFETIME,
    )
    quote.from_account = from_account
    quote.to_account = to_account
    session.add(quote)
    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Transfer quote could not be created",
        ) from error
    await session.refresh(quote)
    return quote_out(quote)
