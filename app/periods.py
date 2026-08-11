"""Owner-private account periods and signed-leg replay."""

from datetime import UTC, date, datetime, time, timedelta
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_user
from app.budget import AllowanceResult, compute_allowance, round_to_quantum
from app.db import get_session
from app.ledger import (
    account_balance,
    decimal_difference,
    decimal_sum,
    require_owned_account,
)
from app.models import (
    Account,
    AccountPeriod,
    Transaction,
    TransactionLeg,
    User,
    Workspace,
)
from app.schemas import (
    AccountPeriodCreate,
    AccountPeriodClosedOut,
    AccountPeriodCurrentOut,
    AccountPeriodEndedOut,
    AccountPeriodOut,
    AccountPeriodPatch,
    AssetOut,
)


router = APIRouter(tags=["account-periods"])
PERIOD_BUSINESS_FIELDS = {"start_date", "end_date", "rollover_policy"}


@dataclass(frozen=True)
class PeriodImpact:
    ended: bool = False
    closed: bool = False

    def merge(self, other: "PeriodImpact") -> "PeriodImpact":
        return PeriodImpact(
            ended=self.ended or other.ended,
            closed=self.closed or other.closed,
        )


@dataclass(frozen=True)
class PeriodBalanceInputs:
    reference_time: datetime
    current_balance: Decimal
    window_net: Decimal
    reconciliation_delta: Decimal
    calculation_opening_balance: Decimal
    movements: tuple[tuple[date, Decimal], ...]


@dataclass(frozen=True)
class PeriodAllowanceProjection:
    balance_inputs: PeriodBalanceInputs
    effective_effects: tuple[tuple[date, Decimal], ...]
    allowance: AllowanceResult


def workspace_today(workspace: Workspace) -> date:
    return workspace_day_at(
        workspace,
        datetime.now(UTC).replace(tzinfo=None),
    )


def utc_reference_time() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def workspace_day_at(workspace: Workspace, reference_time: datetime) -> date:
    return reference_time.replace(tzinfo=UTC).astimezone(
        ZoneInfo(workspace.timezone)
    ).date()


def workspace_day_boundary(workspace: Workspace, day: date) -> datetime:
    return (
        datetime.combine(day, time.min, tzinfo=ZoneInfo(workspace.timezone))
        .astimezone(UTC)
        .replace(tzinfo=None)
    )


async def reserve_period_writer(session: AsyncSession) -> None:
    """Reserve SQLite period writes before reading mutable lifecycle state."""
    await session.execute(text("BEGIN IMMEDIATE"))


async def posted_balance_at(
    session: AsyncSession,
    *,
    account_id: int,
    boundary: datetime,
) -> Decimal:
    amounts = (
        await session.execute(
            select(TransactionLeg.amount)
            .join(Transaction, Transaction.id == TransactionLeg.transaction_id)
            .where(
                TransactionLeg.account_id == account_id,
                TransactionLeg.created_at <= boundary,
                Transaction.status == "posted",
            )
        )
    ).scalars()
    return decimal_sum(Decimal(value) for value in amounts)


async def initial_snapshot_at(
    session: AsyncSession,
    *,
    account_id: int,
    start_date: date,
    workspace: Workspace,
    today: date,
    exclude_period_id: int | None = None,
) -> datetime:
    snapshot_at = workspace_day_boundary(workspace, start_date)
    statement = select(AccountPeriod).where(
        AccountPeriod.account_id == account_id,
        or_(
            AccountPeriod.closed_at.is_not(None),
            AccountPeriod.end_date < today,
        ),
    )
    if exclude_period_id is not None:
        statement = statement.where(AccountPeriod.id != exclude_period_id)
    predecessors = list((await session.execute(statement)).scalars())
    for predecessor in predecessors:
        predecessor_boundary = predecessor.closed_at or workspace_day_boundary(
            workspace, predecessor.end_date + timedelta(days=1)
        )
        snapshot_at = max(snapshot_at, predecessor_boundary)
    return snapshot_at


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
                        AccountPeriod.snapshot_at < leg.created_at,
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
    if impact.ended and workspace_owner and not confirmed:
        raise HTTPException(
            status_code=409,
            detail="Ended account period change requires explicit confirmation",
        )


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


