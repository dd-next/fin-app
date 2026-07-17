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
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import inspect as sa_inspect, text

from app import budget, export, sheets
from app.telegram_auth import require_telegram_auth
from app.db import engine, get_session
from app.models import Base, Operation, Period, RebaseEvent, Workspace
from app.schemas import (
    BudgetOut,
    OperationIn,
    OperationOut,
    OperationWithBudget,
    PeriodIn,
    PeriodOut,
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

# Telegram Mini App gate on all data endpoints (no-op unless
# TELEGRAM_AUTH_ENABLED). /health and the static frontend stay open.
AUTH = Depends(require_telegram_auth)


async def _active_period(session: AsyncSession) -> Period | None:
    result = await session.execute(select(Period).order_by(Period.id.desc()).limit(1))
    return result.scalar_one_or_none()


async def _require_period(session: AsyncSession) -> Period:
    period = await _active_period(session)
    if period is None:
        raise HTTPException(status_code=404, detail="No active period")
    return period


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


@app.post("/period", response_model=PeriodWithBudget, dependencies=[AUTH])
async def set_period(
    body: PeriodIn,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    # Single active period for the MVP: replacing it drops the old one
    # (and, via cascade, its expenses).
    await session.execute(delete(Period))
    period = Period(
        workspace_id=1,
        total_amount=body.total_amount,
        start_date=body.start_date,
        end_date=body.end_date,
    )
    session.add(period)
    await session.commit()
    await session.refresh(period)
    await _queue_sheets_sync(background_tasks, session, period)
    return PeriodWithBudget(
        period=PeriodOut.model_validate(period),
        budget=await _budget_for(session, period),
    )


@app.get("/period", response_model=PeriodWithBudget, dependencies=[AUTH])
async def get_period(session: AsyncSession = Depends(get_session)):
    period = await _require_period(session)
    return PeriodWithBudget(
        period=PeriodOut.model_validate(period),
        budget=await _budget_for(session, period),
    )


@app.get("/budget", response_model=BudgetOut, response_model_exclude_none=True,
         dependencies=[AUTH])
async def get_budget(
    pending: Decimal | None = None, session: AsyncSession = Depends(get_session)
):
    period = await _require_period(session)
    return await _budget_for(session, period, pending)


@app.get("/operations", response_model=list[OperationOut], dependencies=[AUTH])
async def list_operations(session: AsyncSession = Depends(get_session)):
    period = await _require_period(session)
    result = await session.execute(
        select(Operation)
        .where(Operation.period_id == period.id)
        .order_by(Operation.created_at.desc(), Operation.id.desc())
    )
    return [OperationOut.model_validate(o) for o in result.scalars()]


@app.post("/operations", response_model=OperationWithBudget, dependencies=[AUTH])
async def add_operation(
    body: OperationIn,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    period = await _require_period(session)
    operation = Operation(
        period_id=period.id, amount=body.amount, kind=body.kind,
        comment=body.comment, occurred_on=date.today(),
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
            dependencies=[AUTH])
async def delete_operation(
    operation_id: int,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    operation = await session.get(Operation, operation_id)
    if operation is None:
        raise HTTPException(status_code=404, detail="Operation not found")
    period = await session.get(Period, operation.period_id)
    await session.delete(operation)
    await session.commit()
    await _queue_sheets_sync(background_tasks, session, period)
    # Everything is re-derived from (period + operations), so deletion can
    # never corrupt the numbers.
    return await _budget_for(session, period)


@app.get("/savings-prompt", response_model=SavingsPromptOut,
         response_model_exclude_none=True, dependencies=[AUTH])
async def savings_prompt(session: AsyncSession = Depends(get_session)):
    """Next-day savings decision: shown once per calendar day, when yesterday
    (or earlier untouched days) left a positive carry-over."""
    period = await _active_period(session)
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


@app.post("/savings-decision", dependencies=[AUTH])
async def savings_decision(
    body: SavingsDecisionIn,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """Persist the user's choice. "spend_today" keeps the default carry-over
    math and only acknowledges the prompt; "increase_daily" also records a
    rebase event for today, so the replay re-spreads deterministically."""
    period = await _require_period(session)
    today = date.today()
    if body.choice == "increase_daily":
        session.add(RebaseEvent(period_id=period.id, day=today))
    period.prompt_ack_date = today
    await session.commit()
    await _queue_sheets_sync(background_tasks, session, period)
    return {"status": "ok", "budget": await _budget_for(session, period)}


@app.post("/sheets/sync", dependencies=[AUTH])
async def sheets_sync(session: AsyncSession = Depends(get_session)):
    """Manual "sync now": same full re-sync, run in a threadpool
    (gspread is synchronous). Returns ok/failed instead of raising."""
    if not sheets.enabled():
        return {"status": "disabled"}
    period = await _require_period(session)
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


@app.get("/export.xlsx", dependencies=[AUTH])
async def export_xlsx(session: AsyncSession = Depends(get_session)):
    period = await _require_period(session)
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
