"""Pydantic v2 schemas for the API."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Money parses as Decimal with at most 2 decimal places; malformed input → 422.
MoneyIn = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]

# Operations are signed by kind, not by the amount (which stays positive).
OperationKind = Literal[
    "expense", "income", "transfer_to_goal", "transfer_from_goal"
]


class LoginIn(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[^\s]+$")
    password: str = Field(min_length=10, max_length=256)


class BootstrapIn(LoginIn):
    display_name: str | None = Field(default=None, min_length=1, max_length=100)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class WorkspaceOut(BaseModel):
    id: int
    name: str
    kind: Literal["personal", "shared"]
    timezone: str
    role: Literal["owner", "editor"]


class WorkspaceInviteOut(BaseModel):
    token: str
    workspace_id: int
    expires_at: datetime


class WorkspaceMemberOut(BaseModel):
    user: UserOut
    role: Literal["owner", "editor"]
    joined_at: datetime


class InviteAcceptanceOut(BaseModel):
    user: UserOut
    workspace: WorkspaceOut


class PeriodIn(BaseModel):
    total_amount: MoneyIn
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def check_dates(self) -> "PeriodIn":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be >= start_date")
        return self


class PeriodPatch(BaseModel):
    total_amount: MoneyIn | None = None
    start_date: date | None = None
    end_date: date | None = None


class OperationIn(BaseModel):
    amount: MoneyIn
    kind: OperationKind = "expense"
    comment: str | None = None
    occurred_on: date | None = None
    category_id: int | None = None
    savings_goal_id: int | None = None


class PeriodOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    total_amount: Decimal
    start_date: date
    end_date: date
    created_at: datetime
    status: Literal["upcoming", "current", "ended"]


class OperationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    period_id: int
    category_id: int | None
    created_by_user_id: int | None
    savings_goal_id: int | None
    amount: Decimal
    kind: OperationKind
    comment: str | None
    occurred_on: date
    created_at: datetime


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class CategoryPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    archived: bool | None = None


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    name: str
    archived_at: datetime | None


class CategoryPlanIn(BaseModel):
    limit_amount: MoneyIn | None = None
    pool_plan_id: int | None = None


class CategoryPlanOut(BaseModel):
    category: CategoryOut
    limit_amount: Decimal | None
    spent: Decimal
    remaining: Decimal | None
    over_limit: bool
    pool_plan_id: int | None


class PoolCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class PoolPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    archived: bool | None = None


class PoolOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    name: str
    archived_at: datetime | None


class PoolPlanIn(BaseModel):
    allocated_amount: MoneyIn


class PoolPlanOut(BaseModel):
    id: int
    pool: PoolOut
    allocated_amount: Decimal
    spent: Decimal
    remaining: Decimal
    over_limit: bool


class SavingsGoalCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    target_amount: MoneyIn
    target_date: date | None = None


class SavingsGoalPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    target_amount: MoneyIn | None = None
    target_date: date | None = None
    archived: bool | None = None


class SavingsGoalOut(BaseModel):
    id: int
    workspace_id: int
    name: str
    target_amount: Decimal
    target_date: date | None
    balance: Decimal
    remaining: Decimal
    completed: bool
    archived_at: datetime | None


class GoalPlanIn(BaseModel):
    planned_amount: MoneyIn


class GoalPlanOut(BaseModel):
    id: int
    goal: SavingsGoalOut
    planned_amount: Decimal
    contributed: Decimal
    remaining: Decimal
    over_plan: bool


class LimitWarning(BaseModel):
    scope: Literal["category", "pool", "goal"]
    target_id: int
    name: str
    limit_amount: Decimal
    spent: Decimal
    over_by: Decimal


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


class SavingsPromptOut(BaseModel):
    """Next-day savings decision. When show is False the value fields are
    omitted from the response."""

    show: bool
    saved: Decimal | None = None
    spend_today_value: Decimal | None = None  # today's number if it rolls over
    increase_daily_value: Decimal | None = None  # new daily base if re-spread


class SavingsDecisionIn(BaseModel):
    choice: Literal["spend_today", "increase_daily"]


class PeriodWithBudget(BaseModel):
    period: PeriodOut
    budget: BudgetOut


class OperationWithBudget(BaseModel):
    operation: OperationOut
    budget: BudgetOut
    warnings: list[LimitWarning] = Field(default_factory=list)
