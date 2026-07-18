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


class UnvaluedAssetOut(BaseModel):
    asset: AssetOut
    total: Decimal


class AccountSummaryOut(BaseModel):
    base_asset: AssetOut
    net_worth: Decimal
    available: Decimal
    accounts: list[AccountOut]
    unvalued: list[UnvaluedAssetOut]


class TransactionLegOut(BaseModel):
    id: int
    account_id: int | None
    asset: AssetOut
    amount: Decimal


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
    source: Literal["manual", "planned"]
    status: Literal["posted", "unassigned", "voided"]
    base_amount: Decimal | None
    base_rate: Decimal | None
    rate_source: str | None
    created_at: datetime
    updated_at: datetime
    voided_at: datetime | None
    legs: list[TransactionLegOut]
    has_hidden_legs: bool = False


class TransactionCommon(BaseModel):
    category_id: int | None = None
    counterparty: str | None = Field(default=None, max_length=160)
    note: str | None = Field(default=None, max_length=2000)
    occurred_at: datetime | None = None
    local_date: date | None = None


class SingleTransactionIn(TransactionCommon):
    account_id: int | None = None
    asset_code: str | None = Field(default=None, min_length=2, max_length=16)
    amount: PositiveAmount

    @field_validator("asset_code")
    @classmethod
    def normalize_asset_code(cls, value: str | None) -> str | None:
        return value.strip().upper() if value is not None else None


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


class AdjustmentIn(TransactionCommon):
    account_id: int
    delta: DecimalAmount


class AssignAccountIn(BaseModel):
    account_id: int


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
