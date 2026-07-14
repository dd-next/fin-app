"""Pydantic v2 schemas for the API."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Money parses as Decimal with at most 2 decimal places; malformed input → 422.
MoneyIn = Annotated[Decimal, Field(max_digits=12, decimal_places=2)]


class PeriodIn(BaseModel):
    total_amount: MoneyIn
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def check_dates(self) -> "PeriodIn":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be >= start_date")
        return self


class ExpenseIn(BaseModel):
    amount: MoneyIn
    comment: str | None = None


class PeriodOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    total_amount: Decimal
    start_date: date
    end_date: date
    created_at: datetime


class ExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    amount: Decimal
    comment: str | None
    created_at: datetime


class BudgetOut(BaseModel):
    days_total: int
    days_remaining: int
    spent_total: Decimal
    remaining_money: Decimal
    daily_base: Decimal
    budget_today: Decimal
    spent_today: Decimal
    per_day_today: Decimal
    next_daily: Decimal
    preview_after: Decimal | None = None


class PeriodWithBudget(BaseModel):
    period: PeriodOut
    budget: BudgetOut


class ExpenseWithBudget(BaseModel):
    expense: ExpenseOut
    budget: BudgetOut
