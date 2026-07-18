"""Financial transaction commands and history."""

from datetime import UTC, date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import primary_workspace, require_user
from app.access import require_account_action, visible_account_ids
from app.db import get_session
from app.ledger import (
    financial_times,
    quantize_exchange_rate,
    rate_out,
    require_asset_code,
    require_category,
    transaction_out,
    validate_amount,
)
from app.models import (
    Account,
    Asset,
    BudgetPeriod,
    ExchangeRate,
    PlanOccurrence,
    Transaction,
    TransactionLeg,
    User,
    Workspace,
    utcnow,
)
from app.schemas import (
    AdjustmentIn,
    AssignAccountIn,
    ExchangeIn,
    ExchangeRateOut,
    SingleTransactionIn,
    TransactionOut,
    TransactionPageOut,
    TransactionPatch,
    TransferIn,
    VoidTransactionIn,
)
from app.tracker_service import (
    attach_transaction_to_tracker,
    budget_period_status,
    reopen_plan_commitment,
    sync_plan_fulfillment,
    workspace_today,
)


router = APIRouter(tags=["transactions"])


def _transaction(
    workspace: Workspace,
    user: User,
    transaction_type: str,
    occurred_at: datetime,
    local_date: date,
    *,
    category_id: int | None = None,
    counterparty: str | None = None,
    note: str | None = None,
    status: str = "posted",
    parent_transaction_id: int | None = None,
) -> Transaction:
    return Transaction(
        workspace_id=workspace.id,
        created_by_user_id=user.id,
        type=transaction_type,
        category_id=category_id,
        parent_transaction_id=parent_transaction_id,
        counterparty=counterparty,
        note=note,
        occurred_at=occurred_at,
        local_date=local_date,
        source="manual",
        status=status,
    )


async def _principal(
    session: AsyncSession,
    user: User,
    account_id: int | None,
    asset_code: str | None,
    action: str,
) -> tuple[Account | None, Asset]:
    if account_id is not None:
        account, _ = await require_account_action(
            session, account_id, user.id, action
        )
        if asset_code is not None and asset_code != account.asset.code:
            raise HTTPException(status_code=422, detail="Asset does not match account")
        return account, account.asset
    if asset_code is None:
        raise HTTPException(status_code=422, detail="asset_code is required without account_id")
    return None, await require_asset_code(session, asset_code)


async def _create_single(
    session: AsyncSession,
    user: User,
    transaction_type: str,
    body: SingleTransactionIn,
) -> Transaction:
    account, asset = await _principal(
        session,
        user,
        body.account_id,
        body.asset_code,
        "expense" if transaction_type == "expense" else "income",
    )
    workspace = (
        await session.get(Workspace, account.workspace_id)
        if account is not None
        else await primary_workspace(session, user.id)
    )
    assert workspace is not None
    amount = validate_amount(body.amount, asset)
    category = await require_category(
        session, body.category_id, workspace.id, transaction_type
    )
    occurred_at, local_date = financial_times(
        workspace, body.occurred_at, body.local_date
    )
    transaction = _transaction(
        workspace,
        user,
        transaction_type,
        occurred_at,
        local_date,
        category_id=category.id if category else None,
        counterparty=body.counterparty,
        note=body.note,
        status="posted" if account else "unassigned",
    )
    signed = -amount if transaction_type == "expense" else amount
    transaction.legs.append(
        TransactionLeg(
            account_id=account.id if account else None,
            asset_id=asset.id,
            amount=signed,
        )
    )
    session.add(transaction)
    await session.flush()
    await attach_transaction_to_tracker(session, transaction, body.base_amount)
    await session.commit()
    await session.refresh(transaction)
    return transaction


