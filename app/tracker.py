"""Owner-private Tracker periods, commitments, and deterministic summaries."""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.access import require_workspace_owner
from app.auth import require_user
from app.budget import compute_budget, preview_after
from app.db import get_session
from app.ledger import quantize_exchange_rate, require_asset_code, validate_amount
from app.models import (
    Asset,
    BudgetCommitment,
    BudgetPeriod,
    PlanOccurrence,
    PlanRule,
    RebaseEvent,
    Transaction,
    User,
    Workspace,
    utcnow,
)
from app.plan import materialize_workspace
from app.schemas import (
    AssetOut,
    BudgetCommitmentCancelIn,
    BudgetCommitmentCreate,
    BudgetCommitmentOut,
    BudgetCommitmentPatch,
    BudgetPeriodCreate,
    BudgetPeriodOut,
    BudgetPeriodPatch,
    BudgetPeriodPreviewIn,
    PeriodProposalOut,
    SavingsDecisionIn,
    SavingsPromptOut,
    TrackerPreviewOut,
    TrackerSummaryOut,
)
from app.tracker_service import (
    asset_quantum,
    attach_transaction_to_tracker,
    budget_period_status,
    build_period_proposal,
    sync_plan_fulfillment,
    transaction_value_source,
    value_amount,
    workspace_today,
)


router = APIRouter(tags=["tracker"])
ZERO = Decimal("0")


async def require_period(
    session: AsyncSession, workspace_id: int, period_id: int
) -> BudgetPeriod:
    period = await session.get(BudgetPeriod, period_id)
    if period is None or period.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Budget period not found")
    return period


async def resolve_opening(
    session: AsyncSession,
    workspace_id: int,
    transaction_id: int | None,
    occurrence_id: int | None,
) -> tuple[Transaction | None, PlanOccurrence | None]:
    occurrence = await session.get(PlanOccurrence, occurrence_id) if occurrence_id else None
    if occurrence is not None:
        rule = await session.get(PlanRule, occurrence.plan_rule_id)
        if rule is None or rule.workspace_id != workspace_id or rule.kind != "income":
            raise HTTPException(status_code=422, detail="Invalid opening Plan occurrence")
        if transaction_id is None:
            transaction_id = occurrence.transaction_id
    elif occurrence_id is not None:
        raise HTTPException(status_code=422, detail="Invalid opening Plan occurrence")
    transaction = await session.get(Transaction, transaction_id) if transaction_id else None
    if transaction_id is not None and transaction is None:
        raise HTTPException(status_code=422, detail="Invalid opening transaction")
    if transaction is not None:
        if (
            transaction.workspace_id != workspace_id
            or transaction.type != "income"
            or transaction.status != "posted"
        ):
            raise HTTPException(status_code=422, detail="Opening transaction must be posted income")
        linked = (
            await session.execute(
                select(PlanOccurrence).join(
                    PlanRule, PlanRule.id == PlanOccurrence.plan_rule_id
                ).where(
                    PlanOccurrence.transaction_id == transaction.id,
                    PlanRule.workspace_id == workspace_id,
                    PlanRule.kind == "income",
                )
            )
        ).scalar_one_or_none()
        if occurrence is None:
            occurrence = linked
        elif occurrence.transaction_id != transaction.id:
            raise HTTPException(
                status_code=422,
                detail="Opening occurrence is not linked to the opening transaction",
            )
    return transaction, occurrence


async def proposed_period(
    session: AsyncSession,
    workspace: Workspace,
    body: BudgetPeriodPreviewIn,
) -> PeriodProposalOut:
    await materialize_workspace(session, workspace)
    transaction, occurrence = await resolve_opening(
        session,
        workspace.id,
        body.opening_transaction_id,
        body.opening_plan_occurrence_id,
    )
    base_asset = (
        await require_asset_code(session, body.base_asset_code)
        if body.base_asset_code is not None
        else await session.get(Asset, workspace.base_asset_id)
    )
    assert base_asset is not None
    data = await build_period_proposal(
        session,
        workspace,
        transaction,
        opening_occurrence_id=occurrence.id if occurrence else None,
        start_date=body.start_date,
        end_date=body.end_date,
        base_asset=base_asset,
        funding_amount=body.funding_amount,
        commitment_overrides=body.commitment_base_amounts,
    )
    return PeriodProposalOut.model_validate(data)


