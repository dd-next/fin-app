"""FastAPI app + routes."""

from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import inspect as sa_inspect, text

from app import budget, export, sheets
from app.auth import router as auth_router
from app.access import require_workspace_access
from app.workspaces import router as workspaces_router
from app.db import engine, get_session
from app.models import Base, Operation, Period, RebaseEvent, Workspace
from app.schemas import (
    BudgetOut,
    OperationIn,
    OperationOut,
    OperationWithBudget,
    PeriodIn,
    PeriodOut,
    PeriodPatch,
    PeriodWithBudget,
    SavingsDecisionIn,
    SavingsPromptOut,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Zero-setup local dev: ensure tables exist (Alembic is the canonical
    # migration path; create_all is idempotent and a no-op after migrating).
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # create_all never ALTERs an existing table, so columns added after
        # a DB was created need to be patched in here (mirrors Alembic
        # revisions 0002/0003; idempotent).
        async def missing(table: str, column: str) -> bool:
            cols = await conn.run_sync(
                lambda sync_conn: [
                    c["name"] for c in sa_inspect(sync_conn).get_columns(table)
                ]
            )
            return column not in cols

        tables = await conn.run_sync(lambda sync_conn: sa_inspect(sync_conn).get_table_names())
        operation_table = "operation" if "operation" in tables else "expense"
        if await missing(operation_table, "kind"):
            await conn.execute(text(
                f"ALTER TABLE {operation_table} ADD COLUMN kind VARCHAR(10) "
                "NOT NULL DEFAULT 'expense'"
            ))
        if await missing("period", "prompt_ack_date"):
            await conn.execute(text(
                "ALTER TABLE period ADD COLUMN prompt_ack_date DATE"
            ))
        # Fresh databases need a default personal workspace before a period can
        # reference it. Existing databases are upgraded canonically by Alembic.
        await conn.execute(text(
            "INSERT INTO workspace (id, name, kind, timezone, created_at) "
            "SELECT 1, 'Personal', 'personal', 'Asia/Ho_Chi_Minh', CURRENT_TIMESTAMP "
            "WHERE NOT EXISTS (SELECT 1 FROM workspace WHERE id = 1)"
        ))
    yield


app = FastAPI(title="FinApp", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(workspaces_router)

# Telegram Mini App gate on all data endpoints (no-op unless
# TELEGRAM_AUTH_ENABLED). /health and the static frontend stay open.
ACCESS = Depends(require_workspace_access)


async def _active_period(
    session: AsyncSession, workspace_id: int = 1
) -> Period | None:
    """Current period for a workspace, or its newest period when none is live."""
    result = await session.execute(
        select(Period)
        .where(Period.workspace_id == workspace_id)
        .order_by(Period.start_date.desc(), Period.id.desc())
    )
    periods = list(result.scalars())
    today = date.today()
    return next(
        (p for p in periods if p.start_date <= today <= p.end_date),
        periods[0] if periods else None,
    )


async def _require_period(
    session: AsyncSession, period_id: int | None = None, workspace_id: int = 1
) -> Period:
    period = (
        await session.get(Period, period_id)
        if period_id is not None
        else await _active_period(session, workspace_id)
    )
    if period is not None and period.workspace_id != workspace_id:
        period = None
    if period is None:
        raise HTTPException(status_code=404, detail="No active period")
    return period


async def _assert_no_period_overlap(
    session: AsyncSession,
    workspace_id: int,
    start_date: date,
    end_date: date,
    exclude_period_id: int | None = None,
) -> None:
    statement = select(Period.id).where(
        Period.workspace_id == workspace_id,
        Period.start_date <= end_date,
        Period.end_date >= start_date,
    )
    if exclude_period_id is not None:
        statement = statement.where(Period.id != exclude_period_id)
    if (await session.execute(statement.limit(1))).scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409,
            detail="Period dates overlap another period in this workspace",
        )


async def _dated_amounts(
    session: AsyncSession, period: Period
) -> list[budget.DatedAmount]:
    result = await session.execute(
        select(Operation.occurred_on, Operation.amount, Operation.kind).where(
            Operation.period_id == period.id
        )
    )
    # Incomes are negative spending in the replay (see app/budget.py).
    return [
        (occurred_on, -amount if kind == "income" else amount)
        for occurred_on, amount, kind in result.all()
    ]


async def _rebase_days(session: AsyncSession, period: Period) -> list[date]:
    result = await session.execute(
        select(RebaseEvent.day).where(RebaseEvent.period_id == period.id)
    )
    return list(result.scalars())


async def _budget_for(
    session: AsyncSession, period: Period, pending: Decimal | None = None
) -> BudgetOut:
    dated = await _dated_amounts(session, period)
    rebases = await _rebase_days(session, period)
    summary = budget.compute_budget(
        period.total_amount, period.start_date, period.end_date, dated,
        rebase_days=rebases,
    )
    preview = None
    if pending is not None:
        preview = budget.preview_after(summary.per_day_today, pending)
    return BudgetOut(
        days_total=summary.days_total,
        days_remaining=summary.days_remaining,
        spent_total=summary.spent_total,
        remaining_money=summary.remaining_money,
        daily_base=summary.daily_base,
        budget_today=summary.budget_today,
        spent_today=summary.spent_today,
        per_day_today=summary.per_day_today,
        next_daily=summary.next_daily,
        preview_after=preview,
    )


async def _operation_snapshot(
    session: AsyncSession, period: Period
) -> list[export.OperationRow]:
    result = await session.execute(
        select(Operation).where(Operation.period_id == period.id)
    )
    return [
        export.OperationRow(
            created_at=o.created_at, amount=o.amount, comment=o.comment,
            kind=o.kind, occurred_on=o.occurred_on,
        )
        for o in result.scalars()
    ]


async def _queue_sheets_sync(
    background_tasks: BackgroundTasks, session: AsyncSession, period: Period
) -> None:
    """After a successful mutation: schedule a best-effort full re-sync.

    The snapshot is captured now (plain values) because the DB session is
    gone by the time the task runs, after the response is sent."""
    if not sheets.enabled():
        return
    rows = await _operation_snapshot(session, period)
    rebases = await _rebase_days(session, period)
    background_tasks.add_task(
        sheets.sync_safe,
        period.total_amount,
        period.start_date,
        period.end_date,
        rows,
        rebases,
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


async def _period_with_budget(
    session: AsyncSession, period: Period
) -> PeriodWithBudget:
    return PeriodWithBudget(
        period=PeriodOut.model_validate(period),
        budget=await _budget_for(session, period),
    )


@app.post("/period", response_model=PeriodWithBudget, dependencies=[ACCESS])
@app.post("/periods", response_model=PeriodWithBudget, dependencies=[ACCESS])
async def set_period(
    body: PeriodIn,
    background_tasks: BackgroundTasks,
    workspace_id: int = 1,
    session: AsyncSession = Depends(get_session),
):
    await _assert_no_period_overlap(
        session, workspace_id, body.start_date, body.end_date
    )
    period = Period(
        workspace_id=workspace_id,
        total_amount=body.total_amount,
        start_date=body.start_date,
        end_date=body.end_date,
    )
    session.add(period)
    await session.commit()
    await session.refresh(period)
    await _queue_sheets_sync(background_tasks, session, period)
    return await _period_with_budget(session, period)


@app.get("/periods", response_model=list[PeriodWithBudget], dependencies=[ACCESS])
async def list_periods(
    workspace_id: int = 1, session: AsyncSession = Depends(get_session)
):
    result = await session.execute(
        select(Period)
        .where(Period.workspace_id == workspace_id)
        .order_by(Period.start_date.desc(), Period.id.desc())
    )
    return [await _period_with_budget(session, p) for p in result.scalars()]


@app.get(
    "/periods/{period_id}", response_model=PeriodWithBudget, dependencies=[ACCESS]
)
async def get_period_by_id(
    period_id: int,
    workspace_id: int = 1,
    session: AsyncSession = Depends(get_session),
):
    return await _period_with_budget(
        session, await _require_period(session, period_id, workspace_id)
    )


@app.patch(
    "/periods/{period_id}", response_model=PeriodWithBudget, dependencies=[ACCESS]
)
async def update_period(
    period_id: int,
    body: PeriodPatch,
    background_tasks: BackgroundTasks,
    workspace_id: int = 1,
    confirm_ended: bool = False,
    session: AsyncSession = Depends(get_session),
):
    period = await _require_period(session, period_id, workspace_id)
    if period.status == "ended" and not confirm_ended:
        raise HTTPException(
            status_code=409,
            detail="Editing an ended period requires confirm_ended=true",
        )
    start_date = body.start_date or period.start_date
    end_date = body.end_date or period.end_date
    if end_date < start_date:
        raise HTTPException(status_code=422, detail="end_date must be >= start_date")
    await _assert_no_period_overlap(
        session,
        workspace_id,
        start_date,
        end_date,
        exclude_period_id=period.id,
    )
    if body.total_amount is not None:
        period.total_amount = body.total_amount
    period.start_date = start_date
    period.end_date = end_date
    await session.commit()
    await session.refresh(period)
    await _queue_sheets_sync(background_tasks, session, period)
    return await _period_with_budget(session, period)


@app.get("/period", response_model=PeriodWithBudget, dependencies=[ACCESS])
async def get_period(
    period_id: int | None = None,
    workspace_id: int = 1,
    session: AsyncSession = Depends(get_session),
):
    period = await _require_period(session, period_id, workspace_id)
    return await _period_with_budget(session, period)


@app.get("/budget", response_model=BudgetOut, response_model_exclude_none=True,
         dependencies=[ACCESS])
async def get_budget(
    pending: Decimal | None = None,
    period_id: int | None = None,
    workspace_id: int = 1,
    session: AsyncSession = Depends(get_session),
):
    period = await _require_period(session, period_id, workspace_id)
    return await _budget_for(session, period, pending)


@app.get("/operations", response_model=list[OperationOut], dependencies=[ACCESS])
@app.get(
    "/periods/{period_id}/operations",
    response_model=list[OperationOut],
    dependencies=[ACCESS],
)
async def list_operations(
    period_id: int | None = None,
    workspace_id: int = 1,
    session: AsyncSession = Depends(get_session),
):
    period = await _require_period(session, period_id, workspace_id)
    result = await session.execute(
        select(Operation)
        .where(Operation.period_id == period.id)
        .order_by(Operation.created_at.desc(), Operation.id.desc())
    )
    return [OperationOut.model_validate(o) for o in result.scalars()]


@app.post("/operations", response_model=OperationWithBudget, dependencies=[ACCESS])
@app.post(
    "/periods/{period_id}/operations",
    response_model=OperationWithBudget,
    dependencies=[ACCESS],
)
async def add_operation(
    body: OperationIn,
    background_tasks: BackgroundTasks,
    period_id: int | None = None,
    workspace_id: int = 1,
    session: AsyncSession = Depends(get_session),
):
    period = await _require_period(session, period_id, workspace_id)
    occurred_on = body.occurred_on or date.today()
    if not period.start_date <= occurred_on <= period.end_date:
        raise HTTPException(
            status_code=422,
            detail="occurred_on must be inside the selected period",
        )
    operation = Operation(
        period_id=period.id, amount=body.amount, kind=body.kind,
        comment=body.comment, occurred_on=occurred_on,
    )
    session.add(operation)
    await session.commit()
    await session.refresh(operation)
    await _queue_sheets_sync(background_tasks, session, period)
    return OperationWithBudget(
        operation=OperationOut.model_validate(operation),
        budget=await _budget_for(session, period),
    )


@app.delete("/operations/{operation_id}", response_model=BudgetOut,
            dependencies=[ACCESS])
@app.delete(
    "/periods/{period_id}/operations/{operation_id}",
    response_model=BudgetOut,
    dependencies=[ACCESS],
)
async def delete_operation(
    operation_id: int,
    background_tasks: BackgroundTasks,
    period_id: int | None = None,
    workspace_id: int = 1,
    session: AsyncSession = Depends(get_session),
):
    operation = await session.get(Operation, operation_id)
    if operation is None or (period_id is not None and operation.period_id != period_id):
        raise HTTPException(status_code=404, detail="Operation not found")
    period = await session.get(Period, operation.period_id)
    if period is None or period.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Operation not found")
    await session.delete(operation)
    await session.commit()
    await _queue_sheets_sync(background_tasks, session, period)
    # Everything is re-derived from (period + operations), so deletion can
    # never corrupt the numbers.
    return await _budget_for(session, period)


@app.get("/savings-prompt", response_model=SavingsPromptOut,
         response_model_exclude_none=True, dependencies=[ACCESS])
async def savings_prompt(
    workspace_id: int = 1, session: AsyncSession = Depends(get_session)
):
    """Next-day savings decision: shown once per calendar day, when yesterday
    (or earlier untouched days) left a positive carry-over."""
    period = await _active_period(session, workspace_id)
    today = date.today()
    if period is None or not (period.start_date < today <= period.end_date):
        return SavingsPromptOut(show=False)
    if period.prompt_ack_date is not None and period.prompt_ack_date >= today:
        return SavingsPromptOut(show=False)

    dated = await _dated_amounts(session, period)
    rebases = await _rebase_days(session, period)
    current = budget.compute_budget(
        period.total_amount, period.start_date, period.end_date, dated,
        rebase_days=rebases,
    )
    saved = current.budget_today - current.daily_base  # the carry-over
    if saved <= 0:
        return SavingsPromptOut(show=False)
    respread = budget.compute_budget(
        period.total_amount, period.start_date, period.end_date, dated,
        rebase_days=[*rebases, today],
    )
    return SavingsPromptOut(
        show=True,
        saved=saved,
        spend_today_value=current.budget_today,
        increase_daily_value=respread.daily_base,
    )


@app.post("/savings-decision", dependencies=[ACCESS])
async def savings_decision(
    body: SavingsDecisionIn,
    background_tasks: BackgroundTasks,
    workspace_id: int = 1,
    session: AsyncSession = Depends(get_session),
):
    """Persist the user's choice. "spend_today" keeps the default carry-over
    math and only acknowledges the prompt; "increase_daily" also records a
    rebase event for today, so the replay re-spreads deterministically."""
    period = await _require_period(session, workspace_id=workspace_id)
    today = date.today()
    if body.choice == "increase_daily":
        session.add(RebaseEvent(period_id=period.id, day=today))
    period.prompt_ack_date = today
    await session.commit()
    await _queue_sheets_sync(background_tasks, session, period)
    return {"status": "ok", "budget": await _budget_for(session, period)}


@app.post("/sheets/sync", dependencies=[ACCESS])
async def sheets_sync(
    workspace_id: int = 1, session: AsyncSession = Depends(get_session)
):
    """Manual "sync now": same full re-sync, run in a threadpool
    (gspread is synchronous). Returns ok/failed instead of raising."""
    if not sheets.enabled():
        return {"status": "disabled"}
    period = await _require_period(session, workspace_id=workspace_id)
    rows = await _operation_snapshot(session, period)
    rebases = await _rebase_days(session, period)
    try:
        await run_in_threadpool(
            sheets.sync_now,
            period.total_amount,
            period.start_date,
            period.end_date,
            rows,
            rebases,
        )
    except Exception:
        return {"status": "failed"}
    return {"status": "ok"}


@app.get("/export.xlsx", dependencies=[ACCESS])
@app.get("/periods/{period_id}/export.xlsx", dependencies=[ACCESS])
async def export_xlsx(
    period_id: int | None = None,
    workspace_id: int = 1,
    session: AsyncSession = Depends(get_session),
):
    period = await _require_period(session, period_id, workspace_id)
    rows = await _operation_snapshot(session, period)
    rebases = await _rebase_days(session, period)
    data = export.build_workbook(
        period.total_amount, period.start_date, period.end_date, rows,
        rebase_days=rebases,
    )
    return StreamingResponse(
        BytesIO(data),
        media_type=export.CONTENT_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{export.FILENAME}"'},
    )


# Frontend: static SPA served at /. Mounted last so API routes take precedence.
_static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=_static_dir), name="static")
app.mount("/", StaticFiles(directory=_static_dir, html=True), name="root")
