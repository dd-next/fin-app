"""Workspace ownership checks for private Plan and Tracker data."""

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_user
from app.db import get_session
from app.models import User, Workspace


async def require_workspace_owner(
    workspace_id: int,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> Workspace:
    workspace = await session.get(Workspace, workspace_id)
    if (
        workspace is None
        or workspace.archived_at is not None
        or workspace.owner_user_id != user.id
    ):
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace
