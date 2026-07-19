"""Owner-private account periods and signed-leg replay."""

from datetime import UTC, date, datetime
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_user
from app.budget import compute_budget
from app.db import get_session
from app.ledger import decimal_negate, decimal_sum, require_owned_account, validate_amount
from app.models import (
    Account,
    AccountPeriod,
    PlanOccurrence,
    PlanRule,
    RebaseEvent,
    Transaction,
    TransactionLeg,
    User,
    Workspace,
)
from app.schemas import (
    AccountPeriodCreate,
    AccountPeriodOut,
    AccountPeriodPatch,
    AssetOut,
)


router = APIRouter(tags=["account-periods"])
OPEN_PLAN_STATUSES = {"planned", "overdue"}


@dataclass(frozen=True)
class PeriodImpact:
    ended: bool = False
    closed: bool = False

    def merge(self, other: "PeriodImpact") -> "PeriodImpact":
        return PeriodImpact(
            ended=self.ended or other.ended,
            closed=self.closed or other.closed,
        )


def workspace_today(workspace: Workspace) -> date:
    return datetime.now(UTC).astimezone(ZoneInfo(workspace.timezone)).date()


def period_status(period: AccountPeriod, today: date) -> str:
    if period.closed_at is not None:
        return "closed"
    if today < period.start_date:
        return "upcoming"
    if today > period.end_date:
        return "ended"
    return "current"


async def movement_period_impact(
    session: AsyncSession,
    *,
    local_date: date,
    legs: list[TransactionLeg],
) -> PeriodImpact:
    """Classify hidden period state changed by the supplied persisted legs."""
    impact = PeriodImpact()
    workspace_cache: dict[int, Workspace] = {}
    account_cache: dict[int, Account] = {}
    seen_periods: set[int] = set()
    for leg in legs:
        if leg.account_id is None or leg.created_at is None:
            continue
        periods = list(
            (
                await session.execute(
                    select(AccountPeriod).where(
                        AccountPeriod.account_id == leg.account_id,
                        AccountPeriod.created_at < leg.created_at,
                        AccountPeriod.start_date <= local_date,
                        AccountPeriod.end_date >= local_date,
                    )
                )
            ).scalars()
        )
        if not periods:
            continue
        account = account_cache.get(leg.account_id)
        if account is None:
            account = await session.get(Account, leg.account_id)
            assert account is not None
            account_cache[account.id] = account
        workspace = workspace_cache.get(account.workspace_id)
        if workspace is None:
            workspace = await session.get(Workspace, account.workspace_id)
            assert workspace is not None
            workspace_cache[workspace.id] = workspace
        today = workspace_today(workspace)
        for period in periods:
            if period.id in seen_periods:
                continue
            seen_periods.add(period.id)
            status = period_status(period, today)
            impact = impact.merge(
                PeriodImpact(ended=status == "ended", closed=status == "closed")
            )
    return impact


async def transaction_period_impact(
    session: AsyncSession,
    transaction: Transaction,
    *,
    legs: list[TransactionLeg] | None = None,
    include_children: bool = False,
) -> PeriodImpact:
    if legs is None:
        legs = list(
            (
                await session.execute(
                    select(TransactionLeg).where(
                        TransactionLeg.transaction_id == transaction.id
                    )
                )
            ).scalars()
        )
    impact = await movement_period_impact(
        session, local_date=transaction.local_date, legs=legs
    )
    if not include_children:
        return impact
    children = list(
        (
            await session.execute(
                select(Transaction).where(
                    Transaction.parent_transaction_id == transaction.id,
                    Transaction.status == "posted",
                )
            )
        ).scalars()
    )
    for child in children:
        impact = impact.merge(await transaction_period_impact(session, child))
    return impact


def enforce_transaction_period_impact(
    impact: PeriodImpact,
    *,
    confirmed: bool,
    workspace_owner: bool,
) -> None:
    if impact.closed:
        detail = (
            "Closed account period is read-only"
            if workspace_owner
            else "Transaction cannot be changed"
        )
        raise HTTPException(status_code=409, detail=detail)
    if impact.ended and not confirmed:
        detail = (
            "Ended account period change requires explicit confirmation"
            if workspace_owner
            else "Transaction change requires explicit confirmation"
        )
        raise HTTPException(status_code=409, detail=detail)


