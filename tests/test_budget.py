"""Unit tests for the pure budget math in app/budget.py.

Semantics under test are the reference behavior: a fixed daily base,
unspent money rolling forward into today, spending reducing TODAY 1:1, and
an overspent day eating the pool and rebasing the base for the days after.
"""

from datetime import date
from decimal import Decimal

from app.budget import (
    BudgetSummary,
    compute_budget,
    days_remaining,
    days_total,
    per_day,
    preview_after,
)

D = Decimal
START = date(2026, 7, 1)
END = date(2026, 7, 10)  # 10-day period, inclusive


def on(day: int, amount: str) -> tuple[date, Decimal]:
    """A dated expense inside the July test period."""
    return (date(2026, 7, day), D(amount))


def test_normal_split_across_days():
    # 1000 over 10 days, on day 1 → 100/day
    s = compute_budget(D("1000"), START, END, [], today=START)
    assert s == BudgetSummary(
        days_total=10,
        days_remaining=10,
        spent_total=D("0"),
        remaining_money=D("1000"),
        daily_base=D("100.00"),
        budget_today=D("100.00"),
        spent_today=D("0"),
        per_day_today=D("100.00"),
        next_daily=D("200.00"),  # today untouched, so it rolls into tomorrow
    )


def test_uneven_split_rounds_to_two_places():
    # 100 over 3 days → 33.33 exactly (Decimal, no float drift)
    s = compute_budget(
        D("100"), date(2026, 7, 1), date(2026, 7, 3), [],
        today=date(2026, 7, 1),
    )
    assert s.per_day_today == D("33.33")


def test_spending_reduces_today_one_to_one():
    # THE core behavior (and the original bug): an expense today comes out
    # of today's budget in full — it is not re-spread over remaining days.
    before = compute_budget(D("1000"), START, END, [], today=START)
    after = compute_budget(D("1000"), START, END, [on(1, "40")], today=START)
    assert before.per_day_today == D("100.00")
    assert after.budget_today == D("100.00")  # fixed for the whole day
    assert after.spent_today == D("40")
    assert after.per_day_today == D("60.00")  # 100 - 40, not (1000-40)/10
    assert after.remaining_money == D("960")


def test_unspent_money_rolls_into_today():
    # Spend only 40 of day 1's 100 → day 2 gets 100 + 60.
    s = compute_budget(D("1000"), START, END, [on(1, "40")],
                       today=date(2026, 7, 2))
    assert s.daily_base == D("100.00")
    assert s.budget_today == D("160.00")
    assert s.spent_today == D("0")
    assert s.per_day_today == D("160.00")
    # untouched days keep accumulating, and next_daily is tomorrow's reality
    s3 = compute_budget(D("1000"), START, END, [on(1, "40")],
                        today=date(2026, 7, 3))
    assert s3.budget_today == s.next_daily == D("260.00")


def test_overspent_day_rebases_daily_budget():
    # Day 1 blows past its 100 (spent 250): the pool takes the hit and the
    # daily base is rebased to remaining/days-after → 750/9.
    s = compute_budget(D("1000"), START, END, [on(1, "250")],
                       today=date(2026, 7, 2))
    assert s.remaining_money == D("750")
    assert s.daily_base == D("83.33")
    assert s.budget_today == D("83.33")  # no carry after an overspent day
    assert s.per_day_today == D("83.33")


def test_exactly_spent_day_keeps_base():
    # Spending exactly the day's budget is not an overspend: no rebase.
    s = compute_budget(D("1000"), START, END, [on(1, "100")],
                       today=date(2026, 7, 2))
    assert s.daily_base == D("100.00")
    assert s.budget_today == D("100.00")


def test_overspending_today_goes_negative_not_clamped():
    # 100 over 10 days, then 150 spent on day 1: today shows the real hole
    # and next_daily previews the rebased (negative) daily budget.
    s = compute_budget(D("100"), START, END, [on(1, "150")], today=START)
    assert s.budget_today == D("10.00")
    assert s.spent_today == D("150")
    assert s.per_day_today == D("-140.00")
    assert s.remaining_money == D("-50")
    assert s.next_daily == D("-5.56")  # -50 / 9
    # ...and the next morning that rebase is exactly what you wake up to
    morning = compute_budget(D("100"), START, END, [on(1, "150")],
                             today=date(2026, 7, 2))
    assert morning.per_day_today == D("-5.56")


def test_screenshot_scenario_from_bug_report():
    # 6000 over 15 days; 393.33 + 100 spent on day 1. Today must drop 1:1
    # (400 - 493.33), showing the over-state with next daily 5506.67/14.
    start, end = date(2026, 7, 15), date(2026, 7, 29)
    s = compute_budget(
        D("6000"), start, end,
        [(start, D("393.33")), (start, D("100"))],
        today=start,
    )
    assert s.budget_today == D("400.00")
    assert s.spent_today == D("493.33")
    assert s.per_day_today == D("-93.33")
    assert s.remaining_money == D("5506.67")
    assert s.next_daily == D("393.33")


def test_last_day_per_day_equals_remaining():
    s = compute_budget(D("1000"), START, END, [on(1, "300")], today=END)
    assert s.days_remaining == 1
    assert s.per_day_today == s.remaining_money == D("700")


