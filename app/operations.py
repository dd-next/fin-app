"""Action-first Operations commands and persistent creator-scoped Undo."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_user
from app.access import require_account_action, visible_account_ids
from app.db import get_session
from app.ledger import transaction_out
from app.models import (
    OperationsUndoState,
    Transaction,
    TransactionLeg,
    User,
    Workspace,
    utcnow,
)
from app.operations_undo import (
    advance_undo_cursors,
    consume_undo_cursors,
    root_account_ids,
)
from app.schemas import (
    ExchangeIn,
    OperationsSingleIn,
    OperationsUndoIn,
    SingleTransactionIn,
    TransactionOut,
    TransferIn,
)
from app.transactions import (
    _create_exchange,
    _create_single,
    _create_transfer,
    _soft_delete_transaction,
)


router = APIRouter(prefix="/operations", tags=["operations"])


async def operations_transaction_out(
    session: AsyncSession, transaction: Transaction, user: User
) -> TransactionOut:
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


def single_command(body: OperationsSingleIn) -> SingleTransactionIn:
    return SingleTransactionIn(**body.model_dump(), asset_code=None)


async def record_undo_candidate(
    session: AsyncSession, transaction: Transaction, user: User
) -> None:
    """Advance each root-leg account cursor in the operation's DB transaction."""
    await advance_undo_cursors(
        session,
        user_id=user.id,
        transaction_id=transaction.id,
        account_ids=await root_account_ids(session, transaction.id),
    )


async def commit_operation(
    session: AsyncSession, transaction: Transaction, user: User
) -> Transaction:
    await record_undo_candidate(session, transaction, user)
    await session.commit()
    await session.refresh(transaction)
    return transaction


def undo_action(transaction_type: str) -> str:
    return {
        "expense": "expense",
        "income": "income",
        "transfer": "edit",
        "exchange": "edit",
        "adjustment": "owner",
    }[transaction_type]


async def require_undo_rights(
    session: AsyncSession, transaction: Transaction, user: User
) -> None:
    roots_and_children = [transaction]
    roots_and_children.extend(
        list(
            (
                await session.execute(
                    select(Transaction).where(
                        Transaction.parent_transaction_id == transaction.id
                    )
                )
            ).scalars()
        )
    )
    for item in roots_and_children:
        action = undo_action(item.type)
        legs = list(
            (
                await session.execute(
                    select(TransactionLeg).where(
                        TransactionLeg.transaction_id == item.id
                    )
                )
            ).scalars()
        )
        for leg in legs:
            if leg.account_id is None:
                raise HTTPException(status_code=409, detail="Operation cannot be undone")
            await require_account_action(
                session,
                leg.account_id,
                user.id,
                action,
                allow_archived=True,
            )


async def undo_candidate(
    session: AsyncSession,
    account_id: int,
    user: User,
    *,
    required: bool,
) -> Transaction | None:
    await require_account_action(
        session, account_id, user.id, "view", allow_archived=True
    )
    state = (
        await session.execute(
            select(OperationsUndoState).where(
                OperationsUndoState.user_id == user.id,
                OperationsUndoState.account_id == account_id,
            )
        )
    ).scalar_one_or_none()
    transaction = (
        await session.get(Transaction, state.cursor_transaction_id)
        if state is not None and state.consumed_at is None
        else None
    )
    valid = bool(
        transaction is not None
        and transaction.parent_transaction_id is None
        and transaction.origin == "operations"
        and transaction.status == "posted"
        and transaction.created_by_user_id == user.id
        and account_id in await root_account_ids(session, transaction.id)
    )
    if not valid:
        if required:
            raise HTTPException(status_code=409, detail="No operation to undo")
        return None
    assert transaction is not None
    await require_undo_rights(session, transaction, user)
    return transaction


async def consume_undo_candidate(
    session: AsyncSession, transaction: Transaction, user: User
) -> None:
    """Consume this root on every leg unless an even newer cursor exists."""
    await consume_undo_cursors(
        session,
        user_id=user.id,
        transaction_id=transaction.id,
        account_ids=await root_account_ids(session, transaction.id),
    )


async def claim_undo_candidate(
    session: AsyncSession,
    account_id: int,
    transaction_id: int,
    user: User,
) -> None:
    """Optimistically lock exactly the root that the user confirmed."""
    result = await session.execute(
        update(OperationsUndoState)
        .where(
            OperationsUndoState.user_id == user.id,
            OperationsUndoState.account_id == account_id,
            OperationsUndoState.cursor_transaction_id == transaction_id,
            OperationsUndoState.consumed_at.is_(None),
        )
        .values(updated_at=utcnow())
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        raise HTTPException(status_code=409, detail="Undo candidate changed")


@router.post("/spend", response_model=TransactionOut, status_code=201)
async def spend(
    body: OperationsSingleIn,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    transaction = await _create_single(
        session,
        user,
        "expense",
        single_command(body),
        origin="operations",
        commit=False,
    )
    transaction = await commit_operation(session, transaction, user)
    return await operations_transaction_out(session, transaction, user)


@router.post("/add-funds", response_model=TransactionOut, status_code=201)
async def add_funds(
    body: OperationsSingleIn,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    transaction = await _create_single(
        session,
        user,
        "income",
        single_command(body),
        origin="operations",
        commit=False,
    )
    transaction = await commit_operation(session, transaction, user)
    return await operations_transaction_out(session, transaction, user)


@router.post("/transfer", response_model=TransactionOut, status_code=201)
async def transfer(
    body: TransferIn,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    transaction = await _create_transfer(
        session, user, body, origin="operations", commit=False
    )
    transaction = await commit_operation(session, transaction, user)
    return await operations_transaction_out(session, transaction, user)


@router.post("/exchange", response_model=TransactionOut, status_code=201)
async def exchange(
    body: ExchangeIn,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    transaction = await _create_exchange(
        session, user, body, origin="operations", commit=False
    )
    transaction = await commit_operation(session, transaction, user)
    return await operations_transaction_out(session, transaction, user)


@router.get(
    "/accounts/{account_id}/undo",
    response_model=TransactionOut | None,
)
async def get_undo_candidate(
    account_id: int,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    transaction = await undo_candidate(
        session, account_id, user, required=False
    )
    if transaction is None:
        return None
    return await operations_transaction_out(session, transaction, user)


@router.post(
    "/accounts/{account_id}/undo",
    response_model=TransactionOut,
)
async def undo(
    account_id: int,
    body: OperationsUndoIn,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    await require_account_action(
        session, account_id, user.id, "view", allow_archived=True
    )
    await claim_undo_candidate(
        session, account_id, body.transaction_id, user
    )
    transaction = await undo_candidate(session, account_id, user, required=True)
    assert transaction is not None
    if transaction.id != body.transaction_id:
        raise HTTPException(status_code=409, detail="Undo candidate changed")
    await _soft_delete_transaction(
        session,
        transaction,
        user,
        confirmed=body.confirm_ended_period,
    )
    await consume_undo_candidate(session, transaction, user)
    await session.commit()
    await session.refresh(transaction)
    return await operations_transaction_out(session, transaction, user)
