"""Pydantic v2 schemas for the FinApp v2 foundation API."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
