import ast
from dataclasses import FrozenInstanceError
from datetime import date
from decimal import Decimal, localcontext
from pathlib import Path

import pytest

from app.budget import (
    AllowanceResult,
    compute_allowance,
    compute_carry_next_day,
    compute_redistribute_remaining_days,
)


D = Decimal
START = date(2026, 7, 1)
END = date(2026, 7, 10)


def effect(day: int, amount: str):
    return date(2026, 7, day), D(amount)


def quotient(value: str, divisor: str):
    with localcontext() as context:
        context.prec = 100
        return D(value) / D(divisor)


def add_exact(value: Decimal, delta: str):
    with localcontext() as context:
        context.prec = 100
        return value + D(delta)


def test_canonical_day_two_redistributes_instead_of_carrying():
    effects = [effect(1, "-60")]
    today = date(2026, 7, 2)
    redistributed = compute_redistribute_remaining_days(
        D("1000"), START, END, effects, today=today
    )
    carried = compute_carry_next_day(D("1000"), START, END, effects, today=today)
    assert redistributed.current_balance == D("940")
    assert redistributed.daily_base_exact == quotient("940", "9")
    assert redistributed.carry_exact == D("0")
    assert redistributed.available_today_exact == quotient("940", "9")
    assert carried.available_today_exact == D("140")


def test_current_day_outflow_and_income_are_applied_exactly_once():
    prior = effect(1, "-60")
    outflow = compute_redistribute_remaining_days(
        D("1000"), START, END, [prior, effect(2, "-40")],
        today=date(2026, 7, 2),
    )
    base = quotient("940", "9")
    assert outflow.current_balance == D("900")
    assert outflow.today_net == D("-40")
    assert outflow.daily_base_exact == base
    assert outflow.available_today_exact == add_exact(base, "-40")

    income = compute_redistribute_remaining_days(
        D("1000"), START, END, [prior, effect(2, "200")],
        today=date(2026, 7, 2),
    )
    assert income.current_balance == D("1140")
    assert income.daily_base_exact == base
    assert income.available_today_exact == add_exact(base, "200")


def test_each_new_day_freshly_rebases_after_under_and_overspend():
    underspent_day_two = compute_redistribute_remaining_days(
        D("1000"), START, END, [effect(1, "-60")],
        today=date(2026, 7, 2),
    )
    underspent_day_three = compute_redistribute_remaining_days(
        D("1000"), START, END, [effect(1, "-60")],
        today=date(2026, 7, 3),
    )
    assert underspent_day_two.daily_base_exact == quotient("940", "9")
    assert underspent_day_three.daily_base_exact == D("117.5")

    overspent_day_two = compute_redistribute_remaining_days(
        D("1000"), START, END, [effect(1, "-200")],
        today=date(2026, 7, 2),
    )
    overspent_day_three = compute_redistribute_remaining_days(
        D("1000"), START, END,
        [effect(1, "-200"), effect(2, "-100")],
        today=date(2026, 7, 3),
    )
    assert overspent_day_two.daily_base_exact == quotient("800", "9")
    assert overspent_day_three.daily_base_exact == D("87.5")


def test_final_day_exposes_complete_exact_balance_and_rounding_residue():
    pool = D("0.123456789012345678")
    result = compute_redistribute_remaining_days(
        pool,
        START,
        date(2026, 7, 3),
        [],
        today=date(2026, 7, 3),
        quantum=D("0.00000001"),
    )
    assert result.days_remaining == 1
    assert result.current_balance == pool
    assert result.available_today_exact == pool
    assert result.available_today == D("0.12345679")
    assert result.current_balance != result.available_today


def test_negative_one_day_and_reference_bounds_are_not_clamped_to_zero():
    negative = compute_redistribute_remaining_days(
        D("-90"), START, date(2026, 7, 3), [], today=date(2026, 7, 2)
    )
    assert negative.daily_base_exact == D("-45")
    assert negative.available_today_exact == D("-45")

    one_day = compute_redistribute_remaining_days(
        D("50"), START, START, [effect(1, "-60")], today=START
    )
    assert one_day.days_remaining == 1
    assert one_day.current_balance == one_day.available_today_exact == D("-10")

    before = compute_redistribute_remaining_days(
        D("1000"), START, END, [], today=date(2026, 6, 1)
    )
    after = compute_redistribute_remaining_days(
        D("1000"), START, END, [], today=date(2027, 1, 1)
    )
    assert before.days_remaining == 10
    assert before.available_today_exact == D("100")
    assert after.days_remaining == 1
    assert after.available_today_exact == D("1000")


def test_dispatch_default_both_policies_and_unknown_value():
    inputs = (D("1000"), START, END, [effect(1, "-60")])
    today = date(2026, 7, 2)
    direct_redistributed = compute_redistribute_remaining_days(*inputs, today=today)
    assert compute_allowance(*inputs, today=today) == direct_redistributed
    assert compute_allowance(
        *inputs, rollover_policy="redistribute_remaining_days", today=today
    ) == direct_redistributed
    assert compute_allowance(
        *inputs, rollover_policy="carry_next_day", today=today
    ) == compute_carry_next_day(*inputs, today=today)
    with pytest.raises(ValueError, match="Unknown rollover_policy"):
        compute_allowance(*inputs, rollover_policy="unknown", today=today)


@pytest.mark.parametrize(
    "call",
    [
        lambda: compute_redistribute_remaining_days(
            D("1"), END, START, [], today=START
        ),
        lambda: compute_redistribute_remaining_days(
            D("1"), START, END, [effect(2, "1")], today=START
        ),
        lambda: compute_redistribute_remaining_days(
            D("1"), START, END, [], today=START, quantum=D("0.05")
        ),
    ],
)
def test_shared_validation_is_enforced(call):
    with pytest.raises(ValueError):
        call()


def test_vnd_and_btc_presentation_fields_do_not_change_exact_values():
    vnd = compute_redistribute_remaining_days(
        D("100"), START, date(2026, 7, 3), [], today=START, quantum=D("1")
    )
    btc = compute_redistribute_remaining_days(
        D("0.00000010"), START, date(2026, 7, 3), [],
        today=START, quantum=D("0.00000001"),
    )
    assert vnd.daily_base_exact == quotient("100", "3")
    assert vnd.daily_base == D("33")
    assert btc.daily_base_exact == quotient("0.00000010", "3")
    assert btc.daily_base == D("0.00000003")
    assert btc.current_balance == D("0.00000010")


def test_dispatch_result_is_frozen_deterministic_and_module_stays_pure():
    inputs = (D("1000"), START, END, [effect(1, "-60")])
    first = compute_allowance(*inputs, today=date(2026, 7, 2))
    second = compute_allowance(*inputs, today=date(2026, 7, 2))
    assert first == second
    assert isinstance(first, AllowanceResult)
    with pytest.raises(FrozenInstanceError):
        first.carry_exact = D("1")

    source = Path("app/budget.py").read_text()
    imported_roots = {
        alias.name.split(".")[0]
        for node in ast.walk(ast.parse(source))
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert imported_roots.isdisjoint({"sqlalchemy", "fastapi", "pydantic", "app"})