async def commitment_out(
    session: AsyncSession, commitment: BudgetCommitment
) -> BudgetCommitmentOut:
    occurrence = await session.get(PlanOccurrence, commitment.plan_occurrence_id)
    assert occurrence is not None
    transaction = (
        await session.get(Transaction, occurrence.transaction_id)
        if occurrence.transaction_id is not None
        else None
    )
    actual = (
        transaction.base_amount
        if transaction is not None and transaction.status == "posted"
        else None
    )
    effective = (
        ZERO
        if commitment.status == "cancelled"
        else actual
        if commitment.status == "fulfilled" and actual is not None
        else commitment.planned_amount
    )
    return BudgetCommitmentOut(
        id=commitment.id,
        budget_period_id=commitment.budget_period_id,
        plan_occurrence_id=commitment.plan_occurrence_id,
        type=commitment.type,
        name=commitment.name,
        due_date=occurrence.due_date,
        planned_amount=commitment.planned_amount,
        actual_amount=actual,
        effective_amount=effective,
        status=commitment.status,
        transaction_id=occurrence.transaction_id,
        created_at=commitment.created_at,
        updated_at=commitment.updated_at,
    )


async def period_out(
    session: AsyncSession,
    workspace: Workspace,
    period: BudgetPeriod,
) -> BudgetPeriodOut:
    base_asset = await session.get(Asset, period.base_asset_id)
    assert base_asset is not None
    commitments = list(
        (
            await session.execute(
                select(BudgetCommitment)
                .join(
                    PlanOccurrence,
                    PlanOccurrence.id == BudgetCommitment.plan_occurrence_id,
                )
                .where(BudgetCommitment.budget_period_id == period.id)
                .order_by(PlanOccurrence.due_date, BudgetCommitment.id)
            )
        ).scalars()
    )
    rendered = [await commitment_out(session, item) for item in commitments]
    commitments_total = sum((item.effective_amount for item in rendered), ZERO)
    return BudgetPeriodOut(
        id=period.id,
        workspace_id=period.workspace_id,
        created_by_user_id=period.created_by_user_id,
        start_date=period.start_date,
        end_date=period.end_date,
        status=budget_period_status(period, workspace_today(workspace)),
        base_asset=AssetOut.model_validate(base_asset),
        funding_amount=period.funding_amount,
        opening_transaction_id=period.opening_transaction_id,
        opening_plan_occurrence_id=period.opening_plan_occurrence_id,
        prompt_ack_date=period.prompt_ack_date,
        commitments_total=commitments_total,
        daily_pool=period.funding_amount - commitments_total,
        commitments=rendered,
        created_at=period.created_at,
        closed_at=period.closed_at,
    )


