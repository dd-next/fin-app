"""Pure daily-budget math for account periods.

No database, no framework imports. Functions take plain values / Decimals
and return Decimals, so this module can be unit-tested in isolation.

All money values are Decimal — never float. Displayed per-day / allowance
values are rounded to the caller-provided base-asset quantum; stored amounts
stay exact. The default remains 0.01 for backwards compatibility.

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

The legacy `compute_budget` compatibility function receives expense-style
amounts: spending is positive and income is negative. The v2
`compute_carry_next_day` policy receives signed account-balance effects
directly: outflow is negative and income is positive. T-006 adds the common
policy dispatch; callers must not invert v2 ledger-effect signs.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Iterable

TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0")
CALCULATION_PRECISION = 100

# (calendar day the expense belongs to, amount)
DatedAmount = tuple[date, Decimal]


@dataclass(frozen=True)
class AllowanceResult:
    days_total: int
    days_remaining: int
    current_balance: Decimal
    daily_base_exact: Decimal
    carry_exact: Decimal
    available_before_today_effects_exact: Decimal
    today_net: Decimal
    available_today_exact: Decimal
    daily_base: Decimal
    available_today: Decimal


def round2(value: Decimal) -> Decimal:
    """Round a Decimal to 2 decimal places for display."""
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def round_to_quantum(value: Decimal, quantum: Decimal = TWO_PLACES) -> Decimal:
    """Round a display value to the precision of the period base asset."""
    quantum = Decimal(quantum)
    if not quantum.is_finite() or quantum <= 0:
        raise ValueError("quantum must be a positive finite Decimal")
    value = Decimal(value)
    with localcontext() as context:
        context.prec = max(
            CALCULATION_PRECISION,
            len(value.as_tuple().digits) + max(-quantum.as_tuple().exponent, 0) + 2,
        )
        return value.quantize(quantum, rounding=ROUND_HALF_UP)


def _exact_sum(values: Iterable[Decimal]) -> Decimal:
    items = [Decimal(value) for value in values]
    nonzero = [value for value in items if value]
    if not nonzero:
        return ZERO
    digits = (
        max(value.adjusted() for value in nonzero)
        - min(value.as_tuple().exponent for value in nonzero)
        + len(str(len(items)))
        + 2
    )
    with localcontext() as context:
        context.prec = max(CALCULATION_PRECISION, digits)
        total = ZERO
        for value in items:
            total += value
        return total


def _difference(left: Decimal, right: Decimal) -> Decimal:
    return _exact_sum((Decimal(left), Decimal(right).copy_negate()))


def _quotient(value: Decimal, divisor: int) -> Decimal:
    with localcontext() as context:
        context.prec = CALCULATION_PRECISION
        return Decimal(value) / Decimal(divisor)


def _asset_precision_quantum(quantum: Decimal) -> Decimal:
    quantum = Decimal(quantum)
    if not quantum.is_finite() or quantum <= 0:
        raise ValueError("quantum must be a positive finite Decimal")
    normalized = quantum.normalize()
    if normalized.as_tuple().digits != (1,) or normalized.as_tuple().exponent > 0:
        raise ValueError("quantum must be a base-10 asset precision of the form 1E-n")
    return normalized


def days_total(start_date: date, end_date: date) -> int:
    """Number of days in the period, inclusive of both endpoints."""
    return (end_date - start_date).days + 1


def compute_carry_next_day(
    pool_start: Decimal,
    start_date: date,
    end_date: date,
    effects: Iterable[DatedAmount],
    *,
    today: date | None = None,
    quantum: Decimal = TWO_PLACES,
) -> AllowanceResult:
    """Compute exact carry-forward allowance from signed balance effects.

    Effects must already be assigned to an inclusive period day no later than
    the bounded reference day. Negative values are outflows; positive values
    are inflows.
    """
    if end_date < start_date:
        raise ValueError("end_date must not precede start_date")
    quantum = _asset_precision_quantum(quantum)
    reference_day = today if today is not None else date.today()
    reference_day = _clamp_day(reference_day, start_date, end_date)
    total = days_total(start_date, end_date)
    remaining_days = (end_date - reference_day).days + 1

    net_by_day: dict[date, Decimal] = {}
    for day, effect in effects:
        if day < start_date or day > end_date or day > reference_day:
            raise ValueError(
                "effects must be assigned within the period through the reference day"
            )
        net_by_day[day] = _exact_sum(
            (net_by_day.get(day, ZERO), Decimal(effect))
        )

    pool_start = Decimal(pool_start)
    daily_base = _quotient(pool_start, total)
    carry = ZERO
    balance_after_day = pool_start
    day = start_date
    while day < reference_day:
        net_day = net_by_day.get(day, ZERO)
        balance_after_day = _exact_sum((balance_after_day, net_day))
        available_end = _exact_sum((daily_base, carry, net_day))
        if available_end >= 0:
            carry = available_end
        else:
            daily_base = _quotient(
                balance_after_day,
                (end_date - day).days,
            )
            carry = ZERO
        day += timedelta(days=1)

    today_net = net_by_day.get(reference_day, ZERO)
    current_balance = _exact_sum((balance_after_day, today_net))
    available_before_today_effects = _exact_sum((daily_base, carry))
    available_today = _exact_sum((available_before_today_effects, today_net))
    return AllowanceResult(
        days_total=total,
        days_remaining=remaining_days,
        current_balance=current_balance,
        daily_base_exact=daily_base,
        carry_exact=carry,
        available_before_today_effects_exact=available_before_today_effects,
        today_net=today_net,
        available_today_exact=available_today,
        daily_base=round_to_quantum(daily_base, quantum),
        available_today=round_to_quantum(available_today, quantum),
    )


def days_elapsed(start_date: date, end_date: date, today: date) -> int:
    """Days already gone, clamped to [0, days_total]."""
    total = days_total(start_date, end_date)
    return max(0, min((today - start_date).days, total))


def days_remaining(start_date: date, end_date: date, today: date) -> int:
    """Days left in the period, today included. Never 0 (guards division)."""
    total = days_total(start_date, end_date)
    elapsed = days_elapsed(start_date, end_date, today)
    return max(total - elapsed, 1)


def per_day(
    remaining: Decimal, days_left: int, quantum: Decimal = TWO_PLACES
) -> Decimal:
    """Money spread evenly over days_left at base-asset precision."""
    return round_to_quantum(_quotient(remaining, days_left), quantum)


def preview_after(
    available_today: Decimal,
    pending: Decimal,
    quantum: Decimal = TWO_PLACES,
) -> Decimal:
    """Live preview of today's number if a pending (unsaved) expense lands."""
    return round_to_quantum(_difference(available_today, pending), quantum)


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
    rebase_days: Iterable[date] = (),
    quantum: Decimal = TWO_PLACES,
) -> BudgetSummary:
    """Derive the full budget summary from the period and its dated expenses.

    Everything is recomputed from scratch — there is no hidden state, so
    adding or deleting expenses can never corrupt the numbers.

    `rebase_days` are user-triggered rebases (the "increase the daily
    budget" choice): at the START of such a day the remaining money is
    re-spread evenly over the days from it to the end (inclusive) and the
    carry-over resets — the same mechanism as the overspend rebase, but
    voluntary and persisted as an event.
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
        amount = Decimal(amount)
        spent_by_day[day] = _exact_sum((spent_by_day.get(day, ZERO), amount))
        spent = _exact_sum((spent, amount))
    rebases = {d for d in rebase_days if start_date <= d <= end_date}

    # Replay the fully elapsed days: unspent allowance rolls forward; a day
    # that ended overspent ate the pool, so the daily base rebases over the
    # days after it — exactly the reference behavior.
    total_amount = Decimal(total_amount)
    daily = _quotient(total_amount, total)
    carry = ZERO
    spent_before_today = ZERO
    day = start_date
    while day < ref:
        if day in rebases:
            daily = _quotient(
                _difference(total_amount, spent_before_today),
                (end_date - day).days + 1,
            )
            carry = ZERO
        day_spent = spent_by_day.get(day, ZERO)
        spent_before_today = _exact_sum((spent_before_today, day_spent))
        leftover = _exact_sum((daily, carry, day_spent.copy_negate()))
        if leftover >= 0:
            carry = leftover
        else:
            daily = _quotient(
                _difference(total_amount, spent_before_today),
                (end_date - day).days,
            )
            carry = ZERO
        day += timedelta(days=1)
    if ref in rebases:
        daily = _quotient(
            _difference(total_amount, spent_before_today),
            (end_date - ref).days + 1,
        )
        carry = ZERO

    budget_today = _exact_sum((daily, carry))
    spent_today = _difference(spent, spent_before_today)
    available = _difference(budget_today, spent_today)
    remaining = _difference(total_amount, spent)

    # Tomorrow, by the same day-end rule applied to today as it stands:
    # leftover rolls forward; overspend rebases over the remaining days.
    if available >= 0:
        next_daily = _exact_sum((daily, available))
    else:
        next_daily = _quotient(remaining, max(left - 1, 1))

    return BudgetSummary(
        days_total=total,
        days_remaining=left,
        spent_total=spent,
        remaining_money=remaining,
        daily_base=round_to_quantum(daily, quantum),
        budget_today=round_to_quantum(budget_today, quantum),
        spent_today=spent_today,
        per_day_today=round_to_quantum(available, quantum),
        next_daily=round_to_quantum(next_daily, quantum),
    )
