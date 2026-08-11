"""SQLAlchemy models for the FinApp v2 foundation."""

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
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
    __table_args__ = (UniqueConstraint("normalized_username"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    normalized_username: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
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
    __table_args__ = (UniqueConstraint("token_hash"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
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
    __table_args__ = (UniqueConstraint("code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
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
    manual_valuation_rates: Mapped[list["ManualValuationRate"]] = relationship(
        back_populates="workspace",
        cascade="all, delete-orphan",
        foreign_keys="ManualValuationRate.workspace_id",
    )
    exchange_rates: Mapped[list["ExchangeRate"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )


class ManualValuationRate(Base):
    __tablename__ = "manual_valuation_rate"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "main_asset_id",
            "asset_id",
            name="uq_manual_rate_workspace_pair",
        ),
        CheckConstraint(
            "direction IN ('asset_to_main', 'main_to_asset_legacy')",
            name="ck_manual_valuation_rate_direction",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False, index=True
    )
    main_asset_id: Mapped[int] = mapped_column(
        ForeignKey("asset.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("asset.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    rate_value: Mapped[Decimal] = mapped_column(ExactDecimal, nullable=False)
    direction: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    workspace: Mapped[Workspace] = relationship(
        back_populates="manual_valuation_rates", foreign_keys=[workspace_id]
    )
    main_asset: Mapped[Asset] = relationship(foreign_keys=[main_asset_id])
    asset: Mapped[Asset] = relationship(foreign_keys=[asset_id])


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
    periods: Mapped[list["AccountPeriod"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    operations_undo_states: Mapped[list["OperationsUndoState"]] = relationship(
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
    __table_args__ = (UniqueConstraint("token_hash"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("account.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    token_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
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
    __table_args__ = (
        CheckConstraint(
            "origin IN ('manual', 'operations')",
            name="ck_financial_transaction_origin",
        ),
    )

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
    parent_transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("financial_transaction.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    counterparty: Mapped[str | None] = mapped_column(String(160), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    local_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    origin: Mapped[str] = mapped_column(
        String(16), nullable=False, default="manual"
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="posted", index=True
    )
    external_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow
    )

    transaction: Mapped[Transaction] = relationship(back_populates="legs")
    account: Mapped[Account | None] = relationship(back_populates="legs")
    asset: Mapped[Asset] = relationship()


class ExchangeRate(Base):
    __tablename__ = "exchange_rate"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "source_transaction_id",
            "base_asset_id",
            "quote_asset_id",
            name="uq_exchange_rate_transaction_pair",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False, index=True
    )
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

    workspace: Mapped[Workspace] = relationship(back_populates="exchange_rates")
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
        UniqueConstraint("transaction_id"),
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
        index=True,
    )
    matched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    plan_rule: Mapped[PlanRule] = relationship(back_populates="occurrences")
    transaction: Mapped[Transaction | None] = relationship()


class AccountPeriod(Base):
    __tablename__ = "account_period"
    __table_args__ = (
        CheckConstraint(
            "end_date >= start_date", name="ck_account_period_date_order"
        ),
        CheckConstraint(
            "rollover_policy IN ('carry_next_day', "
            "'redistribute_remaining_days')",
            name="ck_account_period_rollover_policy",
        ),
        CheckConstraint(
            "(closed_at IS NULL AND closing_balance IS NULL) OR "
            "(closed_at IS NOT NULL AND closing_balance IS NOT NULL)",
            name="ck_account_period_closing_pair",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("account.id", ondelete="CASCADE"), nullable=False, index=True
    )
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("asset.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    end_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    snapshot_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    opening_balance: Mapped[Decimal] = mapped_column(ExactDecimal, nullable=False)
    rollover_policy: Mapped[str] = mapped_column(
        String(40), nullable=False, default="redistribute_remaining_days"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closing_balance: Mapped[Decimal | None] = mapped_column(ExactDecimal, nullable=True)

    account: Mapped[Account] = relationship(back_populates="periods")
    creator: Mapped[User] = relationship(foreign_keys=[created_by_user_id])
    asset: Mapped[Asset] = relationship(foreign_keys=[asset_id])
    rebase_events: Mapped[list["RebaseEvent"]] = relationship(
        back_populates="account_period", cascade="all, delete-orphan"
    )


class OperationsUndoState(Base):
    __tablename__ = "operations_undo_state"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "account_id", name="uq_operations_undo_state_user_account"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    account_id: Mapped[int] = mapped_column(
        ForeignKey("account.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cursor_transaction_id: Mapped[int] = mapped_column(
        ForeignKey("financial_transaction.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped[User] = relationship()
    account: Mapped[Account] = relationship(back_populates="operations_undo_states")
    cursor_transaction: Mapped[Transaction] = relationship()


class RebaseEvent(Base):
    __tablename__ = "rebase_event"
    __table_args__ = (
        UniqueConstraint("account_period_id", "day", name="uq_rebase_event_period_day"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_period_id: Mapped[int] = mapped_column(
        ForeignKey("account_period.id", ondelete="CASCADE"), nullable=False, index=True
    )
    day: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow
    )

    account_period: Mapped[AccountPeriod] = relationship(back_populates="rebase_events")
