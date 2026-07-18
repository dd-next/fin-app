from datetime import date

import pytest

from app.recurrence import add_months, add_years, occurrence_dates


def test_monthly_recurrence_clamps_from_original_anchor():
    assert occurrence_dates(date(2026, 1, 31), "monthly", date(2026, 5, 31)) == [
        date(2026, 1, 31),
        date(2026, 2, 28),
        date(2026, 3, 31),
        date(2026, 4, 30),
        date(2026, 5, 31),
    ]
    assert add_months(date(2026, 12, 31), 2) == date(2027, 2, 28)


def test_yearly_leap_anchor_recovers_february_29():
    assert occurrence_dates(date(2024, 2, 29), "yearly", date(2028, 3, 1)) == [
        date(2024, 2, 29),
        date(2025, 2, 28),
        date(2026, 2, 28),
        date(2027, 2, 28),
        date(2028, 2, 29),
    ]
    assert add_years(date(2024, 2, 29), 4) == date(2028, 2, 29)


def test_once_weekly_and_invalid_recurrence():
    assert occurrence_dates(date(2026, 7, 1), "once", date(2027, 7, 1)) == [
        date(2026, 7, 1)
    ]
    assert occurrence_dates(date(2026, 7, 1), "weekly", date(2026, 7, 15)) == [
        date(2026, 7, 1),
        date(2026, 7, 8),
        date(2026, 7, 15),
    ]
    assert occurrence_dates(date(2027, 1, 1), "monthly", date(2026, 1, 1)) == []
    with pytest.raises(ValueError):
        occurrence_dates(date(2026, 1, 1), "daily", date(2026, 1, 2))
