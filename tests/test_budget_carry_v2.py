import ast
import inspect
from dataclasses import FrozenInstanceError
from datetime import date
from decimal import Decimal, localcontext
from pathlib import Path

import pytest

from app.budget import AllowanceResult, compute_carry_next_day


D = Decimal
START = date(2026, 7, 1)
END = date(2026, 7, 10)


def effect(day: int, amount: str):
    return date(2026, 7, day), D(amount)


def quotient(value: str, divisor: str):
    with localcontext() as context:
        context.prec = 100
        return D(value) / D(divisor)


def test_canonical_carry_accumulates_only_into_the_next_day():
    end = date(2026, 7, 3)
    day_two = compute_carry_next_day(
        D("300"), START, end, [effect(1, "-60")], today=date(2026, 7, 2)
    )
    assert day_two.daily_base_exact == D("100")
    assert day_two.carry_exact == D("40")
    assert day_two.available_today_exact == D("140")

    day_three = compute_carry_next_day(
        D("300"), START, end, [effect(1, "-60"), effect(2, "0")],
        today=end,
    )
    assert day_three.daily_base_exact == D("100")
    assert day_three.carry_exact == D("140")
    assert day_three.available_today_exact == D("240")


def test_exact_spend_keeps_base_and_overspend_rebases_exactly():
    exact = compute_carry_next_day(
        D("1000"), START, END, [effect(1, "-100")], today=date(2026, 7, 2)
    )
    assert exact.daily_base_exact == D("100")
    assert exact.carry_exact == D("0")
    assert exact.current_balance == D("900")

    overspent = compute_carry_next_day(
        D("1000"), START, END, [effect(1, "-250")], today=date(2026, 7, 2)
    )
    assert overspent.daily_base_exact == quotient("750", "9")
    assert overspent.carry_exact == D("0")
    assert overspent.current_balance == D("750")

    repeated = compute_carry_next_day(
        D("1000"), START, END,
        [effect(1, "-250"), effect(2, "-100")],
        today=date(2026, 7, 3),
    )
    assert repeated.daily_base_exact == quotient("650", "8")
    assert repeated.carry_exact == D("0")
    assert repeated.current_balance == D("650")


def test_signed_current_day_effect_is_applied_once():
    outflow = compute_carry_next_day(
        D("1000"), START, END, [effect(1, "-40")], today=START
    )
    assert outflow.available_before_today_effects_exact == D("100")
    assert outflow.today_net == D("-40")
    assert outflow.available_today_exact == D("60")
    assert outflow.current_balance == D("960")

    income = compute_carry_next_day(
        D("1000"), START, END, [effect(1, "200")], today=START
    )
    assert income.available_today_exact == D("300")
    assert income.current_balance == D("1200")


def test_negative_one_day_and_reference_bounds_never_clamp_to_zero():
    one_day = compute_carry_next_day(
        D("50"), START, START, [effect(1, "-60")], today=START
    )
    assert one_day.days_total == one_day.days_remaining == 1
    assert one_day.current_balance == D("-10")
    assert one_day.available_today_exact == D("-10")
    assert one_day.available_today == D("-10.00")

    before = compute_carry_next_day(
        D("1000"), START, END, [], today=date(2026, 6, 1)
    )
    after = compute_carry_next_day(
        D("1000"), START, END, [], today=date(2027, 1, 1)
    )
    assert before.days_remaining == 10
    assert before.available_today_exact == D("100")
    assert after.days_remaining == 1
    assert after.available_today_exact == D("1000")


def test_negative_starting_pool_stays_negative_across_completed_day_rebase():
    result = compute_carry_next_day(
        D("-90"),
        START,
        date(2026, 7, 3),
        [],
        today=date(2026, 7, 2),
    )
    assert result.current_balance == D("-90")
    assert result.daily_base_exact == D("-45")
    assert result.carry_exact == D("0")
    assert result.available_today_exact == D("-45")
    assert result.available_today == D("-45.00")


@pytest.mark.parametrize(
    "effects,today",
    [
        ([(date(2026, 6, 30), D("1"))], START),
        ([(date(2026, 7, 11), D("1"))], END),
        ([(date(2026, 7, 2), D("1"))], START),
    ],
)
def test_effects_outside_assigned_window_are_rejected(effects, today):
    with pytest.raises(ValueError, match="assigned within the period"):
        compute_carry_next_day(D("1000"), START, END, effects, today=today)


@pytest.mark.parametrize("quantum", [D("0"), D("-0.01"), D("Infinity"), D("0.05"), D("10")])
def test_invalid_range_and_non_asset_quantums_are_rejected(quantum):
    with pytest.raises(ValueError, match="quantum"):
        compute_carry_next_day(D("1"), START, END, [], today=START, quantum=quantum)
    with pytest.raises(ValueError, match="end_date"):
        compute_carry_next_day(D("1"), END, START, [], today=START)


def test_exact_precision_quantization_and_rounding_residue():
    pool = D("0.123456789012345678")
    result = compute_carry_next_day(
        pool,
        START,
        date(2026, 7, 3),
        [],
        today=START,
        quantum=D("0.00000001"),
    )
    assert result.current_balance == pool
    assert result.daily_base_exact == quotient(str(pool), "3")
    assert result.daily_base == D("0.04115226")
    assert result.available_today == D("0.04115226")
    assert result.current_balance != result.daily_base * D("3")

    vnd = compute_carry_next_day(
        D("100"), START, date(2026, 7, 3), [], today=START, quantum=D("1")
    )
    assert vnd.daily_base == D("33")


def test_result_is_frozen_deterministic_and_policy_has_no_rebase_argument():
    inputs = (D("300"), START, date(2026, 7, 3), [effect(1, "-60")])
    first = compute_carry_next_day(*inputs, today=date(2026, 7, 2))
    second = compute_carry_next_day(*inputs, today=date(2026, 7, 2))
    assert first == second
    assert isinstance(first, AllowanceResult)
    with pytest.raises(FrozenInstanceError):
        first.carry_exact = D("0")
    assert "rebase_days" not in inspect.signature(compute_carry_next_day).parameters


def test_budget_module_has_no_database_or_framework_imports():
    source = Path("app/budget.py").read_text()
    imported_roots = {
        alias.name.split(".")[0]
        for node in ast.walk(ast.parse(source))
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert imported_roots.isdisjoint({"sqlalchemy", "fastapi", "pydantic", "app"})
