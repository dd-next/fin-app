"""Personal workspace reads and settings."""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.access import require_workspace_owner
from app.auth import require_user
from app.db import get_session
from app.models import Asset, User, Workspace
from app.schemas import WorkspaceOut, WorkspacePatch


router = APIRouter(prefix="/workspaces", tags=["workspaces"])


async def workspace_out(session: AsyncSession, workspace: Workspace) -> WorkspaceOut:
    await session.refresh(workspace, attribute_names=["base_asset"])
    return WorkspaceOut(
        id=workspace.id,
        owner_user_id=workspace.owner_user_id,
        name=workspace.name,
        timezone=workspace.timezone,
        base_asset=workspace.base_asset,
        created_at=workspace.created_at,
    )


@router.get("", response_model=list[WorkspaceOut])
async def list_workspaces(
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    workspaces = list(
        (
            await session.execute(
                select(Workspace)
                .where(
                    Workspace.owner_user_id == user.id,
                    Workspace.archived_at.is_(None),
                )
                .order_by(Workspace.id)
            )
        ).scalars()
    )
    return [await workspace_out(session, workspace) for workspace in workspaces]


@router.get("/{workspace_id}", response_model=WorkspaceOut)
async def get_workspace(
    workspace: Workspace = Depends(require_workspace_owner),
    session: AsyncSession = Depends(get_session),
):
    return await workspace_out(session, workspace)


@router.patch("/{workspace_id}", response_model=WorkspaceOut)
async def patch_workspace(
    body: WorkspacePatch,
    workspace: Workspace = Depends(require_workspace_owner),
    session: AsyncSession = Depends(get_session),
):
    if body.name is not None:
        workspace.name = body.name.strip()
    if body.timezone is not None:
        try:
            ZoneInfo(body.timezone)
        except ZoneInfoNotFoundError:
            raise HTTPException(status_code=422, detail="Unknown timezone")
        workspace.timezone = body.timezone
    if body.base_asset_code is not None:
        asset = (
            await session.execute(
                select(Asset).where(
                    Asset.code == body.base_asset_code,
                    Asset.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        if asset is None:
            raise HTTPException(status_code=422, detail="Unknown base asset")
        workspace.base_asset_id = asset.id
    await session.commit()
    await session.refresh(workspace)
    return await workspace_out(session, workspace)
