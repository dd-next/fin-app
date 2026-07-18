"""Per-account invitations and access management."""

from datetime import timedelta
import hashlib
import secrets

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.access import require_account_action
from app.auth import require_user
from app.db import get_session
from app.models import Account, AccountAccess, AccountInvitation, User, utcnow
from app.schemas import (
    AccountAccessOut,
    AccountAccessPatch,
    AccountInvitationCreate,
    AccountInvitationOut,
    UserOut,
)


router = APIRouter(tags=["account-sharing"])


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


@router.get("/accounts/{account_id}/access", response_model=list[AccountAccessOut])
async def list_access(
    account_id: int,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    account, _ = await require_account_action(
        session, account_id, user.id, "owner", allow_archived=True
    )
    owner = await session.get(User, account.owner_user_id)
    assert owner is not None
    rows = (
        await session.execute(
            select(AccountAccess, User)
            .join(User, User.id == AccountAccess.user_id)
            .where(AccountAccess.account_id == account.id)
            .order_by(AccountAccess.created_at)
        )
    ).all()
    return [
        AccountAccessOut(
            account_id=account.id,
            user=UserOut.model_validate(owner),
            role="owner",
            created_at=None,
        ),
        *[
            AccountAccessOut(
                account_id=account.id,
                user=UserOut.model_validate(member),
                role=access.role,
                created_at=access.created_at,
            )
            for access, member in rows
        ],
    ]


@router.post(
    "/accounts/{account_id}/invitations",
    response_model=AccountInvitationOut,
    status_code=201,
)
async def create_invitation(
    account_id: int,
    body: AccountInvitationCreate,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    account, _ = await require_account_action(session, account_id, user.id, "owner")
    raw = secrets.token_urlsafe(32)
    expires_at = utcnow() + timedelta(days=7)
    session.add(
        AccountInvitation(
            account_id=account.id,
            created_by_user_id=user.id,
            role=body.role,
            token_hash=_hash_token(raw),
            expires_at=expires_at,
        )
    )
    await session.commit()
    return AccountInvitationOut(
        token=raw,
        account_id=account.id,
        role=body.role,
        expires_at=expires_at,
    )


@router.post(
    "/account-invitations/{token}/accept", response_model=AccountAccessOut
)
async def accept_invitation(
    token: str,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    invitation = (
        await session.execute(
            select(AccountInvitation).where(
                AccountInvitation.token_hash == _hash_token(token)
            )
        )
    ).scalar_one_or_none()
    if (
        invitation is None
        or invitation.accepted_at is not None
        or invitation.expires_at <= utcnow()
    ):
        raise HTTPException(status_code=410, detail="Invitation is invalid or expired")
    account = await session.get(Account, invitation.account_id)
    assert account is not None
    if account.archived_at is not None:
        raise HTTPException(status_code=410, detail="Invitation is invalid or expired")
    if account.owner_user_id == user.id:
        raise HTTPException(status_code=409, detail="Account owner already has access")
    access = AccountAccess(
        account_id=account.id,
        user_id=user.id,
        role=invitation.role,
    )
    session.add(access)
    invitation.accepted_at = utcnow()
    invitation.accepted_by_user_id = user.id
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Account access already exists")
    await session.refresh(access)
    return AccountAccessOut(
        account_id=account.id,
        user=UserOut.model_validate(user),
        role=access.role,
        created_at=access.created_at,
    )


@router.patch(
    "/accounts/{account_id}/access/{target_user_id}",
    response_model=AccountAccessOut,
)
async def patch_access(
    account_id: int,
    target_user_id: int,
    body: AccountAccessPatch,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    account, _ = await require_account_action(
        session, account_id, user.id, "owner", allow_archived=True
    )
    access = (
        await session.execute(
            select(AccountAccess).where(
                AccountAccess.account_id == account.id,
                AccountAccess.user_id == target_user_id,
            )
        )
    ).scalar_one_or_none()
    target = await session.get(User, target_user_id)
    if access is None or target is None:
        raise HTTPException(status_code=404, detail="Account access not found")
    access.role = body.role
    await session.commit()
    await session.refresh(access)
    return AccountAccessOut(
        account_id=account.id,
        user=UserOut.model_validate(target),
        role=access.role,
        created_at=access.created_at,
    )


@router.delete(
    "/accounts/{account_id}/access/{target_user_id}", status_code=204
)
async def delete_access(
    account_id: int,
    target_user_id: int,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    account, _ = await require_account_action(
        session, account_id, user.id, "owner", allow_archived=True
    )
    access = (
        await session.execute(
            select(AccountAccess).where(
                AccountAccess.account_id == account.id,
                AccountAccess.user_id == target_user_id,
            )
        )
    ).scalar_one_or_none()
    if access is None:
        raise HTTPException(status_code=404, detail="Account access not found")
    await session.delete(access)
    await session.commit()
    return Response(status_code=204)
