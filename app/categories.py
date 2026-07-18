"""Workspace-owned transaction categories."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import exists, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.access import (
    require_workspace_category_reader,
    require_workspace_owner,
    visible_account_ids,
)
from app.auth import require_user
from app.db import get_session
from app.models import (
    Category,
    Transaction,
    TransactionLeg,
    User,
    Workspace,
    utcnow,
)
from app.schemas import CategoryCreate, CategoryOut, CategoryPatch


router = APIRouter(tags=["categories"])


def normalize_name(value: str) -> str:
    return " ".join(value.strip().split()).casefold()


async def _category(
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
        raise HTTPException(status_code=404, detail="Category not found")
    return category


@router.get(
    "/workspaces/{workspace_id}/categories", response_model=list[CategoryOut]
)
async def list_categories(
    workspace_id: int,
    include_archived: bool = False,
    workspace: Workspace = Depends(require_workspace_category_reader),
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    statement = select(Category).where(Category.workspace_id == workspace_id)
    if not include_archived:
        statement = statement.where(Category.archived_at.is_(None))
    elif workspace.owner_user_id != user.id:
        account_ids = await visible_account_ids(session, user.id)
        used_by_visible_transaction = exists(
            select(Transaction.id)
            .join(
                TransactionLeg,
                TransactionLeg.transaction_id == Transaction.id,
            )
            .where(
                Transaction.workspace_id == workspace_id,
                Transaction.category_id == Category.id,
                TransactionLeg.account_id.in_(account_ids),
            )
        )
        statement = statement.where(
            or_(Category.archived_at.is_(None), used_by_visible_transaction)
        )
    return list((await session.execute(statement.order_by(Category.name))).scalars())


@router.post(
    "/workspaces/{workspace_id}/categories",
    response_model=CategoryOut,
    status_code=201,
)
async def create_category(
    workspace_id: int,
    body: CategoryCreate,
    workspace: Workspace = Depends(require_workspace_owner),
    session: AsyncSession = Depends(get_session),
):
    del workspace
    name = " ".join(body.name.strip().split())
    category = Category(
        workspace_id=workspace_id,
        name=name,
        normalized_name=normalize_name(name),
        kind=body.kind,
        icon=body.icon,
        color=body.color,
    )
    session.add(category)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Category name already exists")
    await session.refresh(category)
    return category


@router.patch(
    "/workspaces/{workspace_id}/categories/{category_id}",
    response_model=CategoryOut,
)
async def patch_category(
    workspace_id: int,
    category_id: int,
    body: CategoryPatch,
    workspace: Workspace = Depends(require_workspace_owner),
    session: AsyncSession = Depends(get_session),
):
    del workspace
    category = await _category(
        session, category_id, workspace_id, allow_archived=True
    )
    if body.name is not None:
        category.name = " ".join(body.name.strip().split())
        category.normalized_name = normalize_name(category.name)
    if body.kind is not None:
        category.kind = body.kind
    if "icon" in body.model_fields_set:
        category.icon = body.icon
    if "color" in body.model_fields_set:
        category.color = body.color
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
    return category


@router.post(
    "/workspaces/{workspace_id}/categories/{category_id}/archive",
    response_model=CategoryOut,
)
async def archive_category(
    workspace_id: int,
    category_id: int,
    workspace: Workspace = Depends(require_workspace_owner),
    session: AsyncSession = Depends(get_session),
):
    del workspace
    category = await _category(session, category_id, workspace_id)
    category.archived_at = utcnow()
    await session.commit()
    await session.refresh(category)
    return category