async def require_private_period(
    session: AsyncSession, period_id: int, user_id: int
) -> tuple[AccountPeriod, Account]:
    period = await session.get(AccountPeriod, period_id)
    if period is None:
        raise HTTPException(status_code=404, detail="Account period not found")
    try:
        account = await require_owned_account(
            session, period.account_id, user_id, allow_archived=True
        )
    except HTTPException as exc:
        if exc.status_code == 404:
            raise HTTPException(status_code=404, detail="Account period not found")
        raise
    return period, account


async def ensure_no_overlap(
    session: AsyncSession,
    *,
    account_id: int,
    start_date: date,
    end_date: date,
    exclude_period_id: int | None = None,
) -> None:
    statement = select(AccountPeriod.id).where(
        AccountPeriod.account_id == account_id,
        AccountPeriod.start_date <= end_date,
        AccountPeriod.end_date >= start_date,
    )
    if exclude_period_id is not None:
        statement = statement.where(AccountPeriod.id != exclude_period_id)
    if (await session.execute(statement.limit(1))).scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409, detail="Account period dates overlap an existing period"
        )


async def period_movements(
    session: AsyncSession, period: AccountPeriod
) -> list[tuple[date, Decimal]]:
    rows = (
        await session.execute(
            select(Transaction.local_date, TransactionLeg.amount)
            .join(Transaction, Transaction.id == TransactionLeg.transaction_id)
            .where(
                TransactionLeg.account_id == period.account_id,
                TransactionLeg.created_at > period.created_at,
                Transaction.local_date >= period.start_date,
                Transaction.local_date <= period.end_date,
                Transaction.status == "posted",
            )
            .order_by(Transaction.local_date, TransactionLeg.id)
        )
    ).all()
    return [(local_date, Decimal(amount)) for local_date, amount in rows]


async def planned_amount(
    session: AsyncSession, account: Account, period: AccountPeriod
) -> Decimal:
    amounts = (
        await session.execute(
            select(PlanOccurrence.planned_amount)
            .join(PlanRule, PlanRule.id == PlanOccurrence.plan_rule_id)
            .where(
                PlanRule.workspace_id == account.workspace_id,
                PlanOccurrence.status.in_(OPEN_PLAN_STATUSES),
                PlanOccurrence.due_date >= period.start_date,
                PlanOccurrence.due_date <= period.end_date,
                or_(
                    PlanRule.default_from_account_id == account.id,
                    PlanRule.default_to_account_id == account.id,
                ),
            )
        )
    ).scalars()
    return decimal_sum(Decimal(value) for value in amounts)


async def account_period_out(
    session: AsyncSession,
    period: AccountPeriod,
    account: Account,
) -> AccountPeriodOut:
    workspace = await session.get(Workspace, account.workspace_id)
    assert workspace is not None
    await session.refresh(period, attribute_names=["asset"])
    today = workspace_today(workspace)
    movements = await period_movements(session, period)
    rebase_days = list(
        (
            await session.execute(
                select(RebaseEvent.day).where(
                    RebaseEvent.account_period_id == period.id
                )
            )
        ).scalars()
    )
    quantum = Decimal(1).scaleb(-period.asset.decimals)
    budget = compute_budget(
        Decimal(period.funding_amount),
        period.start_date,
        period.end_date,
        (
            (local_date, decimal_negate(amount))
            for local_date, amount in movements
        ),
        today=today,
        rebase_days=rebase_days,
        quantum=quantum,
    )
    return AccountPeriodOut(
        id=period.id,
        account_id=period.account_id,
        asset=AssetOut.model_validate(period.asset),
        created_by_user_id=period.created_by_user_id,
        start_date=period.start_date,
        end_date=period.end_date,
        funding_amount=period.funding_amount,
        available_today=budget.per_day_today,
        remaining=budget.remaining_money,
        planned=await planned_amount(session, account, period),
        status=period_status(period, today),
        created_at=period.created_at,
        closed_at=period.closed_at,
    )


