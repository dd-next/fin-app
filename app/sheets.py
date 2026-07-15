"""Google Sheets sync: idempotent full re-sync of the "Period" and
"Expenses" sheets from current DB state. The DB is the source of truth;
the sheet is only a mirror, so every sync rewrites it from scratch.

Auth is a service account (share the sheet with its client_email as
Editor). All calls are best-effort: a Google outage must never break the
app or lose data.

gspread is synchronous — callers run these functions in a threadpool
(FastAPI BackgroundTasks / run_in_threadpool), keeping the event loop free.
"""

import logging
import os
from datetime import date
from decimal import Decimal
from typing import Iterable

from app import export

logger = logging.getLogger(__name__)


def enabled() -> bool:
    """True only when the feature flag is on AND config is complete.
    Read at call time so tests (and .env changes) take effect without
    reimporting."""
    flag = os.environ.get("SHEETS_ENABLED", "").strip().lower()
    return (
        flag in ("1", "true", "yes", "on")
        and bool(os.environ.get("GOOGLE_SHEET_ID"))
        and bool(os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE"))
    )


def _open_spreadsheet():
    # Imported lazily so the app runs with Sheets unconfigured even if
    # gspread is not installed.
    import gspread

    client = gspread.service_account(
        filename=os.environ["GOOGLE_SERVICE_ACCOUNT_FILE"]
    )
    return client.open_by_key(os.environ["GOOGLE_SHEET_ID"])


def _cell(value):
    # Decimal → float so amounts land as numeric cells (display only;
    # the DB keeps the exact Decimal).
    return float(value) if isinstance(value, Decimal) else value


def _rewrite(spreadsheet, title: str, rows: list[list]) -> None:
    import gspread

    try:
        worksheet = spreadsheet.worksheet(title)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title, rows=100, cols=10)
    worksheet.clear()
    worksheet.update([[_cell(v) for v in row] for row in rows])


def sync_now(
    total_amount: Decimal,
    start_date: date,
    end_date: date,
    operations: Iterable[export.OperationRow],
    rebase_days: Iterable[date] = (),
) -> None:
    """Full re-sync. Raises on failure — use sync_safe() for fire-and-forget.

    Row layout is identical to the .xlsx export (same shared builders)."""
    operations = list(operations)
    rebase_days = list(rebase_days)
    spreadsheet = _open_spreadsheet()
    _rewrite(
        spreadsheet,
        "Period",
        export.period_rows(
            total_amount, start_date, end_date, operations,
            rebase_days=rebase_days,
        ),
    )
    _rewrite(
        spreadsheet,
        "Expenses",
        [export.EXPENSE_HEADERS]
        + export.expense_rows(
            total_amount, start_date, end_date, operations, rebase_days
        ),
    )


def sync_safe(
    total_amount: Decimal,
    start_date: date,
    end_date: date,
    operations: Iterable[export.OperationRow],
    rebase_days: Iterable[date] = (),
) -> None:
    """Best-effort sync for BackgroundTasks: log failures, never raise."""
    try:
        sync_now(total_amount, start_date, end_date, operations, rebase_days)
    except Exception:
        logger.exception("Google Sheets sync failed (data is safe in the DB)")
