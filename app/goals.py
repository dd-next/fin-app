"""Cross-period savings goals and per-period planned contributions."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.access import require_workspace_access
from app.categories import top_level_allocated
from app.db import get_session
from app.models import (
    Operation,
    Period,
    PeriodGoalPlan,
    SavingsGoal,
    WorkspaceMember,
    utcnow,
)
from app.schemas import (
    GoalPlanIn,
    GoalPlanOut,
    LimitWarning,
    SavingsGoalCreate,
    SavingsGoalOut,
    SavingsGoalPatch,
)


router = APIRouter(tags=["savings-goals"])
ZERO = Decimal("0")


def normalize_goal_name(name: str) -> str:
    return " ".join(name.strip().split()).casefold()


async def require_goal(
    session: AsyncSession,
    goal_id: int,
    workspace_id: int,
    *,
    allow_archived: bool = False,
) -> SavingsGoal:
    goal = await session.get(SavingsGoal, goal_id)
    if (
        goal is None
        or goal.workspace_id != workspace_id
        or (goal.archived_at is not None and not allow_archived)
    ):
        raise HTTPException(status_code=422, detail="Invalid savings goal")
    return goal


async def goal_balance(session: AsyncSession, goal_id: int) -> Decimal:
    rows = (
        await session.execute(
            select(Operation.kind, Operation.amount).where(
                Operation.savings_goal_id == goal_id,
                Operation.kind.in_({"transfer_to_goal", "transfer_from_goal"}),
            )
        )
    ).all()
    return sum(
        (amount if kind == "transfer_to_goal" else -amount for kind, amount in rows),
        ZERO,
    )


async def period_goal_contributed(
    session: AsyncSession, period_id: int, goal_id: int
) -> Decimal:
    rows = (
        await session.execute(
            select(Operation.kind, Operation.amount).where(
                Operation.period_id == period_id,
                Operation.savings_goal_id == goal_id,
                Operation.kind.in_({"transfer_to_goal", "transfer_from_goal"}),
            )
        )
    ).all()
    return sum(
        (amount if kind == "transfer_to_goal" else -amount for kind, amount in rows),
        ZERO,
    )


async def goal_out(session: AsyncSession, goal: SavingsGoal) -> SavingsGoalOut:
    balance = await goal_balance(session, goal.id)
    return SavingsGoalOut(
        id=goal.id,
        workspace_id=goal.workspace_id,
        name=goal.name,
        target_amount=goal.target_amount,
        target_date=goal.target_date,
        balance=balance,
        remaining=max(goal.target_amount - balance, ZERO),
        completed=balance >= goal.target_amount,
        archived_at=goal.archived_at,
    )


async def goal_plan_warning(
    session: AsyncSession, period_id: int, goal: SavingsGoal
) -> list[LimitWarning]:
    plan = (
        await session.execute(
            select(PeriodGoalPlan).where(
                PeriodGoalPlan.period_id == period_id,
                PeriodGoalPlan.goal_id == goal.id,
            )
        )
    ).scalar_one_or_none()
    if plan is None:
        return []
    contributed = await period_goal_contributed(session, period_id, goal.id)
    if contributed <= plan.planned_amount:
        return []
    return [
        LimitWarning(
            scope="goal",
            target_id=goal.id,
            name=goal.name,
            limit_amount=plan.planned_amount,
            spent=contributed,
            over_by=contributed - plan.planned_amount,
        )
    ]


@router.get("/savings-goals", response_model=list[SavingsGoalOut])
async def list_goals(
    workspace_id: int = 1,
    include_archived: bool = False,
    member: WorkspaceMember | None = Depends(require_workspace_access),
    session: AsyncSession = Depends(get_session),
):
    statement = select(SavingsGoal).where(SavingsGoal.workspace_id == workspace_id)
    if not include_archived:
        statement = statement.where(SavingsGoal.archived_at.is_(None))
    goals = list((await session.execute(statement.order_by(SavingsGoal.name))).scalars())
    return [await goal_out(session, goal) for goal in goals]


@router.post("/savings-goals", response_model=SavingsGoalOut)
async def create_goal(
    body: SavingsGoalCreate,
    workspace_id: int = 1,
    member: WorkspaceMember | None = Depends(require_workspace_access),
    session: AsyncSession = Depends(get_session),
):
    name = " ".join(body.name.strip().split())
    goal = SavingsGoal(
        workspace_id=workspace_id,
        name=name,
        normalized_name=normalize_goal_name(name),
        target_amount=body.target_amount,
        target_date=body.target_date,
        created_by_user_id=member.user_id if member else None,
    )
    session.add(goal)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Savings goal name already exists")
    await session.refresh(goal)
    return await goal_out(session, goal)


@router.patch("/savings-goals/{goal_id}", response_model=SavingsGoalOut)
async def patch_goal(
    goal_id: int,
    body: SavingsGoalPatch,
    workspace_id: int = 1,
    member: WorkspaceMember | None = Depends(require_workspace_access),
    session: AsyncSession = Depends(get_session),
):
    goal = await require_goal(session, goal_id, workspace_id, allow_archived=True)
    if body.name is not None:
        goal.name = " ".join(body.name.strip().split())
        goal.normalized_name = normalize_goal_name(goal.name)
    if body.target_amount is not None:
        goal.target_amount = body.target_amount
    if "target_date" in body.model_fields_set:
        goal.target_date = body.target_date
    if body.archived is True:
        goal.archived_at = utcnow()
    elif body.archived is False:
        goal.archived_at = None
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Savings goal name already exists")
    await session.refresh(goal)
    return await goal_out(session, goal)


async def _goal_plan_out(
    session: AsyncSession, plan: PeriodGoalPlan, goal: SavingsGoal
) -> GoalPlanOut:
    contributed = await period_goal_contributed(session, plan.period_id, goal.id)
    return GoalPlanOut(
        id=plan.id,
        goal=await goal_out(session, goal),
        planned_amount=plan.planned_amount,
        contributed=contributed,
        remaining=plan.planned_amount - contributed,
        over_plan=contributed > plan.planned_amount,
    )


@router.get("/periods/{period_id}/goal-plans", response_model=list[GoalPlanOut])
async def list_goal_plans(
    period_id: int,
    workspace_id: int = 1,
    member: WorkspaceMember | None = Depends(require_workspace_access),
    session: AsyncSession = Depends(get_session),
):
    period = await session.get(Period, period_id)
    if period is None or period.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Period not found")
    rows = (
        await session.execute(
            select(PeriodGoalPlan, SavingsGoal)
            .join(SavingsGoal, SavingsGoal.id == PeriodGoalPlan.goal_id)
            .where(PeriodGoalPlan.period_id == period_id)
            .order_by(SavingsGoal.name)
        )
    ).all()
    return [await _goal_plan_out(session, plan, goal) for plan, goal in rows]


@router.put(
    "/periods/{period_id}/goal-plans/{goal_id}", response_model=GoalPlanOut
)
async def put_goal_plan(
    period_id: int,
    goal_id: int,
    body: GoalPlanIn,
    workspace_id: int = 1,
    member: WorkspaceMember | None = Depends(require_workspace_access),
    session: AsyncSession = Depends(get_session),
):
    period = await session.get(Period, period_id)
    if period is None or period.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Period not found")
    goal = await require_goal(session, goal_id, workspace_id)
    plan = (
        await session.execute(
            select(PeriodGoalPlan).where(
                PeriodGoalPlan.period_id == period_id,
                PeriodGoalPlan.goal_id == goal_id,
            )
        )
    ).scalar_one_or_none()
    allocated_elsewhere = await top_level_allocated(
        session,
        period_id,
        exclude_goal_plan_id=plan.id if plan else None,
    )
    if allocated_elsewhere + body.planned_amount > period.total_amount:
        raise HTTPException(
            status_code=409,
            detail="Planned savings exceed the period total amount",
        )
    if plan is None:
        plan = PeriodGoalPlan(
            period_id=period_id,
            goal_id=goal_id,
            planned_amount=body.planned_amount,
        )
        session.add(plan)
    else:
        plan.planned_amount = body.planned_amount
    await session.commit()
    await session.refresh(plan)
    return await _goal_plan_out(session, plan, goal)