@router.post(
    "/accounts/{account_id}/periods",
    response_model=AccountPeriodOut,
    status_code=201,
)
async def create_account_period(
    account_id: int,
    body: AccountPeriodCreate,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    account = await require_owned_account(session, account_id, user.id)
    if body.end_date < body.start_date:
        raise HTTPException(status_code=422, detail="End date must not precede start date")
    funding = validate_amount(body.funding_amount, account.asset, allow_zero=True)
    await ensure_no_overlap(
        session,
        account_id=account.id,
        start_date=body.start_date,
        end_date=body.end_date,
    )
    period = AccountPeriod(
        account_id=account.id,
        asset_id=account.asset_id,
        created_by_user_id=user.id,
        start_date=body.start_date,
        end_date=body.end_date,
        funding_amount=funding,
    )
    session.add(period)
    await session.commit()
    await session.refresh(period)
    return await account_period_out(session, period, account)


@router.get(
    "/accounts/{account_id}/periods", response_model=list[AccountPeriodOut]
)
async def list_account_periods(
    account_id: int,
    scope: Literal["all", "current", "history"] = Query(default="all"),
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    account = await require_owned_account(
        session, account_id, user.id, allow_archived=True
    )
    workspace = await session.get(Workspace, account.workspace_id)
    assert workspace is not None
    today = workspace_today(workspace)
    statement = select(AccountPeriod).where(AccountPeriod.account_id == account.id)
    if scope == "current":
        statement = statement.where(
            AccountPeriod.closed_at.is_(None),
            AccountPeriod.start_date <= today,
            AccountPeriod.end_date >= today,
        )
    elif scope == "history":
        statement = statement.where(
            or_(AccountPeriod.closed_at.is_not(None), AccountPeriod.end_date < today)
        )
    periods = list(
        (
            await session.execute(
                statement.order_by(AccountPeriod.start_date.desc(), AccountPeriod.id.desc())
            )
        ).scalars()
    )
    return [await account_period_out(session, period, account) for period in periods]


@router.get("/account-periods/{period_id}", response_model=AccountPeriodOut)
async def get_account_period(
    period_id: int,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    period, account = await require_private_period(session, period_id, user.id)
    return await account_period_out(session, period, account)


@router.patch("/account-periods/{period_id}", response_model=AccountPeriodOut)
async def patch_account_period(
    period_id: int,
    body: AccountPeriodPatch,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    period, account = await require_private_period(session, period_id, user.id)
    workspace = await session.get(Workspace, account.workspace_id)
    assert workspace is not None
    today = workspace_today(workspace)
    changed_fields = body.model_fields_set - {"confirm_ended_period"}
    if not changed_fields:
        return await account_period_out(session, period, account)
    if period.closed_at is not None:
        raise HTTPException(status_code=409, detail="Closed account period is read-only")
    if any(getattr(body, field) is None for field in changed_fields):
        raise HTTPException(status_code=422, detail="Period fields cannot be null")
    start_date = body.start_date if "start_date" in changed_fields else period.start_date
    end_date = body.end_date if "end_date" in changed_fields else period.end_date
    if end_date < start_date:
        raise HTTPException(status_code=422, detail="End date must not precede start date")
    if (
        (period.end_date < today or end_date < today)
        and not body.confirm_ended_period
    ):
        raise HTTPException(
            status_code=409,
            detail="Ended account period change requires explicit confirmation",
        )
    await ensure_no_overlap(
        session,
        account_id=account.id,
        start_date=start_date,
        end_date=end_date,
        exclude_period_id=period.id,
    )
    if "start_date" in changed_fields:
        period.start_date = start_date
    if "end_date" in changed_fields:
        period.end_date = end_date
    if "funding_amount" in changed_fields:
        assert body.funding_amount is not None
        period.funding_amount = validate_amount(
            body.funding_amount, account.asset, allow_zero=True
        )
    await session.commit()
    await session.refresh(period)
    return await account_period_out(session, period, account)


@router.post("/account-periods/{period_id}/close", response_model=AccountPeriodOut)
async def close_account_period(
    period_id: int,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    period, account = await require_private_period(session, period_id, user.id)
    if period.closed_at is not None:
        raise HTTPException(status_code=409, detail="Account period is already closed")
    period.closed_at = datetime.now(UTC).replace(tzinfo=None)
    await session.commit()
    await session.refresh(period)
    return await account_period_out(session, period, account)
