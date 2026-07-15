"""FastAPI app + routes."""

from contextlib import asynccontextmanager
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import budget, export, sheets
from app.telegram_auth import require_telegram_auth
from app.db import engine, get_session
from app.models import Base, Expense, Period
from app.schemas import (
    BudgetOut,
    ExpenseIn,
    ExpenseOut,
    ExpenseWithBudget,
    PeriodIn,
    PeriodOut,
    PeriodWithBudget,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Zero-setup local dev: ensure tables exist (Alembic is the canonical
    # migration path; create_all is idempotent and a no-op after migrating).
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
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


async def _budget_for(
    session: AsyncSession, period: Period, pending: Decimal | None = None
) -> BudgetOut:
    result = await session.execute(
        select(Expense.created_at, Expense.amount).where(
            Expense.period_id == period.id
        )
    )
    dated = [
        (created.date(), amount) for created, amount in result.all()
    ]
    summary = budget.compute_budget(
        period.total_amount, period.start_date, period.end_date, dated
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


async def _expense_snapshot(
    session: AsyncSession, period: Period
) -> list[export.ExpenseRow]:
    result = await session.execute(
        select(Expense).where(Expense.period_id == period.id)
    )
    return [
        export.ExpenseRow(
            created_at=e.created_at, amount=e.amount, comment=e.comment
        )
        for e in result.scalars()
    ]


async def _queue_sheets_sync(
    background_tasks: BackgroundTasks, session: AsyncSession, period: Period
) -> None:
    """After a successful mutation: schedule a best-effort full re-sync.

    The snapshot is captured now (plain values) because the DB session is
    gone by the time the task runs, after the response is sent."""
    if not sheets.enabled():
        return
    rows = await _expense_snapshot(session, period)
    background_tasks.add_task(
        sheets.sync_safe,
        period.total_amount,
        period.start_date,
        period.end_date,
        rows,
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


@app.get("/expenses", response_model=list[ExpenseOut], dependencies=[AUTH])
async def list_expenses(session: AsyncSession = Depends(get_session)):
    period = await _require_period(session)
    result = await session.execute(
        select(Expense)
        .where(Expense.period_id == period.id)
        .order_by(Expense.created_at.desc(), Expense.id.desc())
    )
    return [ExpenseOut.model_validate(e) for e in result.scalars()]


@app.post("/expenses", response_model=ExpenseWithBudget, dependencies=[AUTH])
async def add_expense(
    body: ExpenseIn,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    period = await _require_period(session)
    expense = Expense(period_id=period.id, amount=body.amount, comment=body.comment)
    session.add(expense)
    await session.commit()
    await session.refresh(expense)
    await _queue_sheets_sync(background_tasks, session, period)
    return ExpenseWithBudget(
        expense=ExpenseOut.model_validate(expense),
        budget=await _budget_for(session, period),
    )


@app.delete("/expenses/{expense_id}", response_model=BudgetOut, dependencies=[AUTH])
async def delete_expense(
    expense_id: int,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    expense = await session.get(Expense, expense_id)
    if expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    period = await session.get(Period, expense.period_id)
    await session.delete(expense)
    await session.commit()
    await _queue_sheets_sync(background_tasks, session, period)
    # Everything is re-derived from (period + expenses), so deletion can
    # never corrupt the numbers.
    return await _budget_for(session, period)


@app.post("/sheets/sync", dependencies=[AUTH])
async def sheets_sync(session: AsyncSession = Depends(get_session)):
    """Manual "sync now": same full re-sync, run in a threadpool
    (gspread is synchronous). Returns ok/failed instead of raising."""
    if not sheets.enabled():
        return {"status": "disabled"}
    period = await _require_period(session)
    rows = await _expense_snapshot(session, period)
    try:
        await run_in_threadpool(
            sheets.sync_now,
            period.total_amount,
            period.start_date,
            period.end_date,
            rows,
        )
    except Exception:
        return {"status": "failed"}
    return {"status": "ok"}


@app.get("/export.xlsx", dependencies=[AUTH])
async def export_xlsx(session: AsyncSession = Depends(get_session)):
    period = await _require_period(session)
    result = await session.execute(
        select(Expense).where(Expense.period_id == period.id)
    )
    rows = [
        export.ExpenseRow(created_at=e.created_at, amount=e.amount, comment=e.comment)
        for e in result.scalars()
    ]
    data = export.build_workbook(
        period.total_amount, period.start_date, period.end_date, rows
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