async def tracker_summary(
    session: AsyncSession,
    workspace: Workspace,
    period: BudgetPeriod,
) -> TrackerSummaryOut:
    rendered_period = await period_out(session, workspace, period)
    fulfilled_ids = {
        item.transaction_id
        for item in rendered_period.commitments
        if item.status == "fulfilled" and item.transaction_id is not None
    }
    transactions = list(
        (
            await session.execute(
                select(Transaction).where(
                    Transaction.budget_period_id == period.id,
                    Transaction.status.in_(("posted", "unassigned")),
                    Transaction.type.in_(("expense", "income")),
                )
            )
        ).scalars()
    )
    dated_amounts: list[tuple[date, Decimal]] = []
    for transaction in transactions:
        if (
            transaction.id == period.opening_transaction_id
            or transaction.id in fulfilled_ids
        ):
            continue
        if transaction.base_amount is None:
            raise HTTPException(
                status_code=409,
                detail=f"Transaction {transaction.id} has no frozen base amount",
            )
        signed = (
            transaction.base_amount
            if transaction.type == "expense"
            else -transaction.base_amount
        )
        dated_amounts.append((transaction.local_date, signed))
    rebase_days = list(
        (
            await session.execute(
                select(RebaseEvent.day).where(
                    RebaseEvent.budget_period_id == period.id
                )
            )
        ).scalars()
    )
    today = workspace_today(workspace)
    result = compute_budget(
        rendered_period.daily_pool,
        period.start_date,
        period.end_date,
        dated_amounts,
        today=today,
        rebase_days=rebase_days,
        quantum=asset_quantum(await session.get(Asset, period.base_asset_id)),
    )
    return TrackerSummaryOut(
        period=rendered_period,
        days_total=result.days_total,
        days_remaining=result.days_remaining,
        spent_total=result.spent_total,
        remaining_money=result.remaining_money,
        daily_base=result.daily_base,
        budget_today=result.budget_today,
        spent_today=result.spent_today,
        available_today=result.per_day_today,
        next_daily=result.next_daily,
    )


