"""Shared ledger queries, validation, valuation, and response builders."""

from datetime import UTC, date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Account,
    Asset,
    Category,
    ExchangeRate,
    PlanOccurrence,
    Transaction,
    TransactionLeg,
    Workspace,
)
from app.schemas import (
    AccountOut,
    AssetOut,
    ExchangeRateOut,
    TransactionLegOut,
    TransactionOut,
)


ZERO = Decimal("0")


def normalize_name(value: str) -> str:
    return " ".join(value.strip().split()).casefold()


def validate_amount(value: Decimal, asset: Asset, *, allow_zero: bool = False) -> Decimal:
    value = Decimal(value)
    if not value.is_finite():
        raise HTTPException(status_code=422, detail="Amount must be finite")
    if not allow_zero and value == 0:
        raise HTTPException(status_code=422, detail="Amount must not be zero")
    places = max(-value.as_tuple().exponent, 0)
    if places > asset.decimals:
        raise HTTPException(
            status_code=422,
            detail=f"{asset.code} supports at most {asset.decimals} decimal places",
        )
    if len(value.as_tuple().digits) > 38:
        raise HTTPException(status_code=422, detail="Amount has too many digits")
    return value


async def require_asset_code(session: AsyncSession, code: str) -> Asset:
    asset = (
        await session.execute(
            select(Asset).where(Asset.code == code.upper(), Asset.is_active.is_(True))
        )
    ).scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=422, detail="Unknown asset")
    return asset


async def require_owned_account(
    session: AsyncSession,
    account_id: int,
    user_id: int,
    *,
    allow_archived: bool = False,
) -> Account:
    account = await session.get(Account, account_id)
    if (
        account is None
        or account.owner_user_id != user_id
        or (account.archived_at is not None and not allow_archived)
    ):
        raise HTTPException(status_code=404, detail="Account not found")
    await session.refresh(account, attribute_names=["asset"])
    return account


async def require_category(
    session: AsyncSession,
    category_id: int | None,
    workspace_id: int,
    transaction_type: str,
) -> Category | None:
    if category_id is None:
        return None
    category = await session.get(Category, category_id)
    if (
        category is None
        or category.workspace_id != workspace_id
        or category.archived_at is not None
    ):
        raise HTTPException(status_code=422, detail="Invalid category")
    allowed = {
        "expense": {"expense", "both"},
        "income": {"income", "both"},
    }.get(transaction_type, set())
    if category.kind not in allowed:
        raise HTTPException(status_code=422, detail="Category kind does not match transaction")
    return category


def financial_times(
    workspace: Workspace,
    occurred_at: datetime | None,
    local_date: date | None,
) -> tuple[datetime, date]:
    if occurred_at is None:
        aware = datetime.now(UTC)
    else:
        if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
            raise HTTPException(status_code=422, detail="occurred_at must include a timezone")
        aware = occurred_at.astimezone(UTC)
    utc_naive = aware.replace(tzinfo=None)
    financial_date = local_date or aware.astimezone(ZoneInfo(workspace.timezone)).date()
    return utc_naive, financial_date


async def account_balance(session: AsyncSession, account_id: int) -> Decimal:
    amounts = (
        await session.execute(
            select(TransactionLeg.amount)
            .join(Transaction, Transaction.id == TransactionLeg.transaction_id)
            .where(
                TransactionLeg.account_id == account_id,
                Transaction.status == "posted",
            )
        )
    ).scalars()
    return sum((Decimal(value) for value in amounts), ZERO)


async def latest_rate(
    session: AsyncSession, base_asset_id: int, quote_asset_id: int
) -> ExchangeRate | None:
    return (
        await session.execute(
            select(ExchangeRate)
            .join(Transaction, Transaction.id == ExchangeRate.source_transaction_id)
            .where(
                ExchangeRate.base_asset_id == base_asset_id,
                ExchangeRate.quote_asset_id == quote_asset_id,
                Transaction.status == "posted",
            )
            .order_by(ExchangeRate.captured_at.desc(), ExchangeRate.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def valued_balance(
    session: AsyncSession,
    balance: Decimal,
    asset_id: int,
    base_asset_id: int,
) -> Decimal | None:
    if asset_id == base_asset_id:
        return balance
    rate = await latest_rate(session, asset_id, base_asset_id)
    return None if rate is None else balance * rate.rate


async def account_out(
    session: AsyncSession,
    account: Account,
    base_asset_id: int,
    *,
    access_role: str = "owner",
) -> AccountOut:
    await session.refresh(account, attribute_names=["asset"])
    balance = await account_balance(session, account.id)
    return AccountOut(
        id=account.id,
        workspace_id=account.workspace_id,
        owner_user_id=account.owner_user_id,
        name=account.name,
        storage_type=account.storage_type,
        purpose=account.purpose,
        asset=AssetOut.model_validate(account.asset),
        institution=account.institution,
        include_in_available=account.include_in_available,
        balance=balance,
        valued_balance=await valued_balance(
            session, balance, account.asset_id, base_asset_id
        ),
        archived_at=account.archived_at,
        access_role=access_role,
        is_shared=access_role != "owner",
    )


async def transaction_out(
    session: AsyncSession,
    transaction: Transaction,
    *,
    visible_account_ids: set[int] | None = None,
) -> TransactionOut:
    rows = (
        await session.execute(
            select(TransactionLeg, Asset)
            .join(Asset, Asset.id == TransactionLeg.asset_id)
            .where(TransactionLeg.transaction_id == transaction.id)
            .order_by(TransactionLeg.id)
        )
    ).all()
    has_hidden = False
    legs: list[TransactionLegOut] = []
    for leg, asset in rows:
        if (
            visible_account_ids is not None
            and leg.account_id is not None
            and leg.account_id not in visible_account_ids
        ):
            has_hidden = True
            continue
        legs.append(
            TransactionLegOut(
                id=leg.id,
                account_id=leg.account_id,
                asset=AssetOut.model_validate(asset),
                amount=leg.amount,
            )
        )
    plan_occurrence_id = None
    if visible_account_ids is None:
        plan_occurrence_id = (
            await session.execute(
                select(PlanOccurrence.id).where(
                    PlanOccurrence.transaction_id == transaction.id
                )
            )
        ).scalar_one_or_none()
    return TransactionOut(
        id=transaction.id,
        workspace_id=transaction.workspace_id,
        created_by_user_id=transaction.created_by_user_id,
        type=transaction.type,
        category_id=transaction.category_id,
        parent_transaction_id=transaction.parent_transaction_id,
        counterparty=transaction.counterparty,
        note=transaction.note,
        occurred_at=transaction.occurred_at,
        local_date=transaction.local_date,
        source=transaction.source,
        status=transaction.status,
        base_amount=transaction.base_amount,
        base_rate=transaction.base_rate,
        rate_source=transaction.rate_source,
        created_at=transaction.created_at,
        updated_at=transaction.updated_at,
        voided_at=transaction.voided_at,
        legs=legs,
        has_hidden_legs=has_hidden,
        plan_occurrence_id=plan_occurrence_id,
    )


async def rate_out(session: AsyncSession, rate: ExchangeRate) -> ExchangeRateOut:
    base = await session.get(Asset, rate.base_asset_id)
    quote = await session.get(Asset, rate.quote_asset_id)
    assert base is not None and quote is not None
    return ExchangeRateOut(
        base_asset=AssetOut.model_validate(base),
        quote_asset=AssetOut.model_validate(quote),
        rate=rate.rate,
        captured_at=rate.captured_at,
        source_transaction_id=rate.source_transaction_id,
    )
