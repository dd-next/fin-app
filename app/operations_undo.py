"""Atomic cursor maintenance for creator-scoped Operations Undo."""

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OperationsUndoState, TransactionLeg, utcnow


async def root_account_ids(
    session: AsyncSession, transaction_id: int
) -> set[int]:
    return set(
        (
            await session.execute(
                select(TransactionLeg.account_id).where(
                    TransactionLeg.transaction_id == transaction_id,
                    TransactionLeg.account_id.is_not(None),
                )
            )
        ).scalars()
    )


async def advance_undo_cursors(
    session: AsyncSession,
    *,
    user_id: int,
    transaction_id: int,
    account_ids: Iterable[int],
) -> None:
    """Make a root the candidate unless an even newer cursor already exists."""
    now = utcnow()
    for account_id in set(account_ids):
        statement = sqlite_insert(OperationsUndoState).values(
            user_id=user_id,
            account_id=account_id,
            cursor_transaction_id=transaction_id,
            created_at=now,
            updated_at=now,
            consumed_at=None,
        )
        statement = statement.on_conflict_do_update(
            index_elements=["user_id", "account_id"],
            set_={
                "cursor_transaction_id": transaction_id,
                "updated_at": now,
                "consumed_at": None,
            },
            where=OperationsUndoState.cursor_transaction_id <= transaction_id,
        )
        await session.execute(statement)


async def consume_undo_cursors(
    session: AsyncSession,
    *,
    user_id: int,
    transaction_id: int,
    account_ids: Iterable[int],
) -> None:
    """Consume a root without overwriting an even newer account cursor."""
    now = utcnow()
    for account_id in set(account_ids):
        statement = sqlite_insert(OperationsUndoState).values(
            user_id=user_id,
            account_id=account_id,
            cursor_transaction_id=transaction_id,
            created_at=now,
            updated_at=now,
            consumed_at=now,
        )
        statement = statement.on_conflict_do_update(
            index_elements=["user_id", "account_id"],
            set_={
                "cursor_transaction_id": transaction_id,
                "updated_at": now,
                "consumed_at": now,
            },
            where=OperationsUndoState.cursor_transaction_id <= transaction_id,
        )
        await session.execute(statement)


async def reindex_operations_root(
    session: AsyncSession,
    *,
    user_id: int,
    transaction_id: int,
    previous_account_ids: Iterable[int],
) -> None:
    """Move a corrected root's candidate and consume every removed account."""
    previous = set(previous_account_ids)
    current = await root_account_ids(session, transaction_id)
    await advance_undo_cursors(
        session,
        user_id=user_id,
        transaction_id=transaction_id,
        account_ids=current,
    )
    await consume_undo_cursors(
        session,
        user_id=user_id,
        transaction_id=transaction_id,
        account_ids=previous - current,
    )