@router.post("/transactions/expense", response_model=TransactionOut, status_code=201)
async def create_expense(
    body: SingleTransactionIn,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    transaction = await _create_single(session, user, "expense", body)
    workspace = await session.get(Workspace, transaction.workspace_id)
    assert workspace is not None
    return await transaction_out(
        session,
        transaction,
        visible_account_ids=(
            None
            if workspace.owner_user_id == user.id
            else await visible_account_ids(session, user.id)
        ),
    )


@router.post("/transactions/income", response_model=TransactionOut, status_code=201)
async def create_income(
    body: SingleTransactionIn,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    transaction = await _create_single(session, user, "income", body)
    workspace = await session.get(Workspace, transaction.workspace_id)
    assert workspace is not None
    return await transaction_out(
        session,
        transaction,
        visible_account_ids=(
            None
            if workspace.owner_user_id == user.id
            else await visible_account_ids(session, user.id)
        ),
    )


@router.post("/transactions/transfer", response_model=TransactionOut, status_code=201)
async def create_transfer(
    body: TransferIn,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    if body.category_id is not None:
        raise HTTPException(status_code=422, detail="Transfers cannot have a category")
    source, _ = await require_account_action(
        session, body.from_account_id, user.id, "edit"
    )
    target, _ = await require_account_action(
        session, body.to_account_id, user.id, "edit"
    )
    if source.workspace_id != target.workspace_id:
        raise HTTPException(status_code=422, detail="Accounts must belong to one workspace")
    workspace = await session.get(Workspace, source.workspace_id)
    assert workspace is not None
    if source.id == target.id:
        raise HTTPException(status_code=422, detail="Accounts must be different")
    if source.asset_id != target.asset_id:
        raise HTTPException(status_code=422, detail="Use exchange for different assets")
    amount = validate_amount(body.amount, source.asset)
    occurred_at, local_date = financial_times(
        workspace, body.occurred_at, body.local_date
    )
    transaction = _transaction(
        workspace, user, "transfer", occurred_at, local_date,
        counterparty=body.counterparty, note=body.note,
    )
    transaction.legs.extend(
        [
            TransactionLeg(account_id=source.id, asset_id=source.asset_id, amount=-amount),
            TransactionLeg(account_id=target.id, asset_id=target.asset_id, amount=amount),
        ]
    )
    session.add(transaction)
    await session.commit()
    await session.refresh(transaction)
    return await transaction_out(session, transaction)


async def _replace_rates(
    session: AsyncSession,
    transaction: Transaction,
    source: Account,
    source_amount: Decimal,
    target: Account,
    target_amount: Decimal,
) -> None:
    await session.execute(
        delete(ExchangeRate).where(
            ExchangeRate.source_transaction_id == transaction.id
        )
    )
    session.add_all(
        [
            ExchangeRate(
                source_transaction_id=transaction.id,
                base_asset_id=source.asset_id,
                quote_asset_id=target.asset_id,
                rate=quantize_exchange_rate(target_amount / source_amount),
                captured_at=transaction.occurred_at,
            ),
            ExchangeRate(
                source_transaction_id=transaction.id,
                base_asset_id=target.asset_id,
                quote_asset_id=source.asset_id,
                rate=quantize_exchange_rate(source_amount / target_amount),
                captured_at=transaction.occurred_at,
            ),
        ]
    )


@router.post("/transactions/exchange", response_model=TransactionOut, status_code=201)
async def create_exchange(
    body: ExchangeIn,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    if body.category_id is not None:
        raise HTTPException(status_code=422, detail="Exchanges cannot have a category")
    source, _ = await require_account_action(
        session, body.from_account_id, user.id, "edit"
    )
    target, _ = await require_account_action(
        session, body.to_account_id, user.id, "edit"
    )
    if source.workspace_id != target.workspace_id:
        raise HTTPException(status_code=422, detail="Accounts must belong to one workspace")
    workspace = await session.get(Workspace, source.workspace_id)
    assert workspace is not None
    if source.id == target.id or source.asset_id == target.asset_id:
        raise HTTPException(status_code=422, detail="Exchange requires different assets")
    from_amount = validate_amount(body.from_amount, source.asset)
    to_amount = validate_amount(body.to_amount, target.asset)
    occurred_at, local_date = financial_times(
        workspace, body.occurred_at, body.local_date
    )
    transaction = _transaction(
        workspace, user, "exchange", occurred_at, local_date,
        counterparty=body.counterparty, note=body.note,
    )
    transaction.legs.extend(
        [
            TransactionLeg(account_id=source.id, asset_id=source.asset_id, amount=-from_amount),
            TransactionLeg(account_id=target.id, asset_id=target.asset_id, amount=to_amount),
        ]
    )
    session.add(transaction)
    await session.flush()
    await _replace_rates(session, transaction, source, from_amount, target, to_amount)
    if body.fee is not None:
        fee_account, _ = await require_account_action(
            session, body.fee.account_id, user.id, "edit"
        )
        if fee_account.workspace_id != workspace.id:
            raise HTTPException(status_code=422, detail="Fee account belongs to another workspace")
        fee_amount = validate_amount(body.fee.amount, fee_account.asset)
        fee_category = await require_category(
            session, body.fee.category_id, workspace.id, "expense"
        )
        fee = _transaction(
            workspace,
            user,
            "expense",
            occurred_at,
            local_date,
            category_id=fee_category.id if fee_category else None,
            note=body.fee.note or "Exchange fee",
            parent_transaction_id=transaction.id,
        )
        fee.legs.append(
            TransactionLeg(
                account_id=fee_account.id,
                asset_id=fee_account.asset_id,
                amount=-fee_amount,
            )
        )
        session.add(fee)
        await session.flush()
        await attach_transaction_to_tracker(
            session, fee, body.fee.base_amount
        )
    await session.commit()
    await session.refresh(transaction)
    return await transaction_out(session, transaction)


@router.post("/transactions/adjustment", response_model=TransactionOut, status_code=201)
async def create_adjustment(
    body: AdjustmentIn,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    if body.category_id is not None:
        raise HTTPException(status_code=422, detail="Adjustments cannot have a category")
    account, _ = await require_account_action(
        session, body.account_id, user.id, "owner"
    )
    workspace = await session.get(Workspace, account.workspace_id)
    assert workspace is not None
    delta = validate_amount(body.delta, account.asset)
    occurred_at, local_date = financial_times(
        workspace, body.occurred_at, body.local_date
    )
    transaction = _transaction(
        workspace, user, "adjustment", occurred_at, local_date, note=body.note
    )
    transaction.legs.append(
        TransactionLeg(account_id=account.id, asset_id=account.asset_id, amount=delta)
    )
    session.add(transaction)
    await session.commit()
    await session.refresh(transaction)
    return await transaction_out(session, transaction)


async def _visible_transaction(
    session: AsyncSession, transaction_id: int, user: User
) -> tuple[Transaction, set[int] | None]:
    transaction = await session.get(Transaction, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    workspace = await session.get(Workspace, transaction.workspace_id)
    assert workspace is not None
    if workspace.owner_user_id == user.id:
        return transaction, None
    visible_ids = await visible_account_ids(session, user.id)
    legs = await _transaction_legs(session, transaction.id)
    has_visible_leg = any(
        leg.account_id is not None and leg.account_id in visible_ids for leg in legs
    )
    is_own_unassigned = (
        transaction.created_by_user_id == user.id
        and transaction.status == "unassigned"
        and any(leg.account_id is None for leg in legs)
    )
    if not has_visible_leg and not is_own_unassigned:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction, visible_ids


async def _require_transaction_edit(
    session: AsyncSession, transaction_id: int, user: User
) -> tuple[Transaction, set[int] | None]:
    transaction, visible_ids = await _visible_transaction(session, transaction_id, user)
    legs = await _transaction_legs(session, transaction.id)
    child_legs = list(
        (
            await session.execute(
                select(TransactionLeg)
                .join(Transaction, Transaction.id == TransactionLeg.transaction_id)
                .where(Transaction.parent_transaction_id == transaction.id)
            )
        ).scalars()
    )
    for leg in [*legs, *child_legs]:
        if leg.account_id is None:
            if transaction.created_by_user_id != user.id:
                raise HTTPException(status_code=403, detail="Transaction permission denied")
            continue
        await require_account_action(
            session,
            leg.account_id,
            user.id,
            "owner" if transaction.type == "adjustment" else "edit",
            allow_archived=True,
        )
    return transaction, visible_ids


@router.get("/transactions", response_model=TransactionPageOut)
async def list_transactions(
    workspace_id: int | None = None,
    account_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    type: str | None = None,
    category_id: int | None = None,
    source: str | None = None,
    status: str | None = None,
    created_by_user_id: int | None = None,
    cursor: int | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    workspace = await primary_workspace(session, user.id)
    visible_ids = await visible_account_ids(session, user.id)
    statement = (
        select(Transaction)
        .outerjoin(TransactionLeg)
        .where(
            or_(
                Transaction.workspace_id == workspace.id,
                TransactionLeg.account_id.in_(visible_ids),
                (
                    (Transaction.created_by_user_id == user.id)
                    & (Transaction.status == "unassigned")
                    & TransactionLeg.account_id.is_(None)
                ),
            )
        )
    )
    if workspace_id is not None:
        statement = statement.where(Transaction.workspace_id == workspace_id)
    if account_id is not None:
        await require_account_action(
            session, account_id, user.id, "view", allow_archived=True
        )
        statement = statement.where(TransactionLeg.account_id == account_id)
    if date_from is not None:
        statement = statement.where(Transaction.local_date >= date_from)
    if date_to is not None:
        statement = statement.where(Transaction.local_date <= date_to)
    if type is not None:
        statement = statement.where(Transaction.type == type)
    if category_id is not None:
        statement = statement.where(Transaction.category_id == category_id)
    if source is not None:
        statement = statement.where(Transaction.source == source)
    if status is not None:
        statement = statement.where(Transaction.status == status)
    if created_by_user_id is not None:
        statement = statement.where(Transaction.created_by_user_id == created_by_user_id)
    if cursor is not None:
        statement = statement.where(Transaction.id < cursor)
    transactions = list(
        (
            await session.execute(
                statement.distinct().order_by(Transaction.id.desc()).limit(limit + 1)
            )
        ).scalars()
    )
    has_more = len(transactions) > limit
    page = transactions[:limit]
    return TransactionPageOut(
        items=[
            await transaction_out(
                session,
                item,
                visible_account_ids=(
                    None if item.workspace_id == workspace.id else visible_ids
                ),
            )
            for item in page
        ],
        next_cursor=page[-1].id if has_more and page else None,
    )


@router.get("/transactions/{transaction_id}", response_model=TransactionOut)
async def get_transaction(
    transaction_id: int,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    transaction, visible_ids = await _visible_transaction(
        session, transaction_id, user
    )
    return await transaction_out(
        session, transaction, visible_account_ids=visible_ids
    )


async def _transaction_legs(
    session: AsyncSession, transaction_id: int
) -> list[TransactionLeg]:
    return list(
        (
            await session.execute(
                select(TransactionLeg)
                .where(TransactionLeg.transaction_id == transaction_id)
                .order_by(TransactionLeg.id)
            )
        ).scalars()
    )


def _financial_state(
    transaction: Transaction, legs: list[TransactionLeg]
) -> tuple:
    """Capture persisted economic facts, excluding descriptive metadata."""
    return (
        transaction.occurred_at,
        transaction.local_date,
        transaction.status,
        tuple((leg.account_id, leg.asset_id, Decimal(leg.amount)) for leg in legs),
    )


@router.patch("/transactions/{transaction_id}", response_model=TransactionOut)
async def patch_transaction(
    transaction_id: int,
    body: TransactionPatch,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    transaction, visible_ids = await _require_transaction_edit(
        session, transaction_id, user
    )
    if transaction.status == "voided":
        raise HTTPException(status_code=409, detail="Voided transaction cannot be edited")
    workspace = await session.get(Workspace, transaction.workspace_id)
    assert workspace is not None
    existing_period = (
        await session.get(BudgetPeriod, transaction.budget_period_id)
        if transaction.budget_period_id is not None
        else None
    )
    if (
        existing_period is not None
        and budget_period_status(existing_period, workspace_today(workspace)) == "ended"
        and not body.confirm_ended_period
    ):
        raise HTTPException(
            status_code=409,
            detail="Ended period correction requires explicit confirmation",
        )
    legs = await _transaction_legs(session, transaction.id)
    original_financial_state = _financial_state(transaction, legs)
    original_base_amount = transaction.base_amount
    exchange_rate_inputs: tuple[Account, Decimal, Account, Decimal] | None = None
    if "note" in body.model_fields_set:
        transaction.note = body.note
    if "counterparty" in body.model_fields_set:
        transaction.counterparty = body.counterparty
    if body.occurred_at is not None:
        transaction.occurred_at, derived_date = financial_times(
            workspace, body.occurred_at, body.local_date
        )
        transaction.local_date = body.local_date or derived_date
    elif body.local_date is not None:
        transaction.local_date = body.local_date
    if "category_id" in body.model_fields_set:
        category = await require_category(
            session, body.category_id, workspace.id, transaction.type
        )
        transaction.category_id = category.id if category else None

    if transaction.type in {"expense", "income", "adjustment"}:
        leg = legs[0]
        if transaction.type == "adjustment":
            if body.delta is not None:
                account = (
                    (
                        await require_account_action(
                            session, leg.account_id, user.id, "owner"
                        )
                    )[0]
                    if leg.account_id
                    else None
                )
                assert account is not None
                leg.amount = validate_amount(body.delta, account.asset)
            if any(value is not None for value in (body.amount, body.from_amount, body.to_amount)):
                raise HTTPException(status_code=422, detail="Use delta for adjustment")
        else:
            current_asset = await session.get(Asset, leg.asset_id)
            assert current_asset is not None
            account = (
                (
                    await require_account_action(
                        session, leg.account_id, user.id, "edit"
                    )
                )[0]
                if leg.account_id is not None
                else None
            )
            asset = current_asset
            if "account_id" in body.model_fields_set:
                if body.account_id is None:
                    if workspace.owner_user_id != user.id:
                        raise HTTPException(
                            status_code=403,
                            detail="Only the workspace owner can unassign a transaction",
                        )
                    account = None
                else:
                    account = (
                        await require_account_action(
                            session, body.account_id, user.id, "edit"
                        )
                    )[0]
                    if account.workspace_id != transaction.workspace_id:
                        raise HTTPException(
                            status_code=422,
                            detail="Account belongs to another workspace",
                        )
                if account is not None:
                    asset = account.asset
            if "asset_code" in body.model_fields_set:
                if body.asset_code is None:
                    raise HTTPException(status_code=422, detail="asset_code cannot be null")
                requested_asset = await require_asset_code(session, body.asset_code)
                if account is not None and requested_asset.id != account.asset_id:
                    raise HTTPException(status_code=422, detail="Asset does not match account")
                asset = requested_asset
            assert asset is not None
            amount = validate_amount(body.amount if body.amount is not None else abs(leg.amount), asset)
            leg.account_id = account.id if account else None
            leg.asset_id = asset.id
            leg.amount = -amount if transaction.type == "expense" else amount
            transaction.status = "posted" if account else "unassigned"
    else:
        negative = next(leg for leg in legs if leg.amount < 0)
        positive = next(leg for leg in legs if leg.amount > 0)
        source_id = body.from_account_id or negative.account_id
        target_id = body.to_account_id or positive.account_id
        assert source_id is not None and target_id is not None
        source = (
            await require_account_action(session, source_id, user.id, "edit")
        )[0]
        target = (
            await require_account_action(session, target_id, user.id, "edit")
        )[0]
        if (
            source.workspace_id != transaction.workspace_id
            or target.workspace_id != transaction.workspace_id
        ):
            raise HTTPException(
                status_code=422, detail="Accounts must belong to the transaction workspace"
            )
        if source.id == target.id:
            raise HTTPException(status_code=422, detail="Accounts must be different")
        if transaction.type == "transfer" and source.asset_id != target.asset_id:
            raise HTTPException(status_code=422, detail="Transfer assets must match")
        if transaction.type == "exchange" and source.asset_id == target.asset_id:
            raise HTTPException(status_code=422, detail="Exchange assets must differ")
        from_amount = validate_amount(
            body.from_amount or abs(negative.amount), source.asset
        )
        to_amount = validate_amount(
            body.to_amount or positive.amount, target.asset
        )
        if transaction.type == "transfer" and from_amount != to_amount:
            raise HTTPException(status_code=422, detail="Transfer amounts must match")
        negative.account_id, negative.asset_id, negative.amount = source.id, source.asset_id, -from_amount
        positive.account_id, positive.asset_id, positive.amount = target.id, target.asset_id, to_amount
        if transaction.type == "exchange":
            exchange_rate_inputs = (source, from_amount, target, to_amount)
    has_financial_change = (
        _financial_state(transaction, legs) != original_financial_state
        or (
            "base_amount" in body.model_fields_set
            and body.base_amount != original_base_amount
        )
    )
    if exchange_rate_inputs is not None and has_financial_change:
        await _replace_rates(session, transaction, *exchange_rate_inputs)
    await session.flush()
    linked_occurrence = (
        await session.execute(
            select(PlanOccurrence).where(
                PlanOccurrence.transaction_id == transaction.id
            )
        )
    ).scalar_one_or_none()
    if linked_occurrence is not None and has_financial_change:
        await sync_plan_fulfillment(
            session, linked_occurrence, transaction, body.base_amount
        )
    elif (
        linked_occurrence is None
        and transaction.type in {"expense", "income"}
        and has_financial_change
    ):
        await attach_transaction_to_tracker(
            session, transaction, body.base_amount
        )
    elif transaction.type not in {"expense", "income"} and linked_occurrence is None:
        transaction.budget_period_id = None
        transaction.base_amount = None
        transaction.base_rate = None
        transaction.rate_source = None
    await session.commit()
    await session.refresh(transaction)
    return await transaction_out(
        session, transaction, visible_account_ids=visible_ids
    )


@router.post("/transactions/{transaction_id}/assign-account", response_model=TransactionOut)
async def assign_account(
    transaction_id: int,
    body: AssignAccountIn,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    transaction, visible_ids = await _visible_transaction(
        session, transaction_id, user
    )
    if transaction.status != "unassigned":
        raise HTTPException(status_code=409, detail="Transaction is not unassigned")
    workspace = await session.get(Workspace, transaction.workspace_id)
    assert workspace is not None
    if transaction.created_by_user_id != user.id and workspace.owner_user_id != user.id:
        raise HTTPException(status_code=403, detail="Transaction permission denied")
    legs = await _transaction_legs(session, transaction.id)
    if len(legs) != 1 or legs[0].account_id is not None:
        raise HTTPException(status_code=409, detail="Transaction cannot be assigned")
    action = "expense" if transaction.type == "expense" else "income"
    account = (
        await require_account_action(session, body.account_id, user.id, action)
    )[0]
    if account.workspace_id != transaction.workspace_id:
        raise HTTPException(status_code=422, detail="Account belongs to another workspace")
    if account.asset_id != legs[0].asset_id:
        raise HTTPException(status_code=422, detail="Account asset does not match transaction")
    legs[0].account_id = account.id
    transaction.status = "posted"
    await session.commit()
    await session.refresh(transaction)
    return await transaction_out(
        session, transaction, visible_account_ids=visible_ids
    )


@router.post("/transactions/{transaction_id}/void", response_model=TransactionOut)
async def void_transaction(
    transaction_id: int,
    body: VoidTransactionIn | None = None,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    transaction, visible_ids = await _require_transaction_edit(
        session, transaction_id, user
    )
    if transaction.status == "voided":
        raise HTTPException(status_code=409, detail="Transaction is already voided")
    workspace = await session.get(Workspace, transaction.workspace_id)
    assert workspace is not None
    period = (
        await session.get(BudgetPeriod, transaction.budget_period_id)
        if transaction.budget_period_id is not None
        else None
    )
    if (
        period is not None
        and budget_period_status(period, workspace_today(workspace)) == "ended"
        and not (body and body.confirm_ended_period)
    ):
        raise HTTPException(
            status_code=409,
            detail="Ended period correction requires explicit confirmation",
        )
    now = utcnow()
    transaction.status = "voided"
    transaction.voided_at = now
    await session.execute(
        update(Transaction)
        .where(Transaction.parent_transaction_id == transaction.id)
        .values(status="voided", voided_at=now)
    )
    await session.execute(
        delete(ExchangeRate).where(ExchangeRate.source_transaction_id == transaction.id)
    )
    linked_occurrence = (
        await session.execute(
            select(PlanOccurrence).where(
                PlanOccurrence.transaction_id == transaction.id
            )
        )
    ).scalar_one_or_none()
    if linked_occurrence is not None:
        today = datetime.now(UTC).astimezone(ZoneInfo(workspace.timezone)).date()
        linked_occurrence.status = (
            "overdue" if linked_occurrence.due_date < today else "planned"
        )
        linked_occurrence.transaction_id = None
        linked_occurrence.matched_at = None
        await reopen_plan_commitment(session, linked_occurrence)
    await session.commit()
    await session.refresh(transaction)
    return await transaction_out(
        session, transaction, visible_account_ids=visible_ids
    )


@router.get("/exchange-rates", response_model=list[ExchangeRateOut])
async def list_exchange_rates(
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    workspace = await primary_workspace(session, user.id)
    rates = list(
        (
            await session.execute(
                select(ExchangeRate)
                .join(Transaction, Transaction.id == ExchangeRate.source_transaction_id)
                .where(
                    Transaction.workspace_id == workspace.id,
                    Transaction.status == "posted",
                )
                .order_by(ExchangeRate.captured_at.desc(), ExchangeRate.id.desc())
            )
        ).scalars()
    )
    return [await rate_out(session, rate) for rate in rates]
