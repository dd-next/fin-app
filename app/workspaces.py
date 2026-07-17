"""Personal/shared workspace management and one-time family invites."""

from datetime import timedelta
import hashlib
import secrets

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.access import require_workspace_access, require_workspace_owner
from app.auth import create_session, create_user, require_web_user, set_session_cookie
from app.db import get_session
from app.models import User, Workspace, WorkspaceInvite, WorkspaceMember, utcnow
from app.schemas import (
    BootstrapIn,
    InviteAcceptanceOut,
    UserOut,
    WorkspaceCreate,
    WorkspaceInviteOut,
    WorkspaceMemberOut,
    WorkspaceOut,
)


router = APIRouter(tags=["workspaces"])


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _workspace_out(workspace: Workspace, role: str) -> WorkspaceOut:
    return WorkspaceOut(
        id=workspace.id,
        name=workspace.name,
        kind=workspace.kind,
        timezone=workspace.timezone,
        role=role,
    )


@router.get("/workspaces", response_model=list[WorkspaceOut])
async def list_workspaces(
    user: User = Depends(require_web_user),
    session: AsyncSession = Depends(get_session),
):
    rows = (
        await session.execute(
            select(Workspace, WorkspaceMember.role)
            .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
            .where(
                WorkspaceMember.user_id == user.id,
                Workspace.archived_at.is_(None),
            )
            .order_by(Workspace.kind, Workspace.id)
        )
    ).all()
    return [_workspace_out(workspace, role) for workspace, role in rows]


@router.post("/workspaces", response_model=WorkspaceOut)
async def create_shared_workspace(
    body: WorkspaceCreate,
    user: User = Depends(require_web_user),
    session: AsyncSession = Depends(get_session),
):
    workspace = Workspace(
        name=body.name.strip(),
        kind="shared",
        timezone="Asia/Ho_Chi_Minh",
    )
    session.add(workspace)
    await session.flush()
    session.add(
        WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner")
    )
    await session.commit()
    await session.refresh(workspace)
    return _workspace_out(workspace, "owner")


@router.get(
    "/workspaces/{workspace_id}/members",
    response_model=list[WorkspaceMemberOut],
    dependencies=[Depends(require_workspace_access)],
)
async def list_members(
    workspace_id: int, session: AsyncSession = Depends(get_session)
):
    rows = (
        await session.execute(
            select(WorkspaceMember, User)
            .join(User, User.id == WorkspaceMember.user_id)
            .where(WorkspaceMember.workspace_id == workspace_id)
            .order_by(WorkspaceMember.joined_at)
        )
    ).all()
    return [
        WorkspaceMemberOut(
            user=UserOut.model_validate(user),
            role=member.role,
            joined_at=member.joined_at,
        )
        for member, user in rows
    ]


@router.post(
    "/workspaces/{workspace_id}/invites",
    response_model=WorkspaceInviteOut,
)
async def create_invite(
    workspace_id: int,
    owner: WorkspaceMember = Depends(require_workspace_owner),
    session: AsyncSession = Depends(get_session),
):
    workspace = await session.get(Workspace, workspace_id)
    if workspace is None or workspace.kind != "shared":
        raise HTTPException(status_code=409, detail="Only shared workspaces accept invites")
    raw = secrets.token_urlsafe(32)
    expires_at = utcnow() + timedelta(days=7)
    session.add(
        WorkspaceInvite(
            workspace_id=workspace_id,
            token_hash=_hash_token(raw),
            role="editor",
            created_by_user_id=owner.user_id,
            expires_at=expires_at,
        )
    )
    await session.commit()
    return WorkspaceInviteOut(
        token=raw, workspace_id=workspace_id, expires_at=expires_at
    )


@router.post("/invites/{token}/accept", response_model=InviteAcceptanceOut)
async def accept_invite(
    token: str,
    body: BootstrapIn,
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    invite = (
        await session.execute(
            select(WorkspaceInvite).where(
                WorkspaceInvite.token_hash == _hash_token(token)
            )
        )
    ).scalar_one_or_none()
    if (
        invite is None
        or invite.accepted_at is not None
        or invite.expires_at <= utcnow()
    ):
        raise HTTPException(status_code=410, detail="Invite is invalid or expired")
    workspace = await session.get(Workspace, invite.workspace_id)
    if workspace is None or workspace.archived_at is not None:
        raise HTTPException(status_code=410, detail="Workspace is unavailable")

    user = await create_user(
        session, body.username, body.password, body.display_name
    )
    session.add(
        WorkspaceMember(
            workspace_id=workspace.id,
            user_id=user.id,
            role=invite.role,
        )
    )
    invite.accepted_at = utcnow()
    await session.commit()
    raw_session = await create_session(session, user)
    set_session_cookie(response, raw_session)
    return InviteAcceptanceOut(
        user=UserOut.model_validate(user),
        workspace=_workspace_out(workspace, invite.role),
    )
