"""Stable financial-date projections for the mobile Transactions feed."""

from base64 import b64decode, urlsafe_b64encode
from binascii import Error as Base64Error
from dataclasses import dataclass
from datetime import date, datetime
import json
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.access import visible_account_ids
from app.auth import primary_workspace, require_user
from app.db import get_session
from app.ledger import transaction_out
from app.models import PlanOccurrence, PlanRule, Transaction, TransactionLeg, User, utcnow
from app.periods import workspace_day_at, workspace_day_boundary
from app.plan import materialize_workspace, plan_occurrence_out
from app.schemas import (
    TransactionFeedPageOut,
    TransactionFeedPlannedDetailOut,
    TransactionFeedPlannedOut,
    TransactionFeedTransactionOut,
)
from app.transactions import _visible_transaction


router = APIRouter(prefix="/transaction-feed", tags=["transactions"])

FeedFilter = Literal["all", "income", "expense", "transfer", "planned"]
ALLOWED_QUERY_PARAMETERS = {"filter", "cursor", "limit"}
CURSOR_VERSION = 1


@dataclass(frozen=True)
class FeedCursor:
    financial_date: date
    sort_at: datetime
    kind_rank: int
    item_id: int


def validate_query_shape(request: Request) -> None:
    seen: set[str] = set()
    for key, _ in request.query_params.multi_items():
        if key not in ALLOWED_QUERY_PARAMETERS or key in seen:
            raise HTTPException(status_code=422, detail="Invalid feed query")
        seen.add(key)


