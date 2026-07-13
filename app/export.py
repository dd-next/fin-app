"""Build the .xlsx export workbook (openpyxl). Pure: takes plain values,
returns bytes — no DB or framework imports."""

from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from typing import Iterable, NamedTuple

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from app import budget

FILENAME = "tzlvt-export.xlsx"
CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class ExpenseRow(NamedTuple):
    created_at: datetime
    amount: Decimal
    comment: str | None


def build_workbook(
    total_amount: Decimal,
    start_date: date,
    end_date: date,
    expenses: Iterable[ExpenseRow],
    today: date | None = None,
) -> bytes:
    """One workbook, two sheets: "Period" (key/value) and "Expenses"
    (chronological replay with running balance and per-day allowance)."""
    expenses = sorted(expenses, key=lambda e: e.created_at)
    summary = budget.compute_budget(
        total_amount, start_date, end_date, (e.amount for e in expenses), today=today
    )

    wb = Workbook()

    # --- Sheet "Period": two-column key/value table -------------------------
    ws = wb.active
    ws.title = "Period"
    period_rows = [
        ("total_amount", total_amount),
        ("start_date", start_date.isoformat()),
        ("end_date", end_date.isoformat()),
        ("days_total", summary.days_total),
        ("spent_total", summary.spent_total),
        ("remaining", summary.remaining_money),
    ]
    for key, value in period_rows:
        ws.append([key, value])
    _autosize(ws)

    # --- Sheet "Expenses": replay in chronological order ---------------------
    ws = wb.create_sheet("Expenses")
    headers = ["Date", "Amount", "Comment", "Running balance", "Per-day allowance at that point"]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    balance = total_amount
    for e in expenses:
        balance -= e.amount
        day = e.created_at.date()
        days_left = budget.days_remaining(start_date, end_date, day)
        ws.append(
            [
                day.isoformat(),
                e.amount,
                e.comment or "",
                balance,
                budget.per_day(balance, days_left),
            ]
        )
    _autosize(ws)

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _autosize(ws) -> None:
    for idx, column in enumerate(ws.columns, start=1):
        width = max((len(str(c.value)) for c in column if c.value is not None), default=0)
        ws.column_dimensions[get_column_letter(idx)].width = width + 2
