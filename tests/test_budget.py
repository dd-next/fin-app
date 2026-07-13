"""Unit tests for the pure budget math in app/budget.py."""

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


def test_normal_split_across_days():
    # 1000 over 10 days, on day 1 → 100/day
    s = compute_budget(D("1000"), START, END, [], today=START)
    assert s == BudgetSummary(
        days_total=10,
        days_remaining=10,
        spent_total=D("0"),
        remaining_money=D("1000"),
        per_day_today=D("100.00"),
    )


def test_uneven_split_rounds_to_two_places():
    # 100 over 3 days → 33.33 exactly (Decimal, no float drift)
    s = compute_budget(D("100"), date(2026, 7, 1), date(2026, 7, 3), [], today=date(2026, 7, 1))
    assert s.per_day_today == D("33.33")


def test_expense_lowers_per_day_today():
    before = compute_budget(D("1000"), START, END, [], today=START)
    after = compute_budget(D("1000"), START, END, [D("250")], today=START)
    assert before.per_day_today == D("100.00")
    assert after.spent_total == D("250")
    assert after.remaining_money == D("750")
    assert after.per_day_today == D("75.00")
    assert after.per_day_today < before.per_day_today


def test_overspend_goes_negative_not_clamped():
    s = compute_budget(D("100"), START, END, [D("150")], today=START)
    assert s.remaining_money == D("-50")
    assert s.per_day_today == D("-5.00")


def test_last_day_per_day_equals_remaining():
    s = compute_budget(D("1000"), START, END, [D("300")], today=END)
    assert s.days_remaining == 1
    assert s.per_day_today == s.remaining_money == D("700")


def test_after_end_date_guarded_to_one_day_no_crash():
    s = compute_budget(D("1000"), START, END, [D("400")], today=date(2026, 8, 1))
    assert s.days_remaining == 1
    assert s.per_day_today == D("600.00")


def test_before_start_date_days_elapsed_clamped():
    # today before the period: no days elapsed, full period remaining
    s = compute_budget(D("1000"), START, END, [], today=date(2026, 6, 20))
    assert s.days_remaining == 10
    assert s.per_day_today == D("100.00")


def test_zero_length_period_never_raises():
    # single-day period (start == end): days_total == 1, never divides by 0
    d = date(2026, 7, 5)
    s = compute_budget(D("50"), d, d, [], today=d)
    assert s.days_total == 1
    assert s.days_remaining == 1
    assert s.per_day_today == D("50")
    # even far past the end it stays guarded
    s2 = compute_budget(D("50"), d, d, [D("50")], today=date(2027, 1, 1))
    assert s2.days_remaining == 1
    assert s2.per_day_today == D("0.00")


def test_days_remaining_never_zero_direct():
    assert days_remaining(START, END, date(2030, 1, 1)) == 1
    assert days_total(START, START) == 1


def test_delete_after_increase_equals_fresh_recompute():
    # Sequence: spend 300 early, then mid-period the allowance "rises"
    # (fewer days remaining redistributes remaining money). Delete the
    # earlier expense and assert we match a from-scratch recomputation.
    expenses = [D("300"), D("50")]
    mid = date(2026, 7, 6)  # 5 days remaining
    with_all = compute_budget(D("1000"), START, END, expenses, today=mid)
    assert with_all.per_day_today == D("130.00")  # (1000-350)/5

    after_delete = compute_budget(D("1000"), START, END, [D("50")], today=mid)
    fresh = compute_budget(D("1000"), START, END, [D("50")], today=mid)
    assert after_delete == fresh
    assert after_delete.remaining_money == D("950")
    assert after_delete.per_day_today == D("190.00")


def test_preview_after_pending_expense():
    # remaining 1000, 10 days left, pending 100 → (1000-100)/10 = 90
    assert preview_after(D("1000"), D("100"), 10) == D("90.00")
    # preview may go negative too
    assert preview_after(D("50"), D("150"), 10) == D("-10.00")


def test_decimal_exactness_no_float_drift():
    # 0.1 + 0.2 style trap: Decimals must sum exactly
    s = compute_budget(
        D("1.00"),
        date(2026, 7, 1),
        date(2026, 7, 1),
        [D("0.10"), D("0.20")],
        today=date(2026, 7, 1),
    )
    assert s.spent_total == D("0.30")
    assert s.remaining_money == D("0.70")
    assert s.per_day_today == D("0.70")
    assert isinstance(s.remaining_money, Decimal)
    assert per_day(D("10"), 3) == D("3.33")
