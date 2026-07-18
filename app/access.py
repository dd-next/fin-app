"""Workspace and per-account authorization for FinApp v2."""

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_user
from app.db import get_session
from app.models import Account, AccountAccess, User, Workspace


ACTION_ROLES = {
    "view": {"owner", "editor", "contributor", "viewer"},
    "expense": {"owner", "editor", "contributor"},
    "income": {"owner", "editor"},
    "edit": {"owner", "editor"},
    "account_edit": {"owner", "editor"},
    "owner": {"owner"},
}


async def account_role(
    session: AsyncSession, account: Account, user_id: int
) -> str | None:
    if account.owner_user_id == user_id:
        return "owner"
    return (
        await session.execute(
            select(AccountAccess.role).where(
                AccountAccess.account_id == account.id,
                AccountAccess.user_id == user_id,
            )
        )
    ).scalar_one_or_none()


async def require_account_action(
    session: AsyncSession,
    account_id: int,
    user_id: int,
    action: str,
    *,
    allow_archived: bool = False,
) -> tuple[Account, str]:
    account = await session.get(Account, account_id)
    if account is None or (account.archived_at is not None and not allow_archived):
        raise HTTPException(status_code=404, detail="Account not found")
    role = await account_role(session, account, user_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Account not found")
    if role not in ACTION_ROLES[action]:
        raise HTTPException(status_code=403, detail="Account permission denied")
    await session.refresh(account, attribute_names=["asset"])
    return account, role


async def visible_account_ids(session: AsyncSession, user_id: int) -> set[int]:
    owned = select(Account.id).where(Account.owner_user_id == user_id)
    shared = select(AccountAccess.account_id).where(AccountAccess.user_id == user_id)
    return set((await session.execute(owned.union(shared))).scalars())


async def require_workspace_category_reader(
    workspace_id: int,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> Workspace:
    workspace = await session.get(Workspace, workspace_id)
    if workspace is None or workspace.archived_at is not None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if workspace.owner_user_id == user.id:
        return workspace
    shared = (
        await session.execute(
            select(AccountAccess.id)
            .join(Account, Account.id == AccountAccess.account_id)
            .where(
                Account.workspace_id == workspace_id,
                AccountAccess.user_id == user.id,
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if shared is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace


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
