"""Pydantic v2 schemas for the FinApp v2 foundation API."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


DecimalAmount = Annotated[Decimal, Field(max_digits=38, decimal_places=18)]
PositiveAmount = Annotated[
    Decimal, Field(gt=0, max_digits=38, decimal_places=18)
]


class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[^\s]+$")
    password: str = Field(min_length=10, max_length=256)
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    timezone: str = Field(default="Asia/Ho_Chi_Minh", min_length=1, max_length=64)
    base_asset_code: str = Field(default="USD", min_length=2, max_length=16)

    @field_validator("base_asset_code")
    @classmethod
    def normalize_asset_code(cls, value: str) -> str:
        return value.strip().upper()


class LoginIn(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[^\s]+$")
    password: str = Field(min_length=10, max_length=256)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    timezone: str


class AssetCreate(BaseModel):
    code: str = Field(min_length=2, max_length=16, pattern=r"^[A-Za-z0-9._-]+$")
    name: str = Field(min_length=1, max_length=100)
    kind: Literal["fiat", "crypto"]
    decimals: int = Field(ge=0, le=18)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    kind: Literal["fiat", "crypto"]
    decimals: int
    is_active: bool


class WorkspaceOut(BaseModel):
    id: int
    owner_user_id: int
    name: str
    timezone: str
    base_asset: AssetOut
    created_at: datetime


class WorkspacePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    base_asset_code: str | None = Field(default=None, min_length=2, max_length=16)

    @field_validator("base_asset_code")
    @classmethod
    def normalize_asset_code(cls, value: str | None) -> str | None:
        return value.strip().upper() if value is not None else None


class ManualValuationRateUpsert(BaseModel):
    displayed_rate: PositiveAmount


class ManualValuationRateOut(BaseModel):
    id: int
    workspace_id: int
    main_asset: AssetOut
    asset: AssetOut
    displayed_rate: Decimal
    effective_valuation_rate: Decimal
    active: bool
    created_at: datetime
    updated_at: datetime


class AuthContextOut(BaseModel):
    user: UserOut
    workspace: WorkspaceOut


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    kind: Literal["expense", "income", "both"] = "expense"
    icon: str | None = Field(default=None, max_length=32)
    color: str | None = Field(default=None, max_length=16)


class CategoryPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    kind: Literal["expense", "income", "both"] | None = None
    icon: str | None = Field(default=None, max_length=32)
    color: str | None = Field(default=None, max_length=16)
    archived: bool | None = None


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    name: str
    kind: Literal["expense", "income", "both"]
    icon: str | None
    color: str | None
    archived_at: datetime | None


StorageType = Literal[
    "cash", "bank", "card", "e_wallet", "crypto_wallet", "exchange", "virtual"
]
AccountPurpose = Literal["spending", "reserve", "savings", "investment"]


class AccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    storage_type: StorageType
    purpose: AccountPurpose = "spending"
    asset_code: str = Field(min_length=2, max_length=16)
    institution: str | None = Field(default=None, max_length=100)
    include_in_available: bool = True
    opening_balance: DecimalAmount = Decimal("0")

    @field_validator("asset_code")
    @classmethod
    def normalize_asset_code(cls, value: str) -> str:
        return value.strip().upper()


class AccountPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    storage_type: StorageType | None = None
    purpose: AccountPurpose | None = None
    institution: str | None = Field(default=None, max_length=100)
    include_in_available: bool | None = None


class ReconcileIn(BaseModel):
    target_balance: DecimalAmount
    note: str | None = Field(default=None, max_length=500)


class AccountOut(BaseModel):
    id: int
    workspace_id: int
    owner_user_id: int
    name: str
    storage_type: StorageType
    purpose: AccountPurpose
    asset: AssetOut
    institution: str | None
    include_in_available: bool
    balance: Decimal
    valued_balance: Decimal | None
    archived_at: datetime | None
    access_role: Literal["owner", "editor", "contributor", "viewer"] = "owner"
    is_shared: bool = False


class UnvaluedAssetOut(BaseModel):
    asset: AssetOut
    total: Decimal


class AccountSummaryOut(BaseModel):
    base_asset: AssetOut
    net_worth: Decimal
    available: Decimal
    accounts: list[AccountOut]
    unvalued: list[UnvaluedAssetOut]


class AccountPeriodCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_date: date | None = None
    end_date: date
    rollover_policy: Literal[
        "carry_next_day", "redistribute_remaining_days"
    ] | None = None
    funding_amount: DecimalAmount | None = None


class AccountPeriodPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_date: date | None = None
    end_date: date | None = None
    rollover_policy: Literal[
        "carry_next_day", "redistribute_remaining_days"
    ] | None = None
    funding_amount: object | None = None
    confirm_ended_period: bool = False


class AccountPeriodCommonOut(BaseModel):
    id: int
    account_id: int
    asset: AssetOut
    created_by_user_id: int
    start_date: date
    end_date: date
    snapshot_at: datetime
    opening_balance: Decimal
    rollover_policy: Literal["carry_next_day", "redistribute_remaining_days"]
    funding_amount: Decimal
    planned: Decimal
    created_at: datetime


class AccountPeriodCurrentOut(AccountPeriodCommonOut):
    status: Literal["current"]
    closed_at: None = None
    closing_balance: None = None
    current_balance: Decimal
    available_today: Decimal
    remaining: Decimal


class AccountPeriodEndedOut(AccountPeriodCommonOut):
    status: Literal["ended"]
    closed_at: None = None
    closing_balance: None = None
    remaining: None = None


class AccountPeriodClosedOut(AccountPeriodCommonOut):
    status: Literal["closed"]
    closed_at: datetime
    closing_balance: Decimal
    remaining: Decimal


AccountPeriodOut = (
    AccountPeriodCurrentOut | AccountPeriodEndedOut | AccountPeriodClosedOut
)


class TransactionLegOut(BaseModel):
    id: int
    account_id: int | None
    asset: AssetOut
    amount: Decimal
    created_at: datetime


class TransactionOut(BaseModel):
    id: int
    workspace_id: int
    created_by_user_id: int
    type: Literal["expense", "income", "transfer", "exchange", "adjustment"]
    category_id: int | None
    parent_transaction_id: int | None
    counterparty: str | None
    note: str | None
    occurred_at: datetime
    local_date: date
    origin: Literal["manual", "operations"]
    status: Literal["posted", "unassigned", "deleted"]
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    legs: list[TransactionLegOut]
    has_hidden_legs: bool = False
    plan_occurrence_id: int | None = None


class TransactionCommon(BaseModel):
    category_id: int | None = None
    counterparty: str | None = Field(default=None, max_length=160)
    note: str | None = Field(default=None, max_length=2000)
    occurred_at: datetime | None = None
    local_date: date | None = None
    confirm_ended_period: bool = False


class SingleTransactionIn(TransactionCommon):
    account_id: int | None = None
    asset_code: str | None = Field(default=None, min_length=2, max_length=16)
    amount: PositiveAmount

    @field_validator("asset_code")
    @classmethod
    def normalize_asset_code(cls, value: str | None) -> str | None:
        return value.strip().upper() if value is not None else None


class OperationsSingleIn(TransactionCommon):
    account_id: int
    amount: PositiveAmount


class TransferIn(TransactionCommon):
    from_account_id: int
    to_account_id: int
    amount: PositiveAmount


class FeeIn(BaseModel):
    account_id: int
    amount: PositiveAmount
    category_id: int | None = None
    note: str | None = Field(default=None, max_length=2000)


class ExchangeIn(TransactionCommon):
    from_account_id: int
    from_amount: PositiveAmount
    to_account_id: int
    to_amount: PositiveAmount
    fee: FeeIn | None = None


class AssignAccountIn(BaseModel):
    account_id: int
    confirm_ended_period: bool = False


class TransactionPatch(BaseModel):
    category_id: int | None = None
    counterparty: str | None = Field(default=None, max_length=160)
    note: str | None = Field(default=None, max_length=2000)
    occurred_at: datetime | None = None
    local_date: date | None = None
    account_id: int | None = None
    asset_code: str | None = Field(default=None, min_length=2, max_length=16)
    amount: PositiveAmount | None = None
    delta: DecimalAmount | None = None
    from_account_id: int | None = None
    to_account_id: int | None = None
    from_amount: PositiveAmount | None = None
    to_amount: PositiveAmount | None = None
    confirm_ended_period: bool = False

    @field_validator("asset_code")
    @classmethod
    def normalize_asset_code(cls, value: str | None) -> str | None:
        return value.strip().upper() if value is not None else None


class ExchangeRateOut(BaseModel):
    base_asset: AssetOut
    quote_asset: AssetOut
    rate: Decimal
    captured_at: datetime
    source_transaction_id: int


class TransactionPageOut(BaseModel):
    items: list[TransactionOut]
    next_cursor: int | None


SharedRole = Literal["editor", "contributor", "viewer"]


class AccountInvitationCreate(BaseModel):
    role: SharedRole


class AccountInvitationOut(BaseModel):
    token: str
    account_id: int
    role: SharedRole
    expires_at: datetime


class AccountAccessPatch(BaseModel):
    role: SharedRole


class AccountAccessOut(BaseModel):
    account_id: int
    user: UserOut
    role: Literal["owner", "editor", "contributor", "viewer"]
    created_at: datetime | None


PlanKind = Literal[
    "income",
    "required_expense",
    "subscription",
    "reserve_transfer",
    "other_expense",
]
Recurrence = Literal["once", "weekly", "monthly", "yearly"]


class PlanRuleCreate(BaseModel):
    kind: PlanKind
    name: str = Field(min_length=1, max_length=120)
    amount: PositiveAmount
    asset_code: str = Field(min_length=2, max_length=16)
    recurrence: Recurrence = "once"
    first_due_date: date
    category_id: int | None = None
    default_from_account_id: int | None = None
    default_to_account_id: int | None = None
    is_required: bool = False

    @field_validator("asset_code")
    @classmethod
    def normalize_plan_asset_code(cls, value: str) -> str:
        return value.strip().upper()


class PlanRulePatch(BaseModel):
    kind: PlanKind | None = None
    name: str | None = Field(default=None, min_length=1, max_length=120)
    amount: PositiveAmount | None = None
    asset_code: str | None = Field(default=None, min_length=2, max_length=16)
    recurrence: Recurrence | None = None
    first_due_date: date | None = None
    category_id: int | None = None
    default_from_account_id: int | None = None
    default_to_account_id: int | None = None
    is_required: bool | None = None

    @field_validator("asset_code")
    @classmethod
    def normalize_plan_patch_asset_code(cls, value: str | None) -> str | None:
        return value.strip().upper() if value is not None else None


class PlanRuleOut(BaseModel):
    id: int
    workspace_id: int
    created_by_user_id: int
    kind: PlanKind
    name: str
    amount: Decimal
    asset: AssetOut
    recurrence: Recurrence
    first_due_date: date
    category_id: int | None
    default_from_account_id: int | None
    default_to_account_id: int | None
    is_required: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PlanOccurrenceOut(BaseModel):
    id: int
    plan_rule_id: int
    due_date: date
    planned_amount: Decimal
    status: Literal["planned", "completed", "skipped", "overdue"]
    transaction_id: int | None
    actual_amount: Decimal | None
    actual_asset: AssetOut | None
    matched_at: datetime | None
    created_at: datetime
    rule: PlanRuleOut


class PlanLinkTransactionIn(BaseModel):
    transaction_id: int


class TransactionLinkPlanIn(BaseModel):
    occurrence_id: int


class DeleteTransactionIn(BaseModel):
    confirm_ended_period: bool = False


class OperationsUndoIn(DeleteTransactionIn):
    transaction_id: int
