"""Pure budget math for the daily-budget tracker.

No database, no framework imports. Functions take plain values / Decimals
and return Decimals, so this module can be unit-tested in isolation.

All money values are Decimal — never float. Displayed per-day / allowance
values are rounded to 2 decimals; stored amounts stay exact.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable

TWO_PLACES = Decimal("0.01")


def round2(value: Decimal) -> Decimal:
    """Round a Decimal to 2 decimal places for display."""
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def days_total(start_date: date, end_date: date) -> int:
    """Number of days in the period, inclusive of both endpoints."""
    return (end_date - start_date).days + 1


def days_elapsed(start_date: date, end_date: date, today: date) -> int:
    """Days already gone, clamped to [0, days_total]."""
    total = days_total(start_date, end_date)
    return max(0, min((today - start_date).days, total))


def days_remaining(start_date: date, end_date: date, today: date) -> int:
    """Days left to spread the money over. Never 0 (guards division)."""
    total = days_total(start_date, end_date)
    elapsed = days_elapsed(start_date, end_date, today)
    return max(total - elapsed, 1)


def spent_total(amounts: Iterable[Decimal]) -> Decimal:
    """Sum of expense amounts. Empty input gives Decimal('0')."""
    return sum(amounts, Decimal("0"))


def remaining_money(total_amount: Decimal, spent: Decimal) -> Decimal:
    """Money left for the rest of the period. May go negative — do not clamp."""
    return total_amount - spent


def per_day(remaining: Decimal, days_left: int) -> Decimal:
    """Allowance per remaining day, rounded to 2 decimals. May be negative."""
    return round2(remaining / days_left)


def preview_after(remaining: Decimal, pending: Decimal, days_left: int) -> Decimal:
    """Live allowance preview if a pending (unsaved) expense were added."""
    return per_day(remaining - pending, days_left)


@dataclass(frozen=True)
class BudgetSummary:
    days_total: int
    days_remaining: int
    spent_total: Decimal
    remaining_money: Decimal
    per_day_today: Decimal


def compute_budget(
    total_amount: Decimal,
    start_date: date,
    end_date: date,
    amounts: Iterable[Decimal],
    today: date | None = None,
) -> BudgetSummary:
    """Derive the full budget summary from the period and its expenses.

    Everything is recomputed from scratch — there is no hidden state, so
    adding or deleting expenses can never corrupt the numbers.
    """
    today = today if today is not None else date.today()
    total = days_total(start_date, end_date)
    left = days_remaining(start_date, end_date, today)
    spent = spent_total(amounts)
    remaining = remaining_money(total_amount, spent)
    return BudgetSummary(
        days_total=total,
        days_remaining=left,
        spent_total=spent,
        remaining_money=remaining,
        per_day_today=per_day(remaining, left),
    )
