"""SQLAlchemy models for the FinApp v2 foundation."""

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    """Naive UTC for SQLite's DateTime adapter."""
    return datetime.now(UTC).replace(tzinfo=None)


class ExactDecimal(TypeDecorator):
    """Exact Decimal storage: TEXT on SQLite, Numeric(38,18) elsewhere."""

    impl = Numeric(38, 18)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "sqlite":
            return dialect.type_descriptor(String(80))
        return dialect.type_descriptor(Numeric(38, 18))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        decimal = Decimal(value)
        return str(decimal) if dialect.name == "sqlite" else decimal

    def process_result_value(self, value, dialect):
        return None if value is None else Decimal(str(value))


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    normalized_username: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, default="Asia/Ho_Chi_Minh"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    sessions: Mapped[list["AuthSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    workspaces: Mapped[list["Workspace"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )
    account_accesses: Mapped[list["AccountAccess"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class AuthSession(Base):
    __tablename__ = "auth_session"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped[User] = relationship(back_populates="sessions")


class Asset(Base):
    __tablename__ = "asset"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(16), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    decimals: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Workspace(Base):
    __tablename__ = "workspace"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    base_asset_id: Mapped[int] = mapped_column(
        ForeignKey("asset.id", ondelete="RESTRICT"), nullable=False
    )
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    owner: Mapped[User] = relationship(back_populates="workspaces")
    base_asset: Mapped[Asset] = relationship()
    categories: Mapped[list["Category"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )
    accounts: Mapped[list["Account"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )
    plan_rules: Mapped[list["PlanRule"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )
    budget_periods: Mapped[list["BudgetPeriod"]] = relationship(
        back_populates="workspace",
        cascade="all, delete-orphan",
        foreign_keys="BudgetPeriod.workspace_id",
    )


class Category(Base):
    __tablename__ = "category"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "normalized_name", name="uq_category_workspace_name"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(100), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="expense")
    icon: Mapped[str | None] = mapped_column(String(32), nullable=True)
    color: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    workspace: Mapped[Workspace] = relationship(back_populates="categories")


class Account(Base):
    __tablename__ = "account"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "normalized_name", name="uq_account_workspace_name"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(100), nullable=False)
    storage_type: Mapped[str] = mapped_column(String(24), nullable=False)
    purpose: Mapped[str] = mapped_column(String(24), nullable=False)
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("asset.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    institution: Mapped[str | None] = mapped_column(String(100), nullable=True)
    include_in_available: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    workspace: Mapped[Workspace] = relationship(back_populates="accounts")
    owner: Mapped[User] = relationship()
    asset: Mapped[Asset] = relationship()
    legs: Mapped[list["TransactionLeg"]] = relationship(back_populates="account")
    accesses: Mapped[list["AccountAccess"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    invitations: Mapped[list["AccountInvitation"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )


class AccountAccess(Base):
    __tablename__ = "account_access"
    __table_args__ = (
        UniqueConstraint("account_id", "user_id", name="uq_account_access_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("account.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow
    )

    account: Mapped[Account] = relationship(back_populates="accesses")
    user: Mapped[User] = relationship(back_populates="account_accesses")


class AccountInvitation(Base):
    __tablename__ = "account_invitation"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("account.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    token_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    accepted_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )

    account: Mapped[Account] = relationship(back_populates="invitations")


class Transaction(Base):
    __tablename__ = "financial_transaction"

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("category.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    budget_period_id: Mapped[int | None] = mapped_column(
        ForeignKey("budget_period.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    parent_transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("financial_transaction.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    counterparty: Mapped[str | None] = mapped_column(String(160), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    local_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    source: Mapped[str] = mapped_column(
        String(16), nullable=False, default="manual"
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="posted", index=True
    )
    external_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    base_amount: Mapped[Decimal | None] = mapped_column(ExactDecimal, nullable=True)
    base_rate: Mapped[Decimal | None] = mapped_column(ExactDecimal, nullable=True)
    rate_source: Mapped[str | None] = mapped_column(String(24), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )
    voided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    workspace: Mapped[Workspace] = relationship(back_populates="transactions")
    creator: Mapped[User] = relationship()
    category: Mapped[Category | None] = relationship()
    parent: Mapped["Transaction | None"] = relationship(remote_side="Transaction.id")
    legs: Mapped[list["TransactionLeg"]] = relationship(
        back_populates="transaction", cascade="all, delete-orphan"
    )
    rates: Mapped[list["ExchangeRate"]] = relationship(
        back_populates="source_transaction", cascade="all, delete-orphan"
    )
    budget_period: Mapped["BudgetPeriod | None"] = relationship(
        back_populates="transactions", foreign_keys=[budget_period_id]
    )


class TransactionLeg(Base):
    __tablename__ = "transaction_leg"

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("financial_transaction.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    account_id: Mapped[int | None] = mapped_column(
        ForeignKey("account.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("asset.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(ExactDecimal, nullable=False)

    transaction: Mapped[Transaction] = relationship(back_populates="legs")
    account: Mapped[Account | None] = relationship(back_populates="legs")
    asset: Mapped[Asset] = relationship()


class ExchangeRate(Base):
    __tablename__ = "exchange_rate"
    __table_args__ = (
        UniqueConstraint(
            "source_transaction_id",
            "base_asset_id",
            "quote_asset_id",
            name="uq_exchange_rate_transaction_pair",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_transaction_id: Mapped[int] = mapped_column(
        ForeignKey("financial_transaction.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    base_asset_id: Mapped[int] = mapped_column(
        ForeignKey("asset.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quote_asset_id: Mapped[int] = mapped_column(
        ForeignKey("asset.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    rate: Mapped[Decimal] = mapped_column(ExactDecimal, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    source_transaction: Mapped[Transaction] = relationship(back_populates="rates")


class PlanRule(Base):
    __tablename__ = "plan_rule"

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    amount: Mapped[Decimal] = mapped_column(ExactDecimal, nullable=False)
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("asset.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    recurrence: Mapped[str] = mapped_column(String(16), nullable=False)
    first_due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("category.id", ondelete="RESTRICT"), nullable=True
    )
    default_from_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("account.id", ondelete="RESTRICT"), nullable=True
    )
    default_to_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("account.id", ondelete="RESTRICT"), nullable=True
    )
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    workspace: Mapped[Workspace] = relationship(back_populates="plan_rules")
    creator: Mapped[User] = relationship()
    asset: Mapped[Asset] = relationship()
    category: Mapped[Category | None] = relationship()
    default_from_account: Mapped[Account | None] = relationship(
        foreign_keys=[default_from_account_id]
    )
    default_to_account: Mapped[Account | None] = relationship(
        foreign_keys=[default_to_account_id]
    )
    occurrences: Mapped[list["PlanOccurrence"]] = relationship(
        back_populates="plan_rule", cascade="all, delete-orphan"
    )


class PlanOccurrence(Base):
    __tablename__ = "plan_occurrence"
    __table_args__ = (
        UniqueConstraint("plan_rule_id", "due_date", name="uq_plan_occurrence_rule_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_rule_id: Mapped[int] = mapped_column(
        ForeignKey("plan_rule.id", ondelete="CASCADE"), nullable=False, index=True
    )
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    planned_amount: Mapped[Decimal] = mapped_column(ExactDecimal, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="planned", index=True)
    transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("financial_transaction.id", ondelete="RESTRICT"),
        nullable=True,
        unique=True,
        index=True,
    )
    matched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    plan_rule: Mapped[PlanRule] = relationship(back_populates="occurrences")
    transaction: Mapped[Transaction | None] = relationship()
    commitments: Mapped[list["BudgetCommitment"]] = relationship(
        back_populates="plan_occurrence"
    )


class BudgetPeriod(Base):
    __tablename__ = "budget_period"

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    end_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    base_asset_id: Mapped[int] = mapped_column(
        ForeignKey("asset.id", ondelete="RESTRICT"), nullable=False
    )
    funding_amount: Mapped[Decimal] = mapped_column(ExactDecimal, nullable=False)
    opening_transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("financial_transaction.id", ondelete="RESTRICT"),
        nullable=True,
        unique=True,
    )
    opening_plan_occurrence_id: Mapped[int | None] = mapped_column(
        ForeignKey("plan_occurrence.id", ondelete="RESTRICT"),
        nullable=True,
        unique=True,
    )
    prompt_ack_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    workspace: Mapped[Workspace] = relationship(
        back_populates="budget_periods", foreign_keys=[workspace_id]
    )
    creator: Mapped[User] = relationship(foreign_keys=[created_by_user_id])
    base_asset: Mapped[Asset] = relationship(foreign_keys=[base_asset_id])
    opening_transaction: Mapped[Transaction | None] = relationship(
        foreign_keys=[opening_transaction_id]
    )
    opening_plan_occurrence: Mapped[PlanOccurrence | None] = relationship(
        foreign_keys=[opening_plan_occurrence_id]
    )
    transactions: Mapped[list[Transaction]] = relationship(
        back_populates="budget_period", foreign_keys="Transaction.budget_period_id"
    )
    commitments: Mapped[list["BudgetCommitment"]] = relationship(
        back_populates="budget_period", cascade="all, delete-orphan"
    )
    rebase_events: Mapped[list["RebaseEvent"]] = relationship(
        back_populates="budget_period", cascade="all, delete-orphan"
    )


class BudgetCommitment(Base):
    __tablename__ = "budget_commitment"
    __table_args__ = (
        UniqueConstraint(
            "budget_period_id",
            "plan_occurrence_id",
            name="uq_budget_commitment_period_occurrence",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    budget_period_id: Mapped[int] = mapped_column(
        ForeignKey("budget_period.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plan_occurrence_id: Mapped[int] = mapped_column(
        ForeignKey("plan_occurrence.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(24), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    planned_amount: Mapped[Decimal] = mapped_column(ExactDecimal, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="reserved", index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    budget_period: Mapped[BudgetPeriod] = relationship(back_populates="commitments")
    plan_occurrence: Mapped[PlanOccurrence] = relationship(back_populates="commitments")


class RebaseEvent(Base):
    __tablename__ = "rebase_event"
    __table_args__ = (
        UniqueConstraint("budget_period_id", "day", name="uq_rebase_event_period_day"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    budget_period_id: Mapped[int] = mapped_column(
        ForeignKey("budget_period.id", ondelete="CASCADE"), nullable=False, index=True
    )
    day: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow
    )

    budget_period: Mapped[BudgetPeriod] = relationship(back_populates="rebase_events")
