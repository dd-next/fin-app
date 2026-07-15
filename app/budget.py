"""Pure budget math for the daily-budget tracker.

No database, no framework imports. Functions take plain values / Decimals
and return Decimals, so this module can be unit-tested in isolation.

All money values are Decimal — never float. Displayed per-day / allowance
values are rounded to 2 decimals; stored amounts stay exact.

The reference behavior:

- Setting a period fixes a daily base: total_amount / days_total.
- A day's budget is the base plus whatever previous days left unspent
  (undershoot rolls forward).
- Spending reduces TODAY's number 1:1 — it is not re-spread over the
  remaining days while today's budget lasts.
- A day that ends overspent eats the overall pool: the base is rebased to
  (money left) / (days after that day) and the carry-over resets.

Everything is derived from (period + dated expenses); there is no hidden
state, so recomputing from scratch is always correct.

Incomes (mid-period top-ups) enter the replay as NEGATIVE amounts: an
income on day D is "negative spending", so it grows that day's leftover
(and the pool) from day D onward. Callers sign the amounts; this module
stays agnostic.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable

TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0")

# (calendar day the expense belongs to, amount)
DatedAmount = tuple[date, Decimal]


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
    """Days left in the period, today included. Never 0 (guards division)."""
    total = days_total(start_date, end_date)
    elapsed = days_elapsed(start_date, end_date, today)
    return max(total - elapsed, 1)


def per_day(remaining: Decimal, days_left: int) -> Decimal:
    """Money spread evenly over days_left, rounded to 2 decimals."""
    return round2(remaining / days_left)


def preview_after(available_today: Decimal, pending: Decimal) -> Decimal:
    """Live preview of today's number if a pending (unsaved) expense lands."""
    return round2(available_today - pending)


@dataclass(frozen=True)
class BudgetSummary:
    days_total: int
    days_remaining: int
    spent_total: Decimal
    remaining_money: Decimal
    daily_base: Decimal  # today's per-day base, fixed at the start of the day
    budget_today: Decimal  # daily_base + unspent carried over from past days
    spent_today: Decimal
    # budget_today - spent_today: drops 1:1 as you spend, may go negative
    per_day_today: Decimal
    next_daily: Decimal  # tomorrow's day budget if nothing more is spent today


def _clamp_day(day: date, first: date, last: date) -> date:
    return min(max(day, first), last)


def compute_budget(
    total_amount: Decimal,
    start_date: date,
    end_date: date,
    expenses: Iterable[DatedAmount],
    today: date | None = None,
) -> BudgetSummary:
    """Derive the full budget summary from the period and its dated expenses.

    Everything is recomputed from scratch — there is no hidden state, so
    adding or deleting expenses can never corrupt the numbers.
    """
    today = today if today is not None else date.today()
    total = days_total(start_date, end_date)
    left = days_remaining(start_date, end_date, today)

    # Clamp the reference day and every expense into the period, so entries
    # dated outside it (before start, or after the period ended) still land
    # on a real day instead of being lost.
    ref = _clamp_day(today, start_date, end_date)
    spent_by_day: dict[date, Decimal] = {}
    spent = ZERO
    for day, amount in expenses:
        day = _clamp_day(day, start_date, ref)
        spent_by_day[day] = spent_by_day.get(day, ZERO) + amount
        spent += amount

    # Replay the fully elapsed days: unspent allowance rolls forward; a day
    # that ended overspent ate the pool, so the daily base rebases over the
    # days after it — exactly the reference behavior.
    daily = total_amount / total
    carry = ZERO
    spent_before_today = ZERO
    day = start_date
    while day < ref:
        day_spent = spent_by_day.get(day, ZERO)
        spent_before_today += day_spent
        leftover = daily + carry - day_spent
        if leftover >= 0:
            carry = leftover
        else:
            daily = (total_amount - spent_before_today) / (end_date - day).days
            carry = ZERO
        day += timedelta(days=1)

    budget_today = daily + carry
    spent_today = spent - spent_before_today
    available = budget_today - spent_today
    remaining = total_amount - spent

    # Tomorrow, by the same day-end rule applied to today as it stands:
    # leftover rolls forward; overspend rebases over the remaining days.
    if available >= 0:
        next_daily = daily + available
    else:
        next_daily = remaining / max(left - 1, 1)

    return BudgetSummary(
        days_total=total,
        days_remaining=left,
        spent_total=spent,
        remaining_money=remaining,
        daily_base=round2(daily),
        budget_today=round2(budget_today),
        spent_today=spent_today,
        per_day_today=round2(available),
        next_daily=round2(next_daily),
    )
