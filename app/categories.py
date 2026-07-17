"""Workspace categories, period plans, and non-blocking limit warnings."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.access import require_workspace_access
from app.db import get_session
from app.models import (
    Category,
    Operation,
    Period,
    PeriodCategoryPlan,
    PeriodGoalPlan,
    PeriodPoolPlan,
    Pool,
    WorkspaceMember,
    utcnow,
)
from app.schemas import (
    CategoryCreate,
    CategoryOut,
    CategoryPatch,
    CategoryPlanIn,
    CategoryPlanOut,
    LimitWarning,
)


router = APIRouter(tags=["categories"])
ZERO = Decimal("0")


def normalize_category_name(name: str) -> str:
    return " ".join(name.strip().split()).casefold()


async def require_category(
    session: AsyncSession,
    category_id: int,
    workspace_id: int,
    *,
    allow_archived: bool = False,
) -> Category:
    category = await session.get(Category, category_id)
    if (
        category is None
        or category.workspace_id != workspace_id
        or (category.archived_at is not None and not allow_archived)
    ):
        raise HTTPException(status_code=422, detail="Invalid category")
    return category


async def category_spent(
    session: AsyncSession, period_id: int, category_id: int
) -> Decimal:
    values = (
        await session.execute(
            select(Operation.amount).where(
                Operation.period_id == period_id,
                Operation.category_id == category_id,
                Operation.kind == "expense",
            )
        )
    ).scalars()
    return sum(values, ZERO)


async def pool_spent(
    session: AsyncSession, period_id: int, pool_plan_id: int
) -> Decimal:
    category_ids = list(
        (
            await session.execute(
                select(PeriodCategoryPlan.category_id).where(
                    PeriodCategoryPlan.period_id == period_id,
                    PeriodCategoryPlan.pool_plan_id == pool_plan_id,
                )
            )
        ).scalars()
    )
    if not category_ids:
        return ZERO
    values = (
        await session.execute(
            select(Operation.amount).where(
                Operation.period_id == period_id,
                Operation.kind == "expense",
                Operation.category_id.in_(category_ids),
            )
        )
    ).scalars()
    return sum(values, ZERO)


async def operation_limit_warnings(
    session: AsyncSession, period_id: int, category: Category
) -> list[LimitWarning]:
    plan = (
        await session.execute(
            select(PeriodCategoryPlan).where(
                PeriodCategoryPlan.period_id == period_id,
                PeriodCategoryPlan.category_id == category.id,
            )
        )
    ).scalar_one_or_none()
    if plan is None:
        return []
    warnings: list[LimitWarning] = []
    spent = await category_spent(session, period_id, category.id)
    if plan.limit_amount is not None and spent > plan.limit_amount:
        warnings.append(
            LimitWarning(
                scope="category",
                target_id=category.id,
                name=category.name,
                limit_amount=plan.limit_amount,
                spent=spent,
                over_by=spent - plan.limit_amount,
            )
        )
    if plan.pool_plan_id is not None:
        pool_plan = await session.get(PeriodPoolPlan, plan.pool_plan_id)
        if pool_plan is not None:
            pool_value = await pool_spent(session, period_id, pool_plan.id)
            if pool_value > pool_plan.allocated_amount:
                pool = await session.get(Pool, pool_plan.pool_id)
                warnings.append(
                    LimitWarning(
                        scope="pool",
                        target_id=pool_plan.id,
                        name=pool.name if pool else "Pool",
                        limit_amount=pool_plan.allocated_amount,
                        spent=pool_value,
                        over_by=pool_value - pool_plan.allocated_amount,
                    )
                )
    return warnings


async def configured_category_limits(
    session: AsyncSession, period_id: int, *, exclude_category_id: int | None = None
) -> Decimal:
    statement = select(PeriodCategoryPlan.limit_amount).where(
        PeriodCategoryPlan.period_id == period_id,
        PeriodCategoryPlan.limit_amount.is_not(None),
    )
    if exclude_category_id is not None:
        statement = statement.where(
            PeriodCategoryPlan.category_id != exclude_category_id
        )
    values = (await session.execute(statement)).scalars()
    return sum((value for value in values if value is not None), ZERO)


async def pool_child_limits(
    session: AsyncSession,
    pool_plan_id: int,
    *,
    exclude_category_id: int | None = None,
) -> Decimal:
    statement = select(PeriodCategoryPlan.limit_amount).where(
        PeriodCategoryPlan.pool_plan_id == pool_plan_id,
        PeriodCategoryPlan.limit_amount.is_not(None),
    )
    if exclude_category_id is not None:
        statement = statement.where(
            PeriodCategoryPlan.category_id != exclude_category_id
        )
    values = (await session.execute(statement)).scalars()
    return sum((value for value in values if value is not None), ZERO)


async def top_level_allocated(
    session: AsyncSession,
    period_id: int,
    *,
    exclude_category_id: int | None = None,
    exclude_pool_plan_id: int | None = None,
    exclude_goal_plan_id: int | None = None,
) -> Decimal:
    pool_statement = select(PeriodPoolPlan.allocated_amount).where(
        PeriodPoolPlan.period_id == period_id
    )
    if exclude_pool_plan_id is not None:
        pool_statement = pool_statement.where(
            PeriodPoolPlan.id != exclude_pool_plan_id
        )
    pool_values = (await session.execute(pool_statement)).scalars()

    category_statement = select(PeriodCategoryPlan.limit_amount).where(
        PeriodCategoryPlan.period_id == period_id,
        PeriodCategoryPlan.pool_plan_id.is_(None),
        PeriodCategoryPlan.limit_amount.is_not(None),
    )
    if exclude_category_id is not None:
        category_statement = category_statement.where(
            PeriodCategoryPlan.category_id != exclude_category_id
        )
    category_values = (await session.execute(category_statement)).scalars()
    goal_statement = select(PeriodGoalPlan.planned_amount).where(
        PeriodGoalPlan.period_id == period_id
    )
    if exclude_goal_plan_id is not None:
        goal_statement = goal_statement.where(
            PeriodGoalPlan.id != exclude_goal_plan_id
        )
    goal_values = (await session.execute(goal_statement)).scalars()
    return sum(pool_values, ZERO) + sum(
        (value for value in category_values if value is not None), ZERO
    ) + sum(goal_values, ZERO)


@router.get("/categories", response_model=list[CategoryOut])
async def list_categories(
    workspace_id: int = 1,
    include_archived: bool = False,
    member: WorkspaceMember | None = Depends(require_workspace_access),
    session: AsyncSession = Depends(get_session),
):
    statement = select(Category).where(Category.workspace_id == workspace_id)
    if not include_archived:
        statement = statement.where(Category.archived_at.is_(None))
    result = await session.execute(statement.order_by(Category.name, Category.id))
    return [CategoryOut.model_validate(category) for category in result.scalars()]


@router.post("/categories", response_model=CategoryOut)
async def create_category(
    body: CategoryCreate,
    workspace_id: int = 1,
    member: WorkspaceMember | None = Depends(require_workspace_access),
    session: AsyncSession = Depends(get_session),
):
    name = " ".join(body.name.strip().split())
    category = Category(
        workspace_id=workspace_id,
        name=name,
        normalized_name=normalize_category_name(name),
        created_by_user_id=member.user_id if member else None,
    )
    session.add(category)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Category name already exists")
    await session.refresh(category)
    return CategoryOut.model_validate(category)


@router.patch("/categories/{category_id}", response_model=CategoryOut)
async def patch_category(
    category_id: int,
    body: CategoryPatch,
    workspace_id: int = 1,
    member: WorkspaceMember | None = Depends(require_workspace_access),
    session: AsyncSession = Depends(get_session),
):
    category = await require_category(
        session, category_id, workspace_id, allow_archived=True
    )
    if body.name is not None:
        category.name = " ".join(body.name.strip().split())
        category.normalized_name = normalize_category_name(category.name)
    if body.archived is True:
        category.archived_at = utcnow()
    elif body.archived is False:
        category.archived_at = None
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Category name already exists")
    await session.refresh(category)
    return CategoryOut.model_validate(category)


@router.get(
    "/periods/{period_id}/category-plans",
    response_model=list[CategoryPlanOut],
)
async def list_category_plans(
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
            select(PeriodCategoryPlan, Category)
            .join(Category, Category.id == PeriodCategoryPlan.category_id)
            .where(PeriodCategoryPlan.period_id == period_id)
            .order_by(Category.name)
        )
    ).all()
    response = []
    for plan, category in rows:
        spent = await category_spent(session, period_id, category.id)
        remaining = (
            plan.limit_amount - spent if plan.limit_amount is not None else None
        )
        response.append(
            CategoryPlanOut(
                category=CategoryOut.model_validate(category),
                limit_amount=plan.limit_amount,
                spent=spent,
                remaining=remaining,
                over_limit=(
                    plan.limit_amount is not None and spent > plan.limit_amount
                ),
                pool_plan_id=plan.pool_plan_id,
            )
        )
    return response


@router.put(
    "/periods/{period_id}/category-plans/{category_id}",
    response_model=CategoryPlanOut,
)
async def put_category_plan(
    period_id: int,
    category_id: int,
    body: CategoryPlanIn,
    workspace_id: int = 1,
    member: WorkspaceMember | None = Depends(require_workspace_access),
    session: AsyncSession = Depends(get_session),
):
    period = await session.get(Period, period_id)
    if period is None or period.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Period not found")
    category = await require_category(session, category_id, workspace_id)
    pool_plan = None
    if body.pool_plan_id is not None:
        pool_plan = await session.get(PeriodPoolPlan, body.pool_plan_id)
        if pool_plan is None or pool_plan.period_id != period_id:
            raise HTTPException(status_code=422, detail="Invalid pool plan")
        child_limits = await pool_child_limits(
            session, pool_plan.id, exclude_category_id=category_id
        )
        if (
            body.limit_amount is not None
            and child_limits + body.limit_amount > pool_plan.allocated_amount
        ):
            raise HTTPException(
                status_code=409,
                detail="Category limits exceed the pool allocation",
            )
    else:
        allocated_elsewhere = await top_level_allocated(
            session, period_id, exclude_category_id=category_id
        )
        if (
            body.limit_amount is not None
            and allocated_elsewhere + body.limit_amount > period.total_amount
        ):
            raise HTTPException(
                status_code=409,
                detail="Category limits exceed the period total amount",
            )
    plan = (
        await session.execute(
            select(PeriodCategoryPlan).where(
                PeriodCategoryPlan.period_id == period_id,
                PeriodCategoryPlan.category_id == category_id,
            )
        )
    ).scalar_one_or_none()
    if plan is None:
        plan = PeriodCategoryPlan(
            period_id=period_id,
            category_id=category_id,
            limit_amount=body.limit_amount,
            pool_plan_id=body.pool_plan_id,
        )
        session.add(plan)
    else:
        plan.limit_amount = body.limit_amount
        plan.pool_plan_id = body.pool_plan_id
    await session.commit()
    spent = await category_spent(session, period_id, category_id)
    return CategoryPlanOut(
        category=CategoryOut.model_validate(category),
        limit_amount=plan.limit_amount,
        spent=spent,
        remaining=(plan.limit_amount - spent if plan.limit_amount is not None else None),
        over_limit=(plan.limit_amount is not None and spent > plan.limit_amount),
        pool_plan_id=plan.pool_plan_id,
    )
