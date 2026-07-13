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


EXPENSE_HEADERS = [
    "Date",
    "Amount",
    "Comment",
    "Running balance",
    "Per-day allowance at that point",
]


def period_rows(
    total_amount: Decimal,
    start_date: date,
    end_date: date,
    expenses: Iterable[ExpenseRow],
    today: date | None = None,
) -> list[list]:
    """The "Period" sheet as a two-column key/value table. Shared by the
    .xlsx export and the Google Sheets sync so they always agree."""
    summary = budget.compute_budget(
        total_amount, start_date, end_date,
        (e.amount for e in expenses), today=today,
    )
    return [
        ["total_amount", total_amount],
        ["start_date", start_date.isoformat()],
        ["end_date", end_date.isoformat()],
        ["days_total", summary.days_total],
        ["spent_total", summary.spent_total],
        ["remaining", summary.remaining_money],
    ]


def expense_rows(
    total_amount: Decimal,
    start_date: date,
    end_date: date,
    expenses: Iterable[ExpenseRow],
) -> list[list]:
    """The "Expenses" sheet body: expenses replayed in chronological order with
    running balance and the per-day allowance at each point. No header row."""
    rows: list[list] = []
    balance = total_amount
    for e in sorted(expenses, key=lambda e: e.created_at):
        balance -= e.amount
        day = e.created_at.date()
        days_left = budget.days_remaining(start_date, end_date, day)
        rows.append(
            [
                day.isoformat(),
                e.amount,
                e.comment or "",
                balance,
                budget.per_day(balance, days_left),
            ]
        )
    return rows


def build_workbook(
    total_amount: Decimal,
    start_date: date,
    end_date: date,
    expenses: Iterable[ExpenseRow],
    today: date | None = None,
) -> bytes:
    """One workbook, two sheets: "Period" (key/value) and "Expenses"
    (chronological replay with running balance and per-day allowance)."""
    wb = Workbook()

    # --- Sheet "Period": two-column key/value table -------------------------
    ws = wb.active
    ws.title = "Period"
    for row in period_rows(total_amount, start_date, end_date, expenses, today):
        ws.append(row)
    _autosize(ws)

    # --- Sheet "Expenses": replay in chronological order ---------------------
    ws = wb.create_sheet("Expenses")
    ws.append(EXPENSE_HEADERS)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for row in expense_rows(total_amount, start_date, end_date, expenses):
        ws.append(row)
    _autosize(ws)

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _autosize(ws) -> None:
    for idx, column in enumerate(ws.columns, start=1):
        width = max((len(str(c.value)) for c in column if c.value is not None), default=0)
        ws.column_dimensions[get_column_letter(idx)].width = width + 2