async def ensure_no_current_period(
    session: AsyncSession,
    *,
    account_id: int,
    start_date: date,
    end_date: date,
    today: date,
) -> None:
    if not (start_date <= today <= end_date):
        return
    current_id = (
        await session.execute(
            select(AccountPeriod.id)
            .where(
                AccountPeriod.account_id == account_id,
                AccountPeriod.closed_at.is_(None),
                AccountPeriod.start_date <= today,
                AccountPeriod.end_date >= today,
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if current_id is not None:
        raise HTTPException(
            status_code=409, detail="Account already has a current period"
        )


async def ensure_no_other_current_period(
    session: AsyncSession,
    *,
    account_id: int,
    today: date,
    exclude_period_id: int,
) -> None:
    current_id = (
        await session.execute(
            select(AccountPeriod.id)
            .where(
                AccountPeriod.account_id == account_id,
                AccountPeriod.id != exclude_period_id,
                AccountPeriod.closed_at.is_(None),
                AccountPeriod.start_date <= today,
                AccountPeriod.end_date >= today,
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if current_id is not None:
        raise HTTPException(
            status_code=409, detail="Account already has a current period"
        )


async def period_movements(
    session: AsyncSession,
    period: AccountPeriod,
    *,
    reference_time: datetime,
    include_reference_time: bool = True,
) -> list[tuple[date, Decimal]]:
    statement = (
        select(Transaction.local_date, TransactionLeg.amount)
        .join(Transaction, Transaction.id == TransactionLeg.transaction_id)
        .where(
            TransactionLeg.account_id == period.account_id,
            TransactionLeg.created_at > period.snapshot_at,
            Transaction.status == "posted",
        )
        .order_by(Transaction.local_date, TransactionLeg.id)
    )
    cutoff = (
        TransactionLeg.created_at <= reference_time
        if include_reference_time
        else TransactionLeg.created_at < reference_time
    )
    rows = (await session.execute(statement.where(cutoff))).all()
    return [(local_date, Decimal(amount)) for local_date, amount in rows]


async def current_period_balance_inputs(
    session: AsyncSession,
    period: AccountPeriod,
    *,
    reference_time: datetime,
) -> PeriodBalanceInputs:
    if period.closed_at is not None:
        raise ValueError("Closed period balance inputs use stored snapshots")
    current_balance = await account_balance(
        session,
        period.account_id,
        through=reference_time,
    )
    movements = tuple(
        await period_movements(
            session,
            period,
            reference_time=reference_time,
        )
    )
    window_net = decimal_sum(amount for _, amount in movements)
    reconciliation_delta = decimal_difference(
        current_balance,
        decimal_sum((period.opening_balance, window_net)),
    )
    calculation_opening_balance = decimal_sum(
        (period.opening_balance, reconciliation_delta)
    )
    return PeriodBalanceInputs(
        reference_time=reference_time,
        current_balance=current_balance,
        window_net=window_net,
        reconciliation_delta=reconciliation_delta,
        calculation_opening_balance=calculation_opening_balance,
        movements=movements,
    )


def effective_period_effects(
    period: AccountPeriod,
    movements: tuple[tuple[date, Decimal], ...],
    *,
    reference_day: date,
) -> tuple[tuple[date, Decimal], ...]:
    return tuple(
        (
            min(max(financial_day, period.start_date), reference_day),
            amount,
        )
        for financial_day, amount in movements
    )


async def current_period_allowance(
    session: AsyncSession,
    period: AccountPeriod,
    *,
    reference_time: datetime,
    reference_day: date,
    quantum: Decimal,
) -> PeriodAllowanceProjection:
    balance_inputs = await current_period_balance_inputs(
        session,
        period,
        reference_time=reference_time,
    )
    effects = effective_period_effects(
        period,
        balance_inputs.movements,
        reference_day=reference_day,
    )
    allowance = compute_allowance(
        balance_inputs.calculation_opening_balance,
        period.start_date,
        period.end_date,
        effects,
        rollover_policy=period.rollover_policy,
        today=reference_day,
        quantum=quantum,
    )
    if allowance.current_balance != balance_inputs.current_balance:
        raise RuntimeError("Period allowance does not match live ledger balance")
    return PeriodAllowanceProjection(
        balance_inputs=balance_inputs,
        effective_effects=effects,
        allowance=allowance,
    )


async def account_period_out(
    session: AsyncSession,
    period: AccountPeriod,
    account: Account,
    *,
    reference_time: datetime,
    today: date,
) -> AccountPeriodOut:
    await session.refresh(period, attribute_names=["asset"])
    status = period_status(period, today)
    quantum = Decimal(1).scaleb(-period.asset.decimals)
    opening_balance = round_to_quantum(period.opening_balance, quantum)
    common = {
        "id": period.id,
        "account_id": period.account_id,
        "asset": AssetOut.model_validate(period.asset),
        "created_by_user_id": period.created_by_user_id,
        "start_date": period.start_date,
        "end_date": period.end_date,
        "snapshot_at": period.snapshot_at,
        "opening_balance": opening_balance,
        "rollover_policy": period.rollover_policy,
        "created_at": period.created_at,
    }
    if status == "current":
        projection = await current_period_allowance(
            session,
            period,
            reference_time=reference_time,
            reference_day=today,
            quantum=quantum,
        )
        current_balance = round_to_quantum(
            projection.balance_inputs.current_balance, quantum
        )
        return AccountPeriodCurrentOut(
            **common,
            status="current",
            current_balance=current_balance,
            available_today=projection.allowance.available_today,
        )
    if status == "ended":
        return AccountPeriodEndedOut(
            **common,
            status="ended",
        )
    if status != "closed":
        raise RuntimeError("Future account periods are unsupported")
    assert period.closed_at is not None
    assert period.closing_balance is not None
    closing_balance = round_to_quantum(period.closing_balance, quantum)
    return AccountPeriodClosedOut(
        **common,
        status="closed",
        closed_at=period.closed_at,
        closing_balance=closing_balance,
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
    # SQLite begins deferred transactions by default. Reserve the writer before
    # the current-period guard and snapshot reads so concurrent creates cannot
    # both observe the same account as eligible.
    await reserve_period_writer(session)
    account = await require_owned_account(session, account_id, user.id)
    workspace = await session.get(Workspace, account.workspace_id)
    assert workspace is not None
    reference_time = utc_reference_time()
    today = workspace_day_at(workspace, reference_time)
    if "start_date" in body.model_fields_set and body.start_date is None:
        raise HTTPException(status_code=422, detail="Period fields cannot be null")
    if "rollover_policy" in body.model_fields_set and body.rollover_policy is None:
        raise HTTPException(status_code=422, detail="Period fields cannot be null")
    start_date = body.start_date or today
    rollover_policy = body.rollover_policy or "redistribute_remaining_days"
    if body.end_date < start_date:
        raise HTTPException(status_code=422, detail="End date must not precede start date")
    if start_date > today:
        raise HTTPException(status_code=422, detail="Start date must not be in the future")
    await ensure_no_current_period(
        session,
        account_id=account.id,
        start_date=start_date,
        end_date=body.end_date,
        today=today,
    )
    snapshot_at = await initial_snapshot_at(
        session,
        account_id=account.id,
        start_date=start_date,
        workspace=workspace,
        today=today,
    )
    if snapshot_at >= workspace_day_boundary(
        workspace, body.end_date + timedelta(days=1)
    ):
        raise HTTPException(
            status_code=422,
            detail="Period snapshot must precede end boundary",
        )
    period = AccountPeriod(
        account_id=account.id,
        asset_id=account.asset_id,
        created_by_user_id=user.id,
        start_date=start_date,
        end_date=body.end_date,
        snapshot_at=snapshot_at,
        opening_balance=await posted_balance_at(
            session, account_id=account.id, boundary=snapshot_at
        ),
        rollover_policy=rollover_policy,
    )
    session.add(period)
    await session.commit()
    await session.refresh(period)
    return await account_period_out(
        session,
        period,
        account,
        reference_time=reference_time,
        today=today,
    )


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
    reference_time = utc_reference_time()
    today = workspace_day_at(workspace, reference_time)
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
    return [
        await account_period_out(
            session,
            period,
            account,
            reference_time=reference_time,
            today=today,
        )
        for period in periods
    ]


@router.get(
    "/accounts/{account_id}/periods/current",
    response_model=AccountPeriodCurrentOut | None,
)
async def get_current_account_period(
    account_id: int,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    account = await require_owned_account(
        session, account_id, user.id, allow_archived=True
    )
    workspace = await session.get(Workspace, account.workspace_id)
    assert workspace is not None
    reference_time = utc_reference_time()
    today = workspace_day_at(workspace, reference_time)
    period = (
        await session.execute(
            select(AccountPeriod)
            .where(
                AccountPeriod.account_id == account.id,
                AccountPeriod.closed_at.is_(None),
                AccountPeriod.start_date <= today,
                AccountPeriod.end_date >= today,
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if period is None:
        return None
    return await account_period_out(
        session,
        period,
        account,
        reference_time=reference_time,
        today=today,
    )


@router.get("/account-periods/{period_id}", response_model=AccountPeriodOut)
async def get_account_period(
    period_id: int,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    period, account = await require_private_period(session, period_id, user.id)
    workspace = await session.get(Workspace, account.workspace_id)
    assert workspace is not None
    reference_time = utc_reference_time()
    today = workspace_day_at(workspace, reference_time)
    return await account_period_out(
        session,
        period,
        account,
        reference_time=reference_time,
        today=today,
    )


@router.patch("/account-periods/{period_id}", response_model=AccountPeriodOut)
async def patch_account_period(
    period_id: int,
    body: AccountPeriodPatch,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    # Start-date replay is a financial boundary change. Reserve the SQLite
    # writer before loading lifecycle or ledger state so a stale request must
    # observe any predecessor/successor accepted ahead of it.
    await reserve_period_writer(session)
    period, account = await require_private_period(session, period_id, user.id)
    workspace = await session.get(Workspace, account.workspace_id)
    assert workspace is not None
    reference_time = utc_reference_time()
    today = workspace_day_at(workspace, reference_time)
    changed_fields = body.model_fields_set & PERIOD_BUSINESS_FIELDS
    if not changed_fields:
        raise HTTPException(
            status_code=422, detail="At least one period field is required"
        )
    if period.closed_at is not None:
        raise HTTPException(status_code=409, detail="Closed account period is read-only")
    if period_status(period, today) == "ended":
        raise HTTPException(status_code=409, detail="Ended account period is read-only")
    if any(getattr(body, field) is None for field in changed_fields):
        raise HTTPException(status_code=422, detail="Period fields cannot be null")
    start_date = body.start_date if "start_date" in changed_fields else period.start_date
    end_date = body.end_date if "end_date" in changed_fields else period.end_date
    if start_date > today:
        raise HTTPException(status_code=422, detail="Start date must not be in the future")
    if end_date < start_date:
        raise HTTPException(status_code=422, detail="End date must not precede start date")
    await ensure_no_other_current_period(
        session,
        account_id=account.id,
        exclude_period_id=period.id,
        today=today,
    )
    snapshot_at = period.snapshot_at
    opening_balance = period.opening_balance
    if "start_date" in changed_fields:
        snapshot_at = await initial_snapshot_at(
            session,
            account_id=account.id,
            start_date=start_date,
            workspace=workspace,
            today=today,
            exclude_period_id=period.id,
        )
        opening_balance = await posted_balance_at(
            session,
            account_id=account.id,
            boundary=snapshot_at,
        )
    if snapshot_at >= workspace_day_boundary(
        workspace, end_date + timedelta(days=1)
    ):
        raise HTTPException(
            status_code=422,
            detail="Period snapshot must precede end boundary",
        )
    if "start_date" in changed_fields:
        period.start_date = start_date
        period.snapshot_at = snapshot_at
        period.opening_balance = opening_balance
    if "end_date" in changed_fields:
        period.end_date = end_date
    if "rollover_policy" in changed_fields:
        period.rollover_policy = body.rollover_policy
    await session.commit()
    await session.refresh(period)
    return await account_period_out(
        session,
        period,
        account,
        reference_time=reference_time,
        today=today,
    )


@router.post("/account-periods/{period_id}/close", response_model=AccountPeriodOut)
async def close_account_period(
    period_id: int,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    await reserve_period_writer(session)
    period, account = await require_private_period(session, period_id, user.id)
    workspace = await session.get(Workspace, account.workspace_id)
    assert workspace is not None
    reference_time = utc_reference_time()
    today = workspace_day_at(workspace, reference_time)
    status = period_status(period, today)
    if status == "closed":
        raise HTTPException(status_code=409, detail="Account period is already closed")
    if status == "ended":
        raise HTTPException(status_code=409, detail="Ended account period is read-only")
    if status != "current":
        raise HTTPException(status_code=409, detail="Only a current period can be closed")
    closing_balance = await posted_balance_at(
        session, account_id=account.id, boundary=reference_time
    )
    period.closed_at = reference_time
    period.closing_balance = closing_balance
    await session.commit()
    await session.refresh(period)
    return await account_period_out(
        session,
        period,
        account,
        reference_time=reference_time,
        today=today,
    )
