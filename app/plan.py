"""Private workspace Plan rules, recurrence materialization, and fulfillment."""

from datetime import UTC, date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.access import require_workspace_owner
from app.auth import require_user
from app.db import get_session
from app.ledger import (
    financial_times,
    require_asset_code,
    require_category,
    validate_amount,
)
from app.models import (
    Account,
    Asset,
    PlanOccurrence,
    PlanRule,
    Transaction,
    TransactionLeg,
    User,
    Workspace,
    utcnow,
)
from app.recurrence import horizon_date, occurrence_dates
from app.schemas import (
    AssetOut,
    PlanExecuteIn,
    PlanLinkTransactionIn,
    PlanOccurrenceOut,
    PeriodProposalOut,
    PlanRuleCreate,
    PlanRuleOut,
    PlanRulePatch,
    TransactionLinkPlanIn,
)
from app.tracker_service import build_period_proposal, sync_plan_fulfillment


router = APIRouter(tags=["plan"])
EXPENSE_KINDS = {"required_expense", "subscription", "other_expense"}
OPEN_STATUSES = {"planned", "overdue"}


def workspace_today(workspace: Workspace) -> date:
    return datetime.now(UTC).astimezone(ZoneInfo(workspace.timezone)).date()


async def plan_rule_out(session: AsyncSession, rule: PlanRule) -> PlanRuleOut:
    await session.refresh(rule, attribute_names=["asset"])
    return PlanRuleOut(
        id=rule.id,
        workspace_id=rule.workspace_id,
        created_by_user_id=rule.created_by_user_id,
        kind=rule.kind,
        name=rule.name,
        amount=rule.amount,
        asset=AssetOut.model_validate(rule.asset),
        recurrence=rule.recurrence,
        first_due_date=rule.first_due_date,
        category_id=rule.category_id,
        default_from_account_id=rule.default_from_account_id,
        default_to_account_id=rule.default_to_account_id,
        is_required=rule.is_required,
        is_active=rule.is_active,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


async def actual_amount(
    session: AsyncSession, transaction_id: int | None
) -> Decimal | None:
    if transaction_id is None:
        return None
    amounts = list(
        (
            await session.execute(
                select(TransactionLeg.amount).where(
                    TransactionLeg.transaction_id == transaction_id
                )
            )
        ).scalars()
    )
    if not amounts:
        return None
    negatives = [abs(Decimal(value)) for value in amounts if Decimal(value) < 0]
    positives = [Decimal(value) for value in amounts if Decimal(value) > 0]
    return (negatives or positives or [Decimal("0")])[0]


async def plan_occurrence_out(
    session: AsyncSession, occurrence: PlanOccurrence
) -> PlanOccurrenceOut:
    rule = await session.get(PlanRule, occurrence.plan_rule_id)
    assert rule is not None
    return PlanOccurrenceOut(
        id=occurrence.id,
        plan_rule_id=occurrence.plan_rule_id,
        due_date=occurrence.due_date,
        planned_amount=occurrence.planned_amount,
        status=occurrence.status,
        transaction_id=occurrence.transaction_id,
        actual_amount=await actual_amount(session, occurrence.transaction_id),
        matched_at=occurrence.matched_at,
        created_at=occurrence.created_at,
        rule=await plan_rule_out(session, rule),
    )


async def require_plan_account(
    session: AsyncSession,
    account_id: int | None,
    workspace_id: int,
    asset_id: int,
    *,
    label: str,
) -> Account | None:
    if account_id is None:
        return None
    account = await session.get(Account, account_id)
    if (
        account is None
        or account.workspace_id != workspace_id
        or account.archived_at is not None
    ):
        raise HTTPException(status_code=422, detail=f"Invalid {label} account")
    if account.asset_id != asset_id:
        raise HTTPException(status_code=422, detail=f"{label.title()} account asset does not match rule")
    await session.refresh(account, attribute_names=["asset"])
    return account


async def validate_rule_fields(
    session: AsyncSession,
    workspace_id: int,
    *,
    kind: str,
    asset: Asset,
    category_id: int | None,
    from_account_id: int | None,
    to_account_id: int | None,
) -> tuple[Account | None, Account | None]:
    if kind == "reserve_transfer" and category_id is not None:
        raise HTTPException(status_code=422, detail="Reserve transfers cannot have a category")
    if kind != "reserve_transfer":
        transaction_type = "income" if kind == "income" else "expense"
        await require_category(session, category_id, workspace_id, transaction_type)
    source = await require_plan_account(
        session, from_account_id, workspace_id, asset.id, label="source"
    )
    target = await require_plan_account(
        session, to_account_id, workspace_id, asset.id, label="target"
    )
    if kind == "income" and source is not None:
        raise HTTPException(status_code=422, detail="Income rules cannot have a source account")
    if kind in EXPENSE_KINDS and target is not None:
        raise HTTPException(status_code=422, detail="Expense rules cannot have a target account")
    if kind == "reserve_transfer" and source is not None and target is not None and source.id == target.id:
        raise HTTPException(status_code=422, detail="Reserve transfer accounts must differ")
    return source, target


async def materialize_rule(
    session: AsyncSession,
    rule: PlanRule,
    workspace: Workspace,
    *,
    reset_schedule: bool = False,
    update_amount: bool = False,
) -> None:
    if not rule.is_active:
        open_items = list(
            (
                await session.execute(
                    select(PlanOccurrence).where(
                        PlanOccurrence.plan_rule_id == rule.id,
                        PlanOccurrence.status.in_(OPEN_STATUSES),
                    )
                )
            ).scalars()
        )
        now = utcnow()
        for item in open_items:
            item.status = "skipped"
            item.matched_at = now
        return
    if reset_schedule:
        await session.execute(
            delete(PlanOccurrence).where(
                PlanOccurrence.plan_rule_id == rule.id,
                PlanOccurrence.status.in_(OPEN_STATUSES),
            )
        )
        await session.flush()
    today = workspace_today(workspace)
    existing = {
        item.due_date: item
        for item in (
            await session.execute(
                select(PlanOccurrence).where(PlanOccurrence.plan_rule_id == rule.id)
            )
        ).scalars()
    }
    if update_amount:
        for item in existing.values():
            if item.status in OPEN_STATUSES:
                item.planned_amount = rule.amount
    for due_date in occurrence_dates(
        rule.first_due_date, rule.recurrence, horizon_date(today)
    ):
        if due_date in existing:
            continue
        session.add(
            PlanOccurrence(
                plan_rule_id=rule.id,
                due_date=due_date,
                planned_amount=rule.amount,
                status="overdue" if due_date < today else "planned",
            )
        )
    for item in existing.values():
        if item.status == "planned" and item.due_date < today:
            item.status = "overdue"


async def owned_rule(
    session: AsyncSession, workspace_id: int, rule_id: int
) -> PlanRule:
    rule = await session.get(PlanRule, rule_id)
    if rule is None or rule.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Plan rule not found")
    return rule


@router.post(
    "/workspaces/{workspace_id}/plan-rules",
    response_model=PlanRuleOut,
    status_code=201,
)
async def create_plan_rule(
    workspace_id: int,
    body: PlanRuleCreate,
    workspace: Workspace = Depends(require_workspace_owner),
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    asset = await require_asset_code(session, body.asset_code)
    amount = validate_amount(body.amount, asset)
    await validate_rule_fields(
        session,
        workspace_id,
        kind=body.kind,
        asset=asset,
        category_id=body.category_id,
        from_account_id=body.default_from_account_id,
        to_account_id=body.default_to_account_id,
    )
    rule = PlanRule(
        workspace_id=workspace_id,
        created_by_user_id=user.id,
        kind=body.kind,
        name=" ".join(body.name.strip().split()),
        amount=amount,
        asset_id=asset.id,
        recurrence=body.recurrence,
        first_due_date=body.first_due_date,
        category_id=body.category_id,
        default_from_account_id=body.default_from_account_id,
        default_to_account_id=body.default_to_account_id,
        is_required=body.is_required,
        is_active=True,
    )
    session.add(rule)
    await session.flush()
    await materialize_rule(session, rule, workspace)
    await session.commit()
    await session.refresh(rule)
    return await plan_rule_out(session, rule)


@router.get("/workspaces/{workspace_id}/plan-rules", response_model=list[PlanRuleOut])
async def list_plan_rules(
    workspace_id: int,
    include_archived: bool = False,
    workspace: Workspace = Depends(require_workspace_owner),
    session: AsyncSession = Depends(get_session),
):
    statement = select(PlanRule).where(PlanRule.workspace_id == workspace_id)
    if not include_archived:
        statement = statement.where(PlanRule.is_active.is_(True))
    rules = list((await session.execute(statement.order_by(PlanRule.name))).scalars())
    for rule in rules:
        await materialize_rule(session, rule, workspace)
    await session.commit()
    return [await plan_rule_out(session, rule) for rule in rules]


@router.patch(
    "/workspaces/{workspace_id}/plan-rules/{rule_id}", response_model=PlanRuleOut
)
async def patch_plan_rule(
    workspace_id: int,
    rule_id: int,
    body: PlanRulePatch,
    workspace: Workspace = Depends(require_workspace_owner),
    session: AsyncSession = Depends(get_session),
):
    rule = await owned_rule(session, workspace_id, rule_id)
    if not rule.is_active:
        raise HTTPException(status_code=409, detail="Archived plan rule cannot be edited")
    asset = (
        await require_asset_code(session, body.asset_code)
        if body.asset_code is not None
        else await session.get(Asset, rule.asset_id)
    )
    assert asset is not None
    kind = body.kind or rule.kind
    category_id = body.category_id if "category_id" in body.model_fields_set else rule.category_id
    from_account_id = (
        body.default_from_account_id
        if "default_from_account_id" in body.model_fields_set
        else rule.default_from_account_id
    )
    to_account_id = (
        body.default_to_account_id
        if "default_to_account_id" in body.model_fields_set
        else rule.default_to_account_id
    )
    await validate_rule_fields(
        session,
        workspace_id,
        kind=kind,
        asset=asset,
        category_id=category_id,
        from_account_id=from_account_id,
        to_account_id=to_account_id,
    )
    old_recurrence, old_first = rule.recurrence, rule.first_due_date
    old_amount = rule.amount
    if body.kind is not None:
        rule.kind = body.kind
    if body.name is not None:
        rule.name = " ".join(body.name.strip().split())
    if body.amount is not None:
        rule.amount = validate_amount(body.amount, asset)
    elif body.asset_code is not None:
        rule.amount = validate_amount(rule.amount, asset)
    if body.asset_code is not None:
        rule.asset_id = asset.id
    if body.recurrence is not None:
        rule.recurrence = body.recurrence
    if body.first_due_date is not None:
        rule.first_due_date = body.first_due_date
    if "category_id" in body.model_fields_set:
        rule.category_id = body.category_id
    if "default_from_account_id" in body.model_fields_set:
        rule.default_from_account_id = body.default_from_account_id
    if "default_to_account_id" in body.model_fields_set:
        rule.default_to_account_id = body.default_to_account_id
    if body.is_required is not None:
        rule.is_required = body.is_required
    await session.flush()
    await materialize_rule(
        session,
        rule,
        workspace,
        reset_schedule=(old_recurrence, old_first) != (rule.recurrence, rule.first_due_date),
        update_amount=old_amount != rule.amount,
    )
    await session.commit()
    await session.refresh(rule)
    return await plan_rule_out(session, rule)


@router.post(
    "/workspaces/{workspace_id}/plan-rules/{rule_id}/archive",
    response_model=PlanRuleOut,
)
async def archive_plan_rule(
    workspace_id: int,
    rule_id: int,
    workspace: Workspace = Depends(require_workspace_owner),
    session: AsyncSession = Depends(get_session),
):
    rule = await owned_rule(session, workspace_id, rule_id)
    rule.is_active = False
    await materialize_rule(session, rule, workspace)
    await session.commit()
    await session.refresh(rule)
    return await plan_rule_out(session, rule)


async def materialize_workspace(
    session: AsyncSession, workspace: Workspace
) -> None:
    rules = list(
        (
            await session.execute(
                select(PlanRule).where(
                    PlanRule.workspace_id == workspace.id,
                    PlanRule.is_active.is_(True),
                )
            )
        ).scalars()
    )
    for rule in rules:
        await materialize_rule(session, rule, workspace)
    await session.commit()


@router.get(
    "/workspaces/{workspace_id}/plan-occurrences",
    response_model=list[PlanOccurrenceOut],
)
async def list_plan_occurrences(
    workspace_id: int,
    date_from: date | None = None,
    date_to: date | None = None,
    status: str | None = Query(default=None, pattern="^(planned|completed|skipped|overdue)$"),
    kind: str | None = None,
    workspace: Workspace = Depends(require_workspace_owner),
    session: AsyncSession = Depends(get_session),
):
    await materialize_workspace(session, workspace)
    statement = (
        select(PlanOccurrence)
        .join(PlanRule, PlanRule.id == PlanOccurrence.plan_rule_id)
        .where(PlanRule.workspace_id == workspace_id)
    )
    if date_from is not None:
        statement = statement.where(PlanOccurrence.due_date >= date_from)
    if date_to is not None:
        statement = statement.where(PlanOccurrence.due_date <= date_to)
    if status is not None:
        statement = statement.where(PlanOccurrence.status == status)
    if kind is not None:
        statement = statement.where(PlanRule.kind == kind)
    items = list(
        (
            await session.execute(
                statement.order_by(PlanOccurrence.due_date, PlanOccurrence.id)
            )
        ).scalars()
    )
    return [await plan_occurrence_out(session, item) for item in items]


async def owned_occurrence(
    session: AsyncSession, workspace_id: int, occurrence_id: int
) -> tuple[PlanOccurrence, PlanRule]:
    row = (
        await session.execute(
            select(PlanOccurrence, PlanRule)
            .join(PlanRule, PlanRule.id == PlanOccurrence.plan_rule_id)
            .where(
                PlanOccurrence.id == occurrence_id,
                PlanRule.workspace_id == workspace_id,
            )
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Plan occurrence not found")
    return row[0], row[1]


def require_open_occurrence(occurrence: PlanOccurrence) -> None:
    if occurrence.status not in OPEN_STATUSES:
        raise HTTPException(status_code=409, detail="Plan occurrence is already resolved")


async def execute_occurrence(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    occurrence: PlanOccurrence,
    rule: PlanRule,
    body: PlanExecuteIn,
) -> PlanOccurrenceOut:
    require_open_occurrence(occurrence)
    asset = await session.get(Asset, rule.asset_id)
    assert asset is not None
    amount = validate_amount(body.amount or occurrence.planned_amount, asset)
    occurred_at, local_date = financial_times(workspace, body.occurred_at, body.local_date)
    transaction = Transaction(
        workspace_id=workspace.id,
        created_by_user_id=user.id,
        type=(
            "income"
            if rule.kind == "income"
            else "transfer"
            if rule.kind == "reserve_transfer"
            else "expense"
        ),
        category_id=rule.category_id,
        counterparty=body.counterparty,
        note=body.note or rule.name,
        occurred_at=occurred_at,
        local_date=local_date,
        source="planned",
        status="posted",
    )
    if rule.kind == "income":
        account_id = body.account_id or body.to_account_id or rule.default_to_account_id
        account = await require_plan_account(
            session, account_id, workspace.id, asset.id, label="target"
        )
        if account is None:
            raise HTTPException(status_code=422, detail="Income target account is required")
        transaction.legs.append(
            TransactionLeg(account_id=account.id, asset_id=asset.id, amount=amount)
        )
    elif rule.kind in EXPENSE_KINDS:
        account_id = body.account_id or body.from_account_id or rule.default_from_account_id
        account = await require_plan_account(
            session, account_id, workspace.id, asset.id, label="source"
        )
        if account is None:
            raise HTTPException(status_code=422, detail="Expense source account is required")
        transaction.legs.append(
            TransactionLeg(account_id=account.id, asset_id=asset.id, amount=-amount)
        )
    else:
        source = await require_plan_account(
            session,
            body.from_account_id or rule.default_from_account_id,
            workspace.id,
            asset.id,
            label="source",
        )
        target = await require_plan_account(
            session,
            body.to_account_id or rule.default_to_account_id,
            workspace.id,
            asset.id,
            label="target",
        )
        if source is None or target is None:
            raise HTTPException(status_code=422, detail="Both reserve transfer accounts are required")
        if source.id == target.id:
            raise HTTPException(status_code=422, detail="Reserve transfer accounts must differ")
        transaction.category_id = None
        transaction.legs.extend(
            [
                TransactionLeg(account_id=source.id, asset_id=asset.id, amount=-amount),
                TransactionLeg(account_id=target.id, asset_id=asset.id, amount=amount),
            ]
        )
    session.add(transaction)
    await session.flush()
    occurrence.status = "completed"
    occurrence.transaction_id = transaction.id
    occurrence.matched_at = utcnow()
    await sync_plan_fulfillment(
        session, occurrence, transaction, body.base_amount
    )
    await session.commit()
    await session.refresh(occurrence)
    rendered = await plan_occurrence_out(session, occurrence)
    if rule.kind == "income":
        rendered.period_proposal = PeriodProposalOut.model_validate(
            await build_period_proposal(
                session,
                workspace,
                transaction,
                opening_occurrence_id=occurrence.id,
            )
        )
    return rendered


@router.post(
    "/workspaces/{workspace_id}/plan-occurrences/{occurrence_id}/pay",
    response_model=PlanOccurrenceOut,
)
async def pay_occurrence(
    workspace_id: int,
    occurrence_id: int,
    body: PlanExecuteIn,
    workspace: Workspace = Depends(require_workspace_owner),
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    occurrence, rule = await owned_occurrence(session, workspace_id, occurrence_id)
    if rule.kind == "income":
        raise HTTPException(status_code=422, detail="Use receive for income occurrences")
    return await execute_occurrence(session, workspace, user, occurrence, rule, body)


@router.post(
    "/workspaces/{workspace_id}/plan-occurrences/{occurrence_id}/receive",
    response_model=PlanOccurrenceOut,
)
async def receive_occurrence(
    workspace_id: int,
    occurrence_id: int,
    body: PlanExecuteIn,
    workspace: Workspace = Depends(require_workspace_owner),
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    occurrence, rule = await owned_occurrence(session, workspace_id, occurrence_id)
    if rule.kind != "income":
        raise HTTPException(status_code=422, detail="Only income occurrences can be received")
    return await execute_occurrence(session, workspace, user, occurrence, rule, body)


@router.post(
    "/workspaces/{workspace_id}/plan-occurrences/{occurrence_id}/skip",
    response_model=PlanOccurrenceOut,
)
async def skip_occurrence(
    workspace_id: int,
    occurrence_id: int,
    workspace: Workspace = Depends(require_workspace_owner),
    session: AsyncSession = Depends(get_session),
):
    del workspace
    occurrence, _ = await owned_occurrence(session, workspace_id, occurrence_id)
    require_open_occurrence(occurrence)
    occurrence.status = "skipped"
    occurrence.matched_at = utcnow()
    await session.commit()
    await session.refresh(occurrence)
    return await plan_occurrence_out(session, occurrence)


async def link_occurrence_transaction(
    session: AsyncSession,
    occurrence: PlanOccurrence,
    rule: PlanRule,
    transaction: Transaction,
    supplied_base_amount: Decimal | None = None,
) -> PlanOccurrenceOut:
    require_open_occurrence(occurrence)
    if (
        transaction.workspace_id != rule.workspace_id
        or transaction.status != "posted"
        or transaction.parent_transaction_id is not None
    ):
        raise HTTPException(status_code=422, detail="Transaction cannot fulfill this occurrence")
    expected_type = (
        "income"
        if rule.kind == "income"
        else "transfer"
        if rule.kind == "reserve_transfer"
        else "expense"
    )
    if transaction.type != expected_type:
        raise HTTPException(status_code=422, detail="Transaction type does not match plan occurrence")
    linked = (
        await session.execute(
            select(PlanOccurrence.id).where(
                PlanOccurrence.transaction_id == transaction.id
            )
        )
    ).scalar_one_or_none()
    if linked is not None:
        raise HTTPException(status_code=409, detail="Transaction is already linked to Plan")
    legs = list(
        (
            await session.execute(
                select(TransactionLeg).where(
                    TransactionLeg.transaction_id == transaction.id
                )
            )
        ).scalars()
    )
    if not legs or any(leg.asset_id != rule.asset_id for leg in legs):
        raise HTTPException(status_code=422, detail="Transaction asset does not match plan occurrence")
    occurrence.status = "completed"
    occurrence.transaction_id = transaction.id
    occurrence.matched_at = utcnow()
    await sync_plan_fulfillment(
        session, occurrence, transaction, supplied_base_amount
    )
    await session.commit()
    await session.refresh(occurrence)
    rendered = await plan_occurrence_out(session, occurrence)
    if rule.kind == "income":
        workspace = await session.get(Workspace, rule.workspace_id)
        assert workspace is not None
        rendered.period_proposal = PeriodProposalOut.model_validate(
            await build_period_proposal(
                session,
                workspace,
                transaction,
                opening_occurrence_id=occurrence.id,
            )
        )
    return rendered


@router.post(
    "/workspaces/{workspace_id}/plan-occurrences/{occurrence_id}/link-transaction",
    response_model=PlanOccurrenceOut,
)
async def link_transaction_to_occurrence(
    workspace_id: int,
    occurrence_id: int,
    body: PlanLinkTransactionIn,
    workspace: Workspace = Depends(require_workspace_owner),
    session: AsyncSession = Depends(get_session),
):
    del workspace
    occurrence, rule = await owned_occurrence(session, workspace_id, occurrence_id)
    transaction = await session.get(Transaction, body.transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return await link_occurrence_transaction(
        session, occurrence, rule, transaction, body.base_amount
    )


@router.post(
    "/transactions/{transaction_id}/link-plan", response_model=PlanOccurrenceOut
)
async def link_plan_from_transaction(
    transaction_id: int,
    body: TransactionLinkPlanIn,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    transaction = await session.get(Transaction, transaction_id)
    occurrence = await session.get(PlanOccurrence, body.occurrence_id)
    rule = await session.get(PlanRule, occurrence.plan_rule_id) if occurrence else None
    workspace = await session.get(Workspace, rule.workspace_id) if rule else None
    if (
        transaction is None
        or occurrence is None
        or rule is None
        or workspace is None
        or workspace.owner_user_id != user.id
    ):
        raise HTTPException(status_code=404, detail="Plan occurrence not found")
    return await link_occurrence_transaction(
        session, occurrence, rule, transaction, body.base_amount
    )
