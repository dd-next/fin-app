"""Shared Tracker persistence helpers used by ledger and Plan commands."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ledger import latest_rate, quantize_exchange_rate, validate_amount
from app.budget import round_to_quantum
from app.models import (
    Asset,
    BudgetCommitment,
    BudgetPeriod,
    PlanOccurrence,
    PlanRule,
    Transaction,
    TransactionLeg,
    Workspace,
)


def workspace_today(workspace: Workspace) -> date:
    return datetime.now(UTC).astimezone(ZoneInfo(workspace.timezone)).date()


def asset_quantum(asset: Asset) -> Decimal:
    return Decimal(1).scaleb(-asset.decimals)


def budget_period_status(period: BudgetPeriod, today: date) -> str:
    if period.closed_at is not None or today > period.end_date:
        return "ended"
    if today < period.start_date:
        return "upcoming"
    return "current"


async def period_for_date(
    session: AsyncSession, workspace_id: int, financial_date: date
) -> BudgetPeriod | None:
    return (
        await session.execute(
            select(BudgetPeriod).where(
                BudgetPeriod.workspace_id == workspace_id,
                BudgetPeriod.start_date <= financial_date,
                BudgetPeriod.end_date >= financial_date,
            )
        )
    ).scalar_one_or_none()


async def value_amount(
    session: AsyncSession,
    workspace_id: int,
    amount: Decimal,
    asset: Asset,
    base_asset: Asset,
    supplied_base_amount: Decimal | None = None,
) -> tuple[Decimal, Decimal, str]:
    """Value an absolute source amount and return frozen amount/rate/source."""
    source_amount = validate_amount(abs(Decimal(amount)), asset)
    if asset.id == base_asset.id:
        return source_amount, Decimal("1"), "identity"
    if supplied_base_amount is not None:
        frozen = validate_amount(supplied_base_amount, base_asset)
        if frozen <= 0:
            raise HTTPException(status_code=422, detail="base_amount must be positive")
        return frozen, quantize_exchange_rate(frozen / source_amount), "manual"
    rate = await latest_rate(
        session,
        workspace_id=workspace_id,
        base_asset_id=asset.id,
        quote_asset_id=base_asset.id,
    )
    if rate is None:
        raise HTTPException(
            status_code=422,
            detail=(
                f"base_amount in {base_asset.code} is required because no "
                f"{asset.code}/{base_asset.code} rate exists"
            ),
        )
    frozen = validate_amount(
        round_to_quantum(source_amount * rate.rate, asset_quantum(base_asset)),
        base_asset,
    )
    return (
        frozen,
        quantize_exchange_rate(rate.rate),
        f"exchange:{rate.source_transaction_id}",
    )


async def transaction_value_source(
    session: AsyncSession, transaction: Transaction
) -> tuple[Decimal, Asset]:
    legs = list(
        (
            await session.execute(
                select(TransactionLeg).where(
                    TransactionLeg.transaction_id == transaction.id
                )
            )
        ).scalars()
    )
    if not legs:
        raise HTTPException(status_code=422, detail="Transaction has no financial leg")
    if transaction.type in {"expense", "transfer", "exchange"}:
        candidates = [leg for leg in legs if leg.amount < 0]
    else:
        candidates = [leg for leg in legs if leg.amount > 0]
    leg = (candidates or legs)[0]
    asset = await session.get(Asset, leg.asset_id)
    assert asset is not None
    return abs(Decimal(leg.amount)), asset


async def freeze_transaction_for_period(
    session: AsyncSession,
    transaction: Transaction,
    period: BudgetPeriod,
    supplied_base_amount: Decimal | None = None,
) -> None:
    if transaction.id == period.opening_transaction_id:
        amount, asset = await transaction_value_source(session, transaction)
        base_asset = await session.get(Asset, period.base_asset_id)
        assert base_asset is not None
        frozen, rate, source = await value_amount(
            session, transaction.workspace_id, amount, asset, base_asset, supplied_base_amount
        )
        period.funding_amount = frozen
        transaction.budget_period_id = period.id
        transaction.base_amount = frozen
        transaction.base_rate = rate
        transaction.rate_source = f"opening-{source}"[:24]
        return
    amount, asset = await transaction_value_source(session, transaction)
    base_asset = await session.get(Asset, period.base_asset_id)
    assert base_asset is not None
    frozen, rate, source = await value_amount(
        session, transaction.workspace_id, amount, asset, base_asset, supplied_base_amount
    )
    transaction.budget_period_id = period.id
    transaction.base_amount = frozen
    transaction.base_rate = rate
    transaction.rate_source = source


async def attach_transaction_to_tracker(
    session: AsyncSession,
    transaction: Transaction,
    supplied_base_amount: Decimal | None = None,
    *,
    explicit_period: BudgetPeriod | None = None,
) -> BudgetPeriod | None:
    """Attach a daily-budget transaction and freeze its period valuation."""
    if transaction.type not in {"expense", "income"} and explicit_period is None:
        return None
    period = explicit_period or await period_for_date(
        session, transaction.workspace_id, transaction.local_date
    )
    if period is None:
        if transaction.type in {"expense", "income"}:
            transaction.budget_period_id = None
            transaction.base_amount = None
            transaction.base_rate = None
            transaction.rate_source = None
        return None
    await freeze_transaction_for_period(
        session, transaction, period, supplied_base_amount
    )
    return period


async def sync_plan_fulfillment(
    session: AsyncSession,
    occurrence: PlanOccurrence,
    transaction: Transaction,
    supplied_base_amount: Decimal | None = None,
) -> None:
    commitments = list(
        (
            await session.execute(
                select(BudgetCommitment).where(
                    BudgetCommitment.plan_occurrence_id == occurrence.id,
                    BudgetCommitment.status != "cancelled",
                )
            )
        ).scalars()
    )
    if commitments:
        commitment = commitments[0]
        period = await session.get(BudgetPeriod, commitment.budget_period_id)
        assert period is not None
        await attach_transaction_to_tracker(
            session,
            transaction,
            supplied_base_amount,
            explicit_period=period,
        )
        commitment.status = "fulfilled"
    else:
        await attach_transaction_to_tracker(
            session, transaction, supplied_base_amount
        )


async def reopen_plan_commitment(
    session: AsyncSession, occurrence: PlanOccurrence
) -> None:
    commitments = list(
        (
            await session.execute(
                select(BudgetCommitment).where(
                    BudgetCommitment.plan_occurrence_id == occurrence.id,
                    BudgetCommitment.status == "fulfilled",
                )
            )
        ).scalars()
    )
    for commitment in commitments:
        commitment.status = "reserved"


async def next_income_date(
    session: AsyncSession,
    workspace_id: int,
    after: date,
    *,
    exclude_occurrence_id: int | None = None,
) -> date | None:
    statement = (
        select(PlanOccurrence.due_date)
        .join(PlanRule, PlanRule.id == PlanOccurrence.plan_rule_id)
        .where(
            PlanRule.workspace_id == workspace_id,
            PlanRule.kind == "income",
            PlanRule.is_active.is_(True),
            PlanOccurrence.due_date > after,
            PlanOccurrence.status.in_(("planned", "overdue")),
        )
        .order_by(PlanOccurrence.due_date, PlanOccurrence.id)
        .limit(1)
    )
    if exclude_occurrence_id is not None:
        statement = statement.where(PlanOccurrence.id != exclude_occurrence_id)
    return (await session.execute(statement)).scalar_one_or_none()


async def commitment_candidates(
    session: AsyncSession,
    workspace_id: int,
    start_date: date,
    end_date: date,
) -> list[tuple[PlanOccurrence, PlanRule, Asset]]:
    return list(
        (
            await session.execute(
                select(PlanOccurrence, PlanRule, Asset)
                .join(PlanRule, PlanRule.id == PlanOccurrence.plan_rule_id)
                .join(Asset, Asset.id == PlanRule.asset_id)
                .where(
                    PlanRule.workspace_id == workspace_id,
                    PlanRule.is_active.is_(True),
                    PlanOccurrence.due_date >= start_date,
                    PlanOccurrence.due_date <= end_date,
                    PlanOccurrence.status != "skipped",
                    (
                        (PlanRule.kind.in_(("required_expense", "reserve_transfer")))
                        | (PlanRule.is_required.is_(True))
                    ),
                    PlanRule.kind != "income",
                )
                .order_by(PlanOccurrence.due_date, PlanOccurrence.id)
            )
        ).all()
    )


async def build_commitment_proposals(
    session: AsyncSession,
    workspace: Workspace,
    base_asset: Asset,
    start_date: date,
    end_date: date,
    overrides: dict[int, Decimal] | None = None,
) -> list[dict]:
    overrides = overrides or {}
    proposals: list[dict] = []
    for occurrence, rule, source_asset in await commitment_candidates(
        session, workspace.id, start_date, end_date
    ):
        supplied = overrides.get(occurrence.id)
        try:
            planned, _, _ = await value_amount(
                session,
                workspace.id,
                occurrence.planned_amount,
                source_asset,
                base_asset,
                supplied,
            )
        except HTTPException as exc:
            if exc.status_code != 422 or supplied is not None:
                raise
            planned = None
        proposals.append(
            {
                "plan_occurrence_id": occurrence.id,
                "type": (
                    "reserve_transfer"
                    if rule.kind == "reserve_transfer"
                    else "required_expense"
                ),
                "name": rule.name,
                "due_date": occurrence.due_date,
                "planned_amount": planned,
                "source_amount": occurrence.planned_amount,
                "source_asset": source_asset,
                "needs_base_amount": planned is None,
            }
        )
    return proposals


async def build_period_proposal(
    session: AsyncSession,
    workspace: Workspace,
    transaction: Transaction | None,
    *,
    opening_occurrence_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    base_asset: Asset | None = None,
    funding_amount: Decimal | None = None,
    commitment_overrides: dict[int, Decimal] | None = None,
) -> dict:
    base_asset = base_asset or await session.get(Asset, workspace.base_asset_id)
    assert base_asset is not None
    if transaction is not None:
        if (
            transaction.workspace_id != workspace.id
            or transaction.type != "income"
            or transaction.status != "posted"
        ):
            raise HTTPException(status_code=422, detail="Opening transaction must be posted income")
        start_date = start_date or transaction.local_date
    if start_date is None:
        raise HTTPException(status_code=422, detail="start_date is required")
    if end_date is None:
        next_date = await next_income_date(
            session,
            workspace.id,
            start_date,
            exclude_occurrence_id=opening_occurrence_id,
        )
        end_date = next_date - timedelta(days=1) if next_date is not None else None
    if end_date is not None and end_date < start_date:
        raise HTTPException(status_code=422, detail="end_date must not precede start_date")

    frozen_funding = funding_amount
    if frozen_funding is not None:
        frozen_funding = validate_amount(frozen_funding, base_asset)
    elif transaction is not None:
        amount, source_asset = await transaction_value_source(session, transaction)
        try:
            frozen_funding, _, _ = await value_amount(
                session, workspace.id, amount, source_asset, base_asset
            )
        except HTTPException as exc:
            if exc.status_code != 422:
                raise
            frozen_funding = None

    commitments = (
        await build_commitment_proposals(
            session,
            workspace,
            base_asset,
            start_date,
            end_date,
            commitment_overrides,
        )
        if end_date is not None
        else []
    )
    return {
        "opening_transaction_id": transaction.id if transaction else None,
        "opening_plan_occurrence_id": opening_occurrence_id,
        "start_date": start_date,
        "end_date": end_date,
        "base_asset": base_asset,
        "funding_amount": frozen_funding,
        "needs_end_date": end_date is None,
        "needs_funding_amount": frozen_funding is None,
        "commitments": commitments,
    }