def encode_cursor(cursor: FeedCursor) -> str:
    payload = json.dumps(
        {
            "v": CURSOR_VERSION,
            "d": cursor.financial_date.isoformat(),
            "s": cursor.sort_at.isoformat(timespec="microseconds"),
            "k": cursor.kind_rank,
            "i": cursor.item_id,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def decode_cursor(value: str) -> FeedCursor:
    try:
        padding = "=" * (-len(value) % 4)
        raw = b64decode(
            (value + padding).encode("ascii"),
            altchars=b"-_",
            validate=True,
        )
        if urlsafe_b64encode(raw).decode("ascii").rstrip("=") != value:
            raise ValueError
        payload = json.loads(raw.decode("ascii"))
        if type(payload) is not dict or set(payload) != {"v", "d", "s", "k", "i"}:
            raise ValueError
        if type(payload["v"]) is not int or payload["v"] != CURSOR_VERSION:
            raise ValueError
        if type(payload["d"]) is not str or type(payload["s"]) is not str:
            raise ValueError
        financial_date = date.fromisoformat(payload["d"])
        sort_at = datetime.fromisoformat(payload["s"])
        if sort_at.tzinfo is not None:
            raise ValueError
        kind_rank = payload["k"]
        item_id = payload["i"]
        if (
            type(kind_rank) is not int
            or kind_rank not in {0, 1}
            or type(item_id) is not int
            or item_id <= 0
        ):
            raise ValueError
    except (
        ValueError,
        TypeError,
        KeyError,
        UnicodeError,
        json.JSONDecodeError,
        Base64Error,
    ):
        raise HTTPException(status_code=422, detail="Invalid feed cursor")
    return FeedCursor(financial_date, sort_at, kind_rank, item_id)


def transaction_cursor(transaction: Transaction) -> FeedCursor:
    return FeedCursor(
        financial_date=transaction.local_date,
        sort_at=transaction.occurred_at,
        kind_rank=1,
        item_id=transaction.id,
    )


def planned_cursor(
    occurrence: PlanOccurrence,
    *,
    boundary: datetime,
) -> FeedCursor:
    return FeedCursor(
        financial_date=occurrence.due_date,
        sort_at=boundary,
        kind_rank=0,
        item_id=occurrence.id,
    )


def transaction_continuation(cursor: FeedCursor):
    return or_(
        Transaction.local_date < cursor.financial_date,
        and_(
            Transaction.local_date == cursor.financial_date,
            Transaction.occurred_at < cursor.sort_at,
        ),
        and_(
            Transaction.local_date == cursor.financial_date,
            Transaction.occurred_at == cursor.sort_at,
            1 < cursor.kind_rank,
        ),
        and_(
            Transaction.local_date == cursor.financial_date,
            Transaction.occurred_at == cursor.sort_at,
            cursor.kind_rank == 1,
            Transaction.id < cursor.item_id,
        ),
    )


def planned_continuation(cursor: FeedCursor, *, boundary: datetime):
    return or_(
        PlanOccurrence.due_date < cursor.financial_date,
        and_(
            PlanOccurrence.due_date == cursor.financial_date,
            boundary < cursor.sort_at,
        ),
        and_(
            PlanOccurrence.due_date == cursor.financial_date,
            boundary == cursor.sort_at,
            0 < cursor.kind_rank,
        ),
        and_(
            PlanOccurrence.due_date == cursor.financial_date,
            boundary == cursor.sort_at,
            cursor.kind_rank == 0,
            PlanOccurrence.id < cursor.item_id,
        ),
    )


def mobile_type(transaction_type: str) -> str:
    return "transfer" if transaction_type == "exchange" else transaction_type


async def transaction_projection(
    session: AsyncSession,
    transaction: Transaction,
    *,
    redacted_account_ids: set[int] | None,
) -> TransactionFeedTransactionOut:
    return TransactionFeedTransactionOut(
        kind="transaction",
        key=f"transaction:{transaction.id}",
        financial_date=transaction.local_date,
        mobile_type=mobile_type(transaction.type),
        transaction_type=transaction.type,
        transaction=await transaction_out(
            session,
            transaction,
            visible_account_ids=redacted_account_ids,
        ),
    )


async def planned_projection(
    session: AsyncSession,
    occurrence: PlanOccurrence,
    rule: PlanRule,
    *,
    today: date,
) -> TransactionFeedPlannedOut:
    status = (
        "overdue"
        if occurrence.status == "overdue" or occurrence.due_date < today
        else "required"
        if rule.is_required
        else "planned"
    )
    return TransactionFeedPlannedOut(
        kind="planned",
        key=f"planned:{occurrence.id}",
        financial_date=occurrence.due_date,
        mobile_type="planned",
        mobile_status=status,
        occurrence=await plan_occurrence_out(session, occurrence),
    )


@router.get(
    "",
    response_model=TransactionFeedPageOut,
    responses={422: {"description": "Invalid feed query or cursor"}},
)
async def list_transaction_feed(
    request: Request,
    filter: FeedFilter = "all",
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    validate_query_shape(request)
    decoded_cursor = decode_cursor(cursor) if cursor is not None else None
    workspace = await primary_workspace(session, user.id)
    clock = utcnow()
    today = workspace_day_at(workspace, clock)
    await materialize_workspace(session, workspace, today=today)
    visible_ids = await visible_account_ids(session, user.id)
    transactions: list[Transaction] = []
    if filter != "planned":
        statement = (
            select(Transaction)
            .outerjoin(TransactionLeg)
            .where(
                or_(
                    Transaction.workspace_id == workspace.id,
                    TransactionLeg.account_id.in_(visible_ids),
                    and_(
                        Transaction.created_by_user_id == user.id,
                        Transaction.status == "unassigned",
                        TransactionLeg.account_id.is_(None),
                    ),
                )
            )
        )
        if filter != "all":
            statement = statement.where(Transaction.type == filter)
        if decoded_cursor is not None:
            statement = statement.where(transaction_continuation(decoded_cursor))
        transactions = list(
            (
                await session.execute(
                    statement.distinct()
                    .order_by(
                        Transaction.local_date.desc(),
                        Transaction.occurred_at.desc(),
                        Transaction.id.desc(),
                    )
                    .limit(limit + 1)
                )
            ).scalars()
        )

    planned_rows: list[tuple[PlanOccurrence, PlanRule, datetime]] = []
    if filter in {"all", "planned"}:
        planned_statement = (
            select(PlanOccurrence, PlanRule)
            .join(PlanRule, PlanRule.id == PlanOccurrence.plan_rule_id)
            .where(
                PlanRule.workspace_id == workspace.id,
                PlanRule.is_active.is_(True),
                PlanOccurrence.status.in_({"planned", "overdue"}),
            )
        )
        if decoded_cursor is not None:
            cursor_boundary = workspace_day_boundary(
                workspace, decoded_cursor.financial_date
            )
            planned_statement = planned_statement.where(
                planned_continuation(decoded_cursor, boundary=cursor_boundary)
            )
        raw_planned = list(
            (
                await session.execute(
                    planned_statement.order_by(
                        PlanOccurrence.due_date.desc(),
                        PlanOccurrence.id.desc(),
                    ).limit(limit + 1)
                )
            ).all()
        )
        planned_rows = [
            (
                occurrence,
                rule,
                workspace_day_boundary(workspace, occurrence.due_date),
            )
            for occurrence, rule in raw_planned
        ]

    merged = [
        (transaction_cursor(item), "transaction", item, None)
        for item in transactions
    ] + [
        (
            planned_cursor(occurrence, boundary=boundary),
            "planned",
            occurrence,
            rule,
        )
        for occurrence, rule, boundary in planned_rows
    ]
    merged.sort(
        key=lambda row: (
            row[0].financial_date,
            row[0].sort_at,
            row[0].kind_rank,
            row[0].item_id,
        ),
        reverse=True,
    )
    has_more = len(merged) > limit
    page = merged[:limit]
    items = []
    for _, kind, item, rule in page:
        if kind == "transaction":
            items.append(
                await transaction_projection(
                    session,
                    item,
                    redacted_account_ids=(
                        None if item.workspace_id == workspace.id else visible_ids
                    ),
                )
            )
        else:
            items.append(
                await planned_projection(
                    session,
                    item,
                    rule,
                    today=today,
                )
            )
    return TransactionFeedPageOut(
        items=items,
        next_cursor=(
            encode_cursor(page[-1][0])
            if has_more and page
            else None
        ),
    )


@router.get(
    "/transaction/{transaction_id}",
    response_model=TransactionFeedTransactionOut,
    responses={
        404: {"description": "Feed item not found"},
        422: {"description": "Invalid transaction ID"},
    },
)
async def get_transaction_feed_item(
    transaction_id: Annotated[int, Path(gt=0)],
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        transaction, visible_ids = await _visible_transaction(
            session, transaction_id, user
        )
    except HTTPException as error:
        if error.status_code == 404:
            raise HTTPException(status_code=404, detail="Feed item not found")
        raise
    return await transaction_projection(
        session,
        transaction,
        redacted_account_ids=visible_ids,
    )


@router.get(
    "/planned/{occurrence_id}",
    response_model=TransactionFeedPlannedDetailOut,
    responses={
        404: {"description": "Feed item not found"},
        422: {"description": "Invalid occurrence ID"},
    },
)
async def get_planned_feed_item(
    occurrence_id: Annotated[int, Path(gt=0)],
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    workspace = await primary_workspace(session, user.id)
    clock = utcnow()
    today = workspace_day_at(workspace, clock)
    await materialize_workspace(session, workspace, today=today)
    row = (
        await session.execute(
            select(PlanOccurrence, PlanRule)
            .join(PlanRule, PlanRule.id == PlanOccurrence.plan_rule_id)
            .where(
                PlanOccurrence.id == occurrence_id,
                PlanRule.workspace_id == workspace.id,
                PlanRule.is_active.is_(True),
                PlanOccurrence.status.in_({"planned", "overdue"}),
            )
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Feed item not found")
    projected = await planned_projection(session, row[0], row[1], today=today)
    return TransactionFeedPlannedDetailOut(
        **projected.model_dump(),
        available_actions=("edit_rule", "skip", "link_transaction"),
    )
