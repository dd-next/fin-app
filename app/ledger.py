"""Shared ledger queries, validation, valuation, and response builders."""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Iterable
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Account,
    Asset,
    Category,
    ExchangeRate,
    ManualValuationRate,
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
RATE_DECIMALS = 18
MAX_INTEGER_DIGITS = 20
CALCULATION_PRECISION = 100


@dataclass(frozen=True)
class AccountValues:
    balance: Decimal
    valued_balance: Decimal | None


def decimal_sum(values: Iterable[Decimal]) -> Decimal:
    """Sum finite financial Decimals without the default 28-digit truncation."""
    items = [Decimal(value) for value in values]
    if not items:
        return ZERO
    nonzero = [value for value in items if value]
    if not nonzero:
        return ZERO
    most_significant = max(value.adjusted() for value in nonzero)
    least_exponent = min(value.as_tuple().exponent for value in nonzero)
    exact_digits = most_significant - least_exponent + len(str(len(items))) + 2
    with localcontext() as context:
        context.prec = max(CALCULATION_PRECISION, exact_digits)
        total = ZERO
        for value in items:
            total += value
        return total


def decimal_product(left: Decimal, right: Decimal) -> Decimal:
    """Multiply stored/rate Decimals with enough precision for an exact product."""
    left, right = Decimal(left), Decimal(right)
    exact_digits = len(left.as_tuple().digits) + len(right.as_tuple().digits) + 2
    with localcontext() as context:
        context.prec = max(CALCULATION_PRECISION, exact_digits)
        return left * right


def decimal_absolute(value: Decimal) -> Decimal:
    """Return a magnitude without applying the ambient Decimal context."""
    return Decimal(value).copy_abs()


def decimal_negate(value: Decimal) -> Decimal:
    """Flip a sign without applying the ambient Decimal context."""
    return Decimal(value).copy_negate()


def decimal_difference(left: Decimal, right: Decimal) -> Decimal:
    """Subtract exact financial values through the context-safe sum path."""
    return decimal_sum((Decimal(left), decimal_negate(right)))


def decimal_quotient(numerator: Decimal, denominator: Decimal) -> Decimal:
    """Divide financial Decimals at the shared high calculation precision."""
    with localcontext() as context:
        context.prec = CALCULATION_PRECISION
        return Decimal(numerator) / Decimal(denominator)


def quantize_decimal(value: Decimal, decimals: int) -> Decimal:
    """Round an API-facing Decimal without changing its ledger source value."""
    decimal = Decimal(value)
    quantum = Decimal(1).scaleb(-decimals)
    # Quantizing a valid 38-digit ledger amount to an 18-place display value can
    # need more precision than Decimal's default 28-digit context.
    with localcontext() as context:
        context.prec = max(80, len(decimal.as_tuple().digits) + decimals + 2)
        return decimal.quantize(quantum, rounding=ROUND_HALF_UP)


def quantize_asset_amount(value: Decimal, asset: Asset | AssetOut) -> Decimal:
    return quantize_decimal(value, asset.decimals)


def quantize_main_amount(value: Decimal, main_asset: Asset | AssetOut) -> Decimal:
    """Round a derived valuation only at the Main-currency API boundary."""
    return quantize_asset_amount(value, main_asset)


def quantize_exchange_rate(value: Decimal) -> Decimal:
    decimal = Decimal(value)
    if not decimal.is_finite() or decimal <= 0:
        raise HTTPException(status_code=422, detail="Exchange rate must be positive and finite")
    quantized = quantize_decimal(decimal, RATE_DECIMALS)
    if quantized == 0:
        raise HTTPException(
            status_code=422,
            detail="Exchange rate is below the supported 18-decimal precision",
        )
    if quantized.adjusted() + 1 > MAX_INTEGER_DIGITS:
        raise HTTPException(status_code=422, detail="Exchange rate has too many digits")
    return quantized


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
    if value != 0 and value.adjusted() + 1 > MAX_INTEGER_DIGITS:
        raise HTTPException(status_code=422, detail="Amount has too many integer digits")
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
    *,
    allow_archived: bool = False,
) -> Category | None:
    if category_id is None:
        return None
    category = await session.get(Category, category_id)
    if (
        category is None
        or category.workspace_id != workspace_id
        or (category.archived_at is not None and not allow_archived)
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
    return decimal_sum(Decimal(value) for value in amounts)


async def latest_rate(
    session: AsyncSession,
    *,
    workspace_id: int,
    base_asset_id: int,
    quote_asset_id: int,
) -> ExchangeRate | None:
    return (
        await session.execute(
            select(ExchangeRate)
            .join(Transaction, Transaction.id == ExchangeRate.source_transaction_id)
            .where(
                ExchangeRate.workspace_id == workspace_id,
                ExchangeRate.base_asset_id == base_asset_id,
                ExchangeRate.quote_asset_id == quote_asset_id,
                Transaction.workspace_id == workspace_id,
                Transaction.status == "posted",
            )
            .order_by(ExchangeRate.captured_at.desc(), ExchangeRate.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def valued_balance(
    session: AsyncSession,
    balance: Decimal,
    valuation_workspace_id: int,
    asset_id: int,
    base_asset: Asset,
) -> Decimal | None:
    if asset_id == base_asset.id:
        valued = balance
    else:
        manual_rate = (
            await session.execute(
                select(ManualValuationRate).where(
                    ManualValuationRate.workspace_id == valuation_workspace_id,
                    ManualValuationRate.main_asset_id == base_asset.id,
                    ManualValuationRate.asset_id == asset_id,
                )
            )
        ).scalar_one_or_none()
        if manual_rate is not None:
            valued = decimal_quotient(balance, manual_rate.displayed_rate)
        else:
            rate = await latest_rate(
                session,
                workspace_id=valuation_workspace_id,
                base_asset_id=asset_id,
                quote_asset_id=base_asset.id,
            )
            if rate is None:
                return None
            valued = decimal_product(balance, rate.rate)
    return valued


async def account_values(
    session: AsyncSession,
    account: Account,
    base_asset: Asset,
    valuation_workspace_id: int,
) -> AccountValues:
    """Return exact derived values; API callers decide where to round."""
    balance = await account_balance(session, account.id)
    return AccountValues(
        balance=balance,
        valued_balance=await valued_balance(
            session,
            balance,
            valuation_workspace_id,
            account.asset_id,
            base_asset,
        ),
    )


async def account_out(
    session: AsyncSession,
    account: Account,
    base_asset_id: int,
    valuation_workspace_id: int,
    *,
    access_role: str = "owner",
    values: AccountValues | None = None,
) -> AccountOut:
    await session.refresh(account, attribute_names=["asset"])
    base_asset = await session.get(Asset, base_asset_id)
    assert base_asset is not None
    values = values or await account_values(
        session, account, base_asset, valuation_workspace_id
    )
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
        balance=quantize_asset_amount(values.balance, account.asset),
        valued_balance=(
            quantize_main_amount(values.valued_balance, base_asset)
            if values.valued_balance is not None
            else None
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
                created_at=leg.created_at,
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
        origin=transaction.origin,
        status="deleted" if transaction.status == "voided" else transaction.status,
        created_at=transaction.created_at,
        updated_at=transaction.updated_at,
        deleted_at=transaction.voided_at,
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
        rate=quantize_exchange_rate(rate.rate),
        captured_at=rate.captured_at,
        source_transaction_id=rate.source_transaction_id,
    )