async def current_period(
    session: AsyncSession, workspace: Workspace
) -> BudgetPeriod:
    today = workspace_today(workspace)
    period = (
        await session.execute(
            select(BudgetPeriod).where(
                BudgetPeriod.workspace_id == workspace.id,
                BudgetPeriod.start_date <= today,
                BudgetPeriod.end_date >= today,
                BudgetPeriod.closed_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if period is None:
        raise HTTPException(status_code=404, detail="No current budget period")
    return period


def require_ended_confirmation(
    workspace: Workspace,
    period: BudgetPeriod,
    confirmed: bool,
) -> None:
    if budget_period_status(period, workspace_today(workspace)) == "ended" and not confirmed:
        raise HTTPException(
            status_code=409,
            detail="Ended period correction requires explicit confirmation",
        )


async def ensure_no_overlap(
    session: AsyncSession,
    workspace_id: int,
    start_date: date,
    end_date: date,
    *,
    exclude_id: int | None = None,
) -> None:
    statement = select(BudgetPeriod.id).where(
        BudgetPeriod.workspace_id == workspace_id,
        BudgetPeriod.start_date <= end_date,
        BudgetPeriod.end_date >= start_date,
    )
    if exclude_id is not None:
        statement = statement.where(BudgetPeriod.id != exclude_id)
    if (await session.execute(statement.limit(1))).scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Budget periods cannot overlap")


async def ensure_period_range_contains_history(
    session: AsyncSession,
    period: BudgetPeriod,
    start_date: date,
    end_date: date,
) -> None:
    transaction_id = (
        await session.execute(
            select(Transaction.id)
            .where(
                Transaction.budget_period_id == period.id,
                or_(
                    Transaction.local_date < start_date,
                    Transaction.local_date > end_date,
                ),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if transaction_id is not None:
        raise HTTPException(
            status_code=409,
            detail="Budget period dates cannot exclude attached transactions",
        )

    commitment_id = (
        await session.execute(
            select(BudgetCommitment.id)
            .join(
                PlanOccurrence,
                PlanOccurrence.id == BudgetCommitment.plan_occurrence_id,
            )
            .where(
                BudgetCommitment.budget_period_id == period.id,
                or_(
                    PlanOccurrence.due_date < start_date,
                    PlanOccurrence.due_date > end_date,
                ),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if commitment_id is not None:
        raise HTTPException(
            status_code=409,
            detail="Budget period dates cannot exclude commitment occurrences",
        )

    rebase_id = (
        await session.execute(
            select(RebaseEvent.id)
            .where(
                RebaseEvent.budget_period_id == period.id,
                or_(RebaseEvent.day < start_date, RebaseEvent.day > end_date),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if rebase_id is not None or (
        period.prompt_ack_date is not None
        and not (start_date <= period.prompt_ack_date <= end_date)
    ):
        raise HTTPException(
            status_code=409,
            detail="Budget period dates cannot exclude persisted Tracker decisions",
        )


@router.post(
    "/workspaces/{workspace_id}/budget-periods/preview",
    response_model=PeriodProposalOut,
)
async def preview_budget_period(
    workspace_id: int,
    body: BudgetPeriodPreviewIn,
    workspace: Workspace = Depends(require_workspace_owner),
    session: AsyncSession = Depends(get_session),
):
    return await proposed_period(session, workspace, body)


@router.post(
    "/workspaces/{workspace_id}/budget-periods",
    response_model=TrackerSummaryOut,
    status_code=201,
)
async def create_budget_period(
    workspace_id: int,
    body: BudgetPeriodCreate,
    workspace: Workspace = Depends(require_workspace_owner),
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    proposal = await proposed_period(session, workspace, body)
    if proposal.end_date is None:
        raise HTTPException(
            status_code=422,
            detail="end_date is required when there is no next planned income",
        )
    if proposal.funding_amount is None:
        raise HTTPException(
            status_code=422,
            detail="funding_amount in the period base asset is required",
        )
    missing = [
        item.plan_occurrence_id
        for item in proposal.commitments
        if item.needs_base_amount
    ]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Base amounts are required for commitments: {missing}",
        )
    await ensure_no_overlap(
        session, workspace_id, proposal.start_date, proposal.end_date
    )
    transaction, occurrence = await resolve_opening(
        session,
        workspace_id,
        proposal.opening_transaction_id,
        proposal.opening_plan_occurrence_id,
    )
    period = BudgetPeriod(
        workspace_id=workspace_id,
        created_by_user_id=user.id,
        start_date=proposal.start_date,
        end_date=proposal.end_date,
        base_asset_id=proposal.base_asset.id,
        funding_amount=proposal.funding_amount,
        opening_transaction_id=transaction.id if transaction else None,
        opening_plan_occurrence_id=occurrence.id if occurrence else None,
    )
    session.add(period)
    await session.flush()

    if transaction is not None:
        amount, source_asset = await transaction_value_source(session, transaction)
        base_asset = await session.get(Asset, period.base_asset_id)
        assert base_asset is not None
        if source_asset.id == base_asset.id and proposal.funding_amount != amount:
            raise HTTPException(
                status_code=422,
                detail="funding_amount must match the opening income in the base asset",
            )
        transaction.budget_period_id = period.id
        transaction.base_amount = proposal.funding_amount
        transaction.base_rate = quantize_exchange_rate(
            proposal.funding_amount / amount
        )
        transaction.rate_source = (
            "opening" if source_asset.id == base_asset.id else "manual-opening"
        )

    for item in proposal.commitments:
        commitment = BudgetCommitment(
            budget_period_id=period.id,
            plan_occurrence_id=item.plan_occurrence_id,
            type=item.type,
            name=item.name,
            planned_amount=item.planned_amount,
            status="reserved",
        )
        session.add(commitment)
    await session.flush()

    commitment_transactions: set[int] = set()
    for commitment in list(
        (
            await session.execute(
                select(BudgetCommitment).where(
                    BudgetCommitment.budget_period_id == period.id
                )
            )
        ).scalars()
    ):
        item = await session.get(PlanOccurrence, commitment.plan_occurrence_id)
        assert item is not None
        if item.status == "completed" and item.transaction_id is not None:
            linked = await session.get(Transaction, item.transaction_id)
            if linked is not None and linked.status == "posted":
                await sync_plan_fulfillment(
                    session,
                    item,
                    linked,
                    body.transaction_base_amounts.get(linked.id),
                    confirm_ended_period=True,
                )
                commitment_transactions.add(linked.id)

    existing = list(
        (
            await session.execute(
                select(Transaction).where(
                    Transaction.workspace_id == workspace_id,
                    Transaction.local_date >= period.start_date,
                    Transaction.local_date <= period.end_date,
                    Transaction.status.in_(("posted", "unassigned")),
                    Transaction.type.in_(("expense", "income")),
                )
            )
        ).scalars()
    )
    for item in existing:
        if item.id == period.opening_transaction_id or item.id in commitment_transactions:
            continue
        try:
            await attach_transaction_to_tracker(
                session,
                item,
                body.transaction_base_amounts.get(item.id),
                explicit_period=period,
                confirm_ended_period=True,
            )
        except HTTPException as exc:
            if exc.status_code == 422:
                raise HTTPException(
                    status_code=422,
                    detail=f"Transaction {item.id}: {exc.detail}",
                )
            raise
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Opening income already has a period")
    await session.refresh(period)
    return await tracker_summary(session, workspace, period)


@router.get(
    "/workspaces/{workspace_id}/budget-periods",
    response_model=list[BudgetPeriodOut],
)
async def list_budget_periods(
    workspace_id: int,
    workspace: Workspace = Depends(require_workspace_owner),
    session: AsyncSession = Depends(get_session),
):
    periods = list(
        (
            await session.execute(
                select(BudgetPeriod)
                .where(BudgetPeriod.workspace_id == workspace_id)
                .order_by(BudgetPeriod.start_date.desc(), BudgetPeriod.id.desc())
            )
        ).scalars()
    )
    return [await period_out(session, workspace, item) for item in periods]


@router.get(
    "/workspaces/{workspace_id}/budget-periods/current",
    response_model=TrackerSummaryOut,
)
async def get_current_budget_period(
    workspace_id: int,
    workspace: Workspace = Depends(require_workspace_owner),
    session: AsyncSession = Depends(get_session),
):
    return await tracker_summary(
        session, workspace, await current_period(session, workspace)
    )


@router.get(
    "/workspaces/{workspace_id}/budget-periods/{period_id}",
    response_model=TrackerSummaryOut,
)
async def get_budget_period(
    workspace_id: int,
    period_id: int,
    workspace: Workspace = Depends(require_workspace_owner),
    session: AsyncSession = Depends(get_session),
):
    return await tracker_summary(
        session, workspace, await require_period(session, workspace_id, period_id)
    )


@router.patch(
    "/workspaces/{workspace_id}/budget-periods/{period_id}",
    response_model=TrackerSummaryOut,
)
async def patch_budget_period(
    workspace_id: int,
    period_id: int,
    body: BudgetPeriodPatch,
    workspace: Workspace = Depends(require_workspace_owner),
    session: AsyncSession = Depends(get_session),
):
    period = await require_period(session, workspace_id, period_id)
    start = body.start_date or period.start_date
    end = body.end_date or period.end_date
    if end < start:
        raise HTTPException(status_code=422, detail="end_date must not precede start_date")
    has_change = (
        start != period.start_date
        or end != period.end_date
        or (
            body.funding_amount is not None
            and body.funding_amount != period.funding_amount
        )
    )
    if not has_change:
        return await tracker_summary(session, workspace, period)
    require_ended_confirmation(workspace, period, body.confirm_ended_period)
    if period.closed_at is not None:
        raise HTTPException(status_code=409, detail="Closed period cannot be edited")
    await ensure_no_overlap(session, workspace_id, start, end, exclude_id=period.id)
    await ensure_period_range_contains_history(session, period, start, end)
    period.start_date, period.end_date = start, end
    if body.funding_amount is not None:
        base_asset = await session.get(Asset, period.base_asset_id)
        assert base_asset is not None
        period.funding_amount = validate_amount(body.funding_amount, base_asset)
    await session.commit()
    await session.refresh(period)
    return await tracker_summary(session, workspace, period)


@router.post(
    "/workspaces/{workspace_id}/budget-periods/{period_id}/close",
    response_model=TrackerSummaryOut,
)
async def close_budget_period(
    workspace_id: int,
    period_id: int,
    workspace: Workspace = Depends(require_workspace_owner),
    session: AsyncSession = Depends(get_session),
):
    period = await require_period(session, workspace_id, period_id)
    if period.closed_at is not None:
        raise HTTPException(status_code=409, detail="Budget period is already closed")
    period.closed_at = utcnow()
    await session.commit()
    await session.refresh(period)
    return await tracker_summary(session, workspace, period)


@router.post(
    "/workspaces/{workspace_id}/budget-periods/{period_id}/commitments",
    response_model=TrackerSummaryOut,
    status_code=201,
)
async def create_budget_commitment(
    workspace_id: int,
    period_id: int,
    body: BudgetCommitmentCreate,
    workspace: Workspace = Depends(require_workspace_owner),
    session: AsyncSession = Depends(get_session),
):
    period = await require_period(session, workspace_id, period_id)
    if period.closed_at is not None:
        raise HTTPException(
            status_code=409,
            detail="Closed period does not accept new commitments",
        )
    require_ended_confirmation(workspace, period, body.confirm_ended_period)
    occurrence = await session.get(PlanOccurrence, body.plan_occurrence_id)
    rule = await session.get(PlanRule, occurrence.plan_rule_id) if occurrence else None
    if (
        occurrence is None
        or rule is None
        or rule.workspace_id != workspace_id
        or occurrence.due_date < period.start_date
        or occurrence.due_date > period.end_date
        or rule.kind == "income"
        or not (
            rule.kind in {"required_expense", "reserve_transfer"}
            or rule.is_required
        )
    ):
        raise HTTPException(status_code=422, detail="Invalid commitment occurrence")
    source_asset = await session.get(Asset, rule.asset_id)
    base_asset = await session.get(Asset, period.base_asset_id)
    assert source_asset is not None and base_asset is not None
    planned, _, _ = await value_amount(
        session,
        workspace_id,
        occurrence.planned_amount,
        source_asset,
        base_asset,
        body.planned_amount,
    )
    commitment = BudgetCommitment(
        budget_period_id=period.id,
        plan_occurrence_id=occurrence.id,
        type=(
            "reserve_transfer"
            if rule.kind == "reserve_transfer"
            else "required_expense"
        ),
        name=rule.name,
        planned_amount=planned,
        status="reserved",
    )
    session.add(commitment)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Commitment already exists")
    if occurrence.status == "completed" and occurrence.transaction_id is not None:
        transaction = await session.get(Transaction, occurrence.transaction_id)
        if transaction is not None and transaction.status == "posted":
            await sync_plan_fulfillment(
                session,
                occurrence,
                transaction,
                body.planned_amount,
                confirm_ended_period=body.confirm_ended_period,
            )
    await session.commit()
    return await tracker_summary(session, workspace, period)


@router.patch(
    "/workspaces/{workspace_id}/budget-commitments/{commitment_id}",
    response_model=TrackerSummaryOut,
)
async def patch_budget_commitment(
    workspace_id: int,
    commitment_id: int,
    body: BudgetCommitmentPatch,
    workspace: Workspace = Depends(require_workspace_owner),
    session: AsyncSession = Depends(get_session),
):
    commitment = await session.get(BudgetCommitment, commitment_id)
    period = (
        await session.get(BudgetPeriod, commitment.budget_period_id)
        if commitment
        else None
    )
    if commitment is None or period is None or period.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Budget commitment not found")
    name = (
        " ".join(body.name.strip().split())
        if body.name is not None
        else commitment.name
    )
    if not name:
        raise HTTPException(status_code=422, detail="Commitment name is required")
    planned_amount = commitment.planned_amount
    if body.planned_amount is not None:
        base_asset = await session.get(Asset, period.base_asset_id)
        assert base_asset is not None
        planned_amount = validate_amount(body.planned_amount, base_asset)
    status = body.status or commitment.status
    if (
        name == commitment.name
        and planned_amount == commitment.planned_amount
        and status == commitment.status
    ):
        return await tracker_summary(session, workspace, period)
    if commitment.status == "fulfilled" and body.status is not None:
        raise HTTPException(status_code=409, detail="Fulfilled commitment status is automatic")
    require_ended_confirmation(workspace, period, body.confirm_ended_period)
    commitment.name = name
    commitment.planned_amount = planned_amount
    commitment.status = status
    await session.commit()
    return await tracker_summary(session, workspace, period)


@router.delete(
    "/workspaces/{workspace_id}/budget-commitments/{commitment_id}",
    response_model=TrackerSummaryOut,
)
async def cancel_budget_commitment(
    workspace_id: int,
    commitment_id: int,
    body: BudgetCommitmentCancelIn | None = None,
    workspace: Workspace = Depends(require_workspace_owner),
    session: AsyncSession = Depends(get_session),
):
    commitment = await session.get(BudgetCommitment, commitment_id)
    period = (
        await session.get(BudgetPeriod, commitment.budget_period_id)
        if commitment
        else None
    )
    if commitment is None or period is None or period.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Budget commitment not found")
    if commitment.status == "fulfilled":
        raise HTTPException(status_code=409, detail="Fulfilled commitment cannot be cancelled")
    if commitment.status == "cancelled":
        return await tracker_summary(session, workspace, period)
    require_ended_confirmation(
        workspace,
        period,
        body.confirm_ended_period if body is not None else False,
    )
    commitment.status = "cancelled"
    await session.commit()
    return await tracker_summary(session, workspace, period)


@router.get(
    "/workspaces/{workspace_id}/tracker/today",
    response_model=TrackerSummaryOut,
)
async def tracker_today(
    workspace_id: int,
    workspace: Workspace = Depends(require_workspace_owner),
    session: AsyncSession = Depends(get_session),
):
    return await tracker_summary(
        session, workspace, await current_period(session, workspace)
    )


@router.get(
    "/workspaces/{workspace_id}/tracker/preview",
    response_model=TrackerPreviewOut,
)
async def tracker_preview(
    workspace_id: int,
    pending: Decimal = Query(ge=0),
    workspace: Workspace = Depends(require_workspace_owner),
    session: AsyncSession = Depends(get_session),
):
    period = await current_period(session, workspace)
    summary = await tracker_summary(session, workspace, period)
    base_asset = await session.get(Asset, period.base_asset_id)
    assert base_asset is not None
    pending = validate_amount(pending, base_asset, allow_zero=True)
    return TrackerPreviewOut(
        **summary.model_dump(),
        pending_amount=pending,
        available_after=preview_after(
            summary.available_today, pending, asset_quantum(base_asset)
        ),
    )


@router.get(
    "/workspaces/{workspace_id}/tracker/savings-prompt",
    response_model=SavingsPromptOut,
)
async def savings_prompt(
    workspace_id: int,
    workspace: Workspace = Depends(require_workspace_owner),
    session: AsyncSession = Depends(get_session),
):
    period = await current_period(session, workspace)
    summary = await tracker_summary(session, workspace, period)
    today = workspace_today(workspace)
    carry = max(summary.budget_today - summary.daily_base, ZERO)
    acknowledged = period.prompt_ack_date == today
    return SavingsPromptOut(
        required=today > period.start_date and carry > 0 and not acknowledged,
        day=today,
        carry_amount=carry,
        acknowledged=acknowledged,
    )


@router.post(
    "/workspaces/{workspace_id}/tracker/savings-decision",
    response_model=TrackerSummaryOut,
)
async def savings_decision(
    workspace_id: int,
    body: SavingsDecisionIn,
    workspace: Workspace = Depends(require_workspace_owner),
    session: AsyncSession = Depends(get_session),
):
    period = await current_period(session, workspace)
    today = workspace_today(workspace)
    if today <= period.start_date:
        raise HTTPException(status_code=409, detail="Savings decision starts on the next day")
    if body.choice == "redistribute":
        exists = (
            await session.execute(
                select(RebaseEvent.id).where(
                    RebaseEvent.budget_period_id == period.id,
                    RebaseEvent.day == today,
                )
            )
        ).scalar_one_or_none()
        if exists is None:
            session.add(
                RebaseEvent(
                    budget_period_id=period.id,
                    day=today,
                    reason="savings_redistribute",
                )
            )
    period.prompt_ack_date = today
    await session.commit()
    return await tracker_summary(session, workspace, period)
