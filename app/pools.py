"""Budget pools (envelopes), allocations, and period-plan cloning."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.access import require_workspace_access
from app.categories import pool_child_limits, pool_spent, top_level_allocated
from app.db import get_session
from app.models import (
    Period,
    PeriodCategoryPlan,
    PeriodGoalPlan,
    PeriodPoolPlan,
    Pool,
    WorkspaceMember,
    utcnow,
)
from app.schemas import (
    PoolCreate,
    PoolOut,
    PoolPatch,
    PoolPlanIn,
    PoolPlanOut,
)


router = APIRouter(tags=["pools"])


def normalize_pool_name(name: str) -> str:
    return " ".join(name.strip().split()).casefold()


async def require_pool(
    session: AsyncSession,
    pool_id: int,
    workspace_id: int,
    *,
    allow_archived: bool = False,
) -> Pool:
    pool = await session.get(Pool, pool_id)
    if (
        pool is None
        or pool.workspace_id != workspace_id
        or (pool.archived_at is not None and not allow_archived)
    ):
        raise HTTPException(status_code=422, detail="Invalid pool")
    return pool


async def clone_period_plan(
    session: AsyncSession, source_period_id: int, target_period_id: int
) -> None:
    source_pool_plans = list(
        (
            await session.execute(
                select(PeriodPoolPlan).where(
                    PeriodPoolPlan.period_id == source_period_id
                )
            )
        ).scalars()
    )
    pool_plan_map: dict[int, int] = {}
    for source in source_pool_plans:
        clone = PeriodPoolPlan(
            period_id=target_period_id,
            pool_id=source.pool_id,
            allocated_amount=source.allocated_amount,
        )
        session.add(clone)
        await session.flush()
        pool_plan_map[source.id] = clone.id

    source_category_plans = list(
        (
            await session.execute(
                select(PeriodCategoryPlan).where(
                    PeriodCategoryPlan.period_id == source_period_id
                )
            )
        ).scalars()
    )
    for source in source_category_plans:
        session.add(
            PeriodCategoryPlan(
                period_id=target_period_id,
                category_id=source.category_id,
                limit_amount=source.limit_amount,
                pool_plan_id=(
                    pool_plan_map.get(source.pool_plan_id)
                    if source.pool_plan_id is not None
                    else None
                ),
            )
        )

    source_goal_plans = list(
        (
            await session.execute(
                select(PeriodGoalPlan).where(
                    PeriodGoalPlan.period_id == source_period_id
                )
            )
        ).scalars()
    )
    for source in source_goal_plans:
        session.add(
            PeriodGoalPlan(
                period_id=target_period_id,
                goal_id=source.goal_id,
                planned_amount=source.planned_amount,
            )
        )


@router.get("/pools", response_model=list[PoolOut])
async def list_pools(
    workspace_id: int = 1,
    include_archived: bool = False,
    member: WorkspaceMember | None = Depends(require_workspace_access),
    session: AsyncSession = Depends(get_session),
):
    statement = select(Pool).where(Pool.workspace_id == workspace_id)
    if not include_archived:
        statement = statement.where(Pool.archived_at.is_(None))
    result = await session.execute(statement.order_by(Pool.name, Pool.id))
    return [PoolOut.model_validate(pool) for pool in result.scalars()]


@router.post("/pools", response_model=PoolOut)
async def create_pool(
    body: PoolCreate,
    workspace_id: int = 1,
    member: WorkspaceMember | None = Depends(require_workspace_access),
    session: AsyncSession = Depends(get_session),
):
    name = " ".join(body.name.strip().split())
    pool = Pool(
        workspace_id=workspace_id,
        name=name,
        normalized_name=normalize_pool_name(name),
        created_by_user_id=member.user_id if member else None,
    )
    session.add(pool)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Pool name already exists")
    await session.refresh(pool)
    return PoolOut.model_validate(pool)


@router.patch("/pools/{pool_id}", response_model=PoolOut)
async def patch_pool(
    pool_id: int,
    body: PoolPatch,
    workspace_id: int = 1,
    member: WorkspaceMember | None = Depends(require_workspace_access),
    session: AsyncSession = Depends(get_session),
):
    pool = await require_pool(session, pool_id, workspace_id, allow_archived=True)
    if body.name is not None:
        pool.name = " ".join(body.name.strip().split())
        pool.normalized_name = normalize_pool_name(pool.name)
    if body.archived is True:
        pool.archived_at = utcnow()
    elif body.archived is False:
        pool.archived_at = None
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Pool name already exists")
    await session.refresh(pool)
    return PoolOut.model_validate(pool)


async def _pool_plan_out(
    session: AsyncSession, plan: PeriodPoolPlan, pool: Pool
) -> PoolPlanOut:
    spent = await pool_spent(session, plan.period_id, plan.id)
    return PoolPlanOut(
        id=plan.id,
        pool=PoolOut.model_validate(pool),
        allocated_amount=plan.allocated_amount,
        spent=spent,
        remaining=plan.allocated_amount - spent,
        over_limit=spent > plan.allocated_amount,
    )


@router.get("/periods/{period_id}/pool-plans", response_model=list[PoolPlanOut])
async def list_pool_plans(
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
            select(PeriodPoolPlan, Pool)
            .join(Pool, Pool.id == PeriodPoolPlan.pool_id)
            .where(PeriodPoolPlan.period_id == period_id)
            .order_by(Pool.name)
        )
    ).all()
    return [await _pool_plan_out(session, plan, pool) for plan, pool in rows]


@router.put(
    "/periods/{period_id}/pool-plans/{pool_id}", response_model=PoolPlanOut
)
async def put_pool_plan(
    period_id: int,
    pool_id: int,
    body: PoolPlanIn,
    workspace_id: int = 1,
    member: WorkspaceMember | None = Depends(require_workspace_access),
    session: AsyncSession = Depends(get_session),
):
    period = await session.get(Period, period_id)
    if period is None or period.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Period not found")
    pool = await require_pool(session, pool_id, workspace_id)
    plan = (
        await session.execute(
            select(PeriodPoolPlan).where(
                PeriodPoolPlan.period_id == period_id,
                PeriodPoolPlan.pool_id == pool_id,
            )
        )
    ).scalar_one_or_none()
    allocated_elsewhere = await top_level_allocated(
        session,
        period_id,
        exclude_pool_plan_id=plan.id if plan else None,
    )
    if allocated_elsewhere + body.allocated_amount > period.total_amount:
        raise HTTPException(
            status_code=409,
            detail="Pool allocations exceed the period total amount",
        )
    if plan is not None:
        child_limits = await pool_child_limits(session, plan.id)
        if child_limits > body.allocated_amount:
            raise HTTPException(
                status_code=409,
                detail="Pool allocation is below its category limits",
            )
        plan.allocated_amount = body.allocated_amount
    else:
        plan = PeriodPoolPlan(
            period_id=period_id,
            pool_id=pool_id,
            allocated_amount=body.allocated_amount,
        )
        session.add(plan)
    await session.commit()
    await session.refresh(plan)
    return await _pool_plan_out(session, plan, pool)
