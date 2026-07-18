"""Owned account management and derived balances."""

from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import primary_workspace, require_user
from app.access import account_role, require_account_action, visible_account_ids
from app.db import get_session
from app.ledger import (
    ZERO,
    account_balance,
    account_out,
    account_values,
    financial_times,
    normalize_name,
    quantize_asset_amount,
    require_asset_code,
    transaction_out,
    validate_amount,
)
from app.models import Account, Asset, Transaction, TransactionLeg, User, utcnow
from app.schemas import (
    AccountCreate,
    AccountOut,
    AccountPatch,
    AccountSummaryOut,
    AssetOut,
    ReconcileIn,
    TransactionOut,
    UnvaluedAssetOut,
)


router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.post("", response_model=AccountOut, status_code=201)
async def create_account(
    body: AccountCreate,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    workspace = await primary_workspace(session, user.id)
    asset = await require_asset_code(session, body.asset_code)
    opening = validate_amount(body.opening_balance, asset, allow_zero=True)
    name = " ".join(body.name.strip().split())
    account = Account(
        workspace_id=workspace.id,
        owner_user_id=user.id,
        name=name,
        normalized_name=normalize_name(name),
        storage_type=body.storage_type,
        purpose=body.purpose,
        asset_id=asset.id,
        institution=body.institution.strip() if body.institution else None,
        include_in_available=body.include_in_available,
    )
    session.add(account)
    try:
        await session.flush()
        if opening != 0:
            occurred_at, local_date = financial_times(workspace, None, None)
            transaction = Transaction(
                workspace_id=workspace.id,
                created_by_user_id=user.id,
                type="adjustment",
                note="Opening balance",
                occurred_at=occurred_at,
                local_date=local_date,
                source="manual",
                status="posted",
            )
            transaction.legs.append(
                TransactionLeg(account_id=account.id, asset_id=asset.id, amount=opening)
            )
            session.add(transaction)
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Account name already exists")
    await session.refresh(account)
    return await account_out(session, account, workspace.base_asset_id)


@router.get("", response_model=list[AccountOut])
async def list_accounts(
    include_archived: bool = False,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    workspace = await primary_workspace(session, user.id)
    visible_ids = await visible_account_ids(session, user.id)
    statement = select(Account).where(Account.id.in_(visible_ids))
    if not include_archived:
        statement = statement.where(Account.archived_at.is_(None))
    accounts = list((await session.execute(statement.order_by(Account.name))).scalars())
    return [
        await account_out(
            session,
            account,
            workspace.base_asset_id,
            access_role=(await account_role(session, account, user.id)) or "viewer",
        )
        for account in accounts
    ]


@router.get("/summary", response_model=AccountSummaryOut)
async def account_summary(
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    workspace = await primary_workspace(session, user.id)
    base_asset = await session.get(Asset, workspace.base_asset_id)
    assert base_asset is not None
    visible_ids = await visible_account_ids(session, user.id)
    accounts = list(
        (
            await session.execute(
                select(Account)
                .where(
                    Account.id.in_(visible_ids),
                    Account.archived_at.is_(None),
                )
                .order_by(Account.name)
            )
        ).scalars()
    )
    exact_values = [
        await account_values(session, account, base_asset) for account in accounts
    ]
    outputs = [
        await account_out(
            session,
            account,
            workspace.base_asset_id,
            access_role=(await account_role(session, account, user.id)) or "viewer",
            values=values,
        )
        for account, values in zip(accounts, exact_values, strict=True)
    ]
    net_worth = sum(
        (
            values.valued_balance
            for values in exact_values
            if values.valued_balance is not None
        ),
        ZERO,
    )
    available = sum(
        (
            values.valued_balance
            for account, values in zip(accounts, exact_values, strict=True)
            if account.include_in_available and values.valued_balance is not None
        ),
        ZERO,
    )
    unvalued_totals: dict[int, Decimal] = {}
    assets: dict[int, AssetOut] = {}
    for account, output, values in zip(
        accounts, outputs, exact_values, strict=True
    ):
        if values.valued_balance is None and values.balance != 0:
            unvalued_totals[account.asset_id] = (
                unvalued_totals.get(account.asset_id, ZERO) + values.balance
            )
            assets[account.asset_id] = output.asset
    return AccountSummaryOut(
        base_asset=AssetOut.model_validate(base_asset),
        net_worth=quantize_asset_amount(net_worth, base_asset),
        available=quantize_asset_amount(available, base_asset),
        accounts=outputs,
        unvalued=[
            UnvaluedAssetOut(
                asset=assets[asset_id],
                total=quantize_asset_amount(total, assets[asset_id]),
            )
            for asset_id, total in sorted(
                unvalued_totals.items(), key=lambda item: assets[item[0]].code
            )
        ],
    )


@router.get("/{account_id}", response_model=AccountOut)
async def get_account(
    account_id: int,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    workspace = await primary_workspace(session, user.id)
    account, role = await require_account_action(
        session, account_id, user.id, "view", allow_archived=True
    )
    return await account_out(
        session, account, workspace.base_asset_id, access_role=role
    )


@router.patch("/{account_id}", response_model=AccountOut)
async def patch_account(
    account_id: int,
    body: AccountPatch,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    workspace = await primary_workspace(session, user.id)
    account, role = await require_account_action(
        session, account_id, user.id, "account_edit"
    )
    if body.name is not None:
        account.name = " ".join(body.name.strip().split())
        account.normalized_name = normalize_name(account.name)
    if body.storage_type is not None:
        account.storage_type = body.storage_type
    if body.purpose is not None:
        account.purpose = body.purpose
    if "institution" in body.model_fields_set:
        account.institution = body.institution.strip() if body.institution else None
    if body.include_in_available is not None:
        account.include_in_available = body.include_in_available
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Account name already exists")
    await session.refresh(account)
    return await account_out(
        session, account, workspace.base_asset_id, access_role=role
    )


@router.post("/{account_id}/reconcile", response_model=TransactionOut)
async def reconcile_account(
    account_id: int,
    body: ReconcileIn,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    workspace = await primary_workspace(session, user.id)
    account, _ = await require_account_action(session, account_id, user.id, "owner")
    target = validate_amount(body.target_balance, account.asset, allow_zero=True)
    delta = target - await account_balance(session, account.id)
    validate_amount(delta, account.asset)
    occurred_at, local_date = financial_times(workspace, None, None)
    transaction = Transaction(
        workspace_id=workspace.id,
        created_by_user_id=user.id,
        type="adjustment",
        note=body.note or "Balance reconciliation",
        occurred_at=occurred_at,
        local_date=local_date,
        source="manual",
        status="posted",
    )
    transaction.legs.append(
        TransactionLeg(account_id=account.id, asset_id=account.asset_id, amount=delta)
    )
    session.add(transaction)
    await session.commit()
    await session.refresh(transaction)
    return await transaction_out(session, transaction)


@router.post("/{account_id}/archive", response_model=AccountOut)
async def archive_account(
    account_id: int,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    workspace = await primary_workspace(session, user.id)
    account, role = await require_account_action(session, account_id, user.id, "owner")
    account.archived_at = utcnow()
    await session.commit()
    await session.refresh(account)
    return await account_out(
        session, account, workspace.base_asset_id, access_role=role
    )
