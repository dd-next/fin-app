"""Workspace membership access checks shared by all financial routes."""

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_auth, web_auth_enabled
from app.db import get_session
from app.models import User, WorkspaceMember


async def membership_for(
    session: AsyncSession, user_id: int, workspace_id: int
) -> WorkspaceMember | None:
    return (
        await session.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.user_id == user_id,
                WorkspaceMember.workspace_id == workspace_id,
            )
        )
    ).scalar_one_or_none()


async def require_workspace_access(
    workspace_id: int = 1,
    user: User | None = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
) -> WorkspaceMember | None:
    # Legacy local/Telegram mode remains restricted to the migrated workspace.
    if not web_auth_enabled():
        if workspace_id != 1:
            raise HTTPException(status_code=403, detail="Workspace access denied")
        return None
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    member = await membership_for(session, user.id, workspace_id)
    if member is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return member


async def require_workspace_owner(
    workspace_id: int,
    user: User = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
) -> WorkspaceMember:
    member = await membership_for(session, user.id, workspace_id)
    if member is None or member.role != "owner":
        raise HTTPException(status_code=403, detail="Workspace owner required")
    return member