def test_after_end_date_guarded_to_one_day_no_crash():
    s = compute_budget(D("1000"), START, END, [on(1, "400")],
                       today=date(2026, 8, 1))
    assert s.days_remaining == 1
    assert s.per_day_today == D("600.00")


def test_before_start_date_days_elapsed_clamped():
    # today before the period: no days elapsed, full period remaining
    s = compute_budget(D("1000"), START, END, [], today=date(2026, 6, 20))
    assert s.days_remaining == 10
    assert s.per_day_today == D("100.00")


def test_expense_dates_outside_period_are_clamped():
    # dated before the start → counts on the first day
    s = compute_budget(D("1000"), START, END, [(date(2026, 6, 25), D("100"))],
                       today=date(2026, 7, 2))
    assert s.spent_total == D("100")
    assert s.per_day_today == D("100.00")  # day 1 spent exactly its 100
    # dated after today → counts today, not silently dropped
    s2 = compute_budget(D("1000"), START, END, [on(9, "50")], today=START)
    assert s2.spent_today == D("50")
    assert s2.per_day_today == D("50.00")


def test_zero_length_period_never_raises():
    # single-day period (start == end): days_total == 1, never divides by 0
    d = date(2026, 7, 5)
    s = compute_budget(D("50"), d, d, [], today=d)
    assert s.days_total == 1
    assert s.days_remaining == 1
    assert s.per_day_today == D("50")
    # even far past the end it stays guarded
    s2 = compute_budget(D("50"), d, d, [(d, D("50"))], today=date(2027, 1, 1))
    assert s2.days_remaining == 1
    assert s2.per_day_today == D("0.00")


def test_days_remaining_never_zero_direct():
    assert days_remaining(START, END, date(2030, 1, 1)) == 1
    assert days_total(START, START) == 1


def test_delete_after_increase_equals_fresh_recompute():
    # Sequence: overspend on day 2 (rebase), underspend later (carry), so the
    # allowance history rises and falls. Delete the earlier expense and assert
    # we match a from-scratch recomputation — there is no hidden state.
    expenses = [on(2, "300"), on(4, "50")]
    mid = date(2026, 7, 6)
    with_all = compute_budget(D("1000"), START, END, expenses, today=mid)
    # day 2 rebased to 700/8 = 87.50; days 3-5 carried 87.50+125+87.50
    assert with_all.per_day_today == D("300.00")

    after_delete = compute_budget(D("1000"), START, END, [on(4, "50")],
                                  today=mid)
    fresh = compute_budget(D("1000"), START, END, [on(4, "50")], today=mid)
    assert after_delete == fresh
    assert after_delete.remaining_money == D("950")
    assert after_delete.per_day_today == D("550.00")
    assert after_delete.per_day_today > with_all.per_day_today


def test_income_today_raises_todays_number():
    # Incomes enter the replay as negative amounts. +200 on day 1 raises
    # today's number 1:1 and grows the pool.
    s = compute_budget(D("1000"), START, END,
                       [on(1, "40"), on(1, "-200")], today=START)
    assert s.budget_today == D("100.00")
    assert s.spent_today == D("-160")  # 40 spent, 200 received
    assert s.per_day_today == D("260.00")  # 100 - 40 + 200
    assert s.remaining_money == D("1160")


def test_income_after_overspent_day_rolls_forward():
    # Day 1 overspends (250 > 100) → rebase to 750/9. Day 2 receives 500,
    # spends nothing → the whole 500 (plus day 2's base) carries into day 3.
    s = compute_budget(D("1000"), START, END,
                       [on(1, "250"), on(2, "-500")], today=date(2026, 7, 3))
    assert s.daily_base == D("83.33")  # 750/9, set by the day-1 rebase
    assert s.budget_today == D("666.67")  # 83.33 (base) + 83.33 + 500 (carry)
    assert s.remaining_money == D("1250")


def test_income_delete_equals_fresh_recompute():
    # Removing an income is just recomputing without it — no hidden state.
    with_income = compute_budget(D("1000"), START, END,
                                 [on(1, "250"), on(2, "-300")],
                                 today=date(2026, 7, 4))
    without = compute_budget(D("1000"), START, END, [on(1, "250")],
                             today=date(2026, 7, 4))
    fresh = compute_budget(D("1000"), START, END, [on(1, "250")],
                           today=date(2026, 7, 4))
    assert without == fresh
    assert with_income.remaining_money - without.remaining_money == D("300")


def test_preview_after_pending_expense():
    # today shows 100.00, typing 30 previews 70.00
    assert preview_after(D("100.00"), D("30")) == D("70.00")
    # preview may go negative too
    assert preview_after(D("50"), D("150")) == D("-100.00")


def test_decimal_exactness_no_float_drift():
    # 0.1 + 0.2 style trap: Decimals must sum exactly
    d = date(2026, 7, 1)
    s = compute_budget(D("1.00"), d, d, [(d, D("0.10")), (d, D("0.20"))],
                       today=d)
    assert s.spent_total == D("0.30")
    assert s.remaining_money == D("0.70")
    assert s.per_day_today == D("0.70")
    assert isinstance(s.remaining_money, Decimal)
    assert per_day(D("10"), 3) == D("3.33")
