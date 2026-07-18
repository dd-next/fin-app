"""Pure calendar recurrence helpers for Plan occurrences."""

import calendar
from datetime import date, timedelta


def add_months(anchor: date, months: int) -> date:
    absolute = anchor.year * 12 + anchor.month - 1 + months
    year, month_index = divmod(absolute, 12)
    month = month_index + 1
    day = min(anchor.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def add_years(anchor: date, years: int) -> date:
    day = min(anchor.day, calendar.monthrange(anchor.year + years, anchor.month)[1])
    return date(anchor.year + years, anchor.month, day)


def horizon_date(today: date) -> date:
    return add_years(today, 1)


def occurrence_dates(
    first_due_date: date, recurrence: str, through: date
) -> list[date]:
    if first_due_date > through:
        return []
    if recurrence == "once":
        return [first_due_date]
    dates: list[date] = []
    index = 0
    while True:
        if recurrence == "weekly":
            current = first_due_date + timedelta(days=7 * index)
        elif recurrence == "monthly":
            current = add_months(first_due_date, index)
        elif recurrence == "yearly":
            current = add_years(first_due_date, index)
        else:
            raise ValueError("Unsupported recurrence")
        if current > through:
            break
        dates.append(current)
        index += 1
    return dates
