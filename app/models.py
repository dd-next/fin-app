"""SQLAlchemy models for FinApp's workspace-scoped budget ledger."""

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, TypeDecorator
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Money(TypeDecorator):
    """Exact Decimal storage. Numeric(12,2) on real databases; TEXT on SQLite
    (whose NUMERIC affinity is floating point and would lose exactness)."""

    impl = Numeric(12, 2)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "sqlite":
            return dialect.type_descriptor(String(32))
        return dialect.type_descriptor(Numeric(12, 2))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return str(Decimal(value)) if dialect.name == "sqlite" else value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return Decimal(str(value))


def localnow() -> datetime:
    # Local (not UTC) on purpose: the budget math works in local calendar
    # days (`date.today()`), so "the day the expense was entered" must be
    # the local day too, or dates disagree around midnight.
    return datetime.now()


def utcnow() -> datetime:
    # SQLAlchemy's current SQLite DateTime adapter is naive; keep a naive UTC
    # value while avoiding deprecated datetime.utcnow().
    return datetime.now(UTC).replace(tzinfo=None)


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


class Workspace(Base):
    """A personal or shared financial space.

    Phase 1 creates one legacy personal workspace. Membership and users are
    added in later phases without moving periods again.
    """

    __tablename__ = "workspace"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="personal")
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, default="Asia/Ho_Chi_Minh"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=localnow, nullable=False
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    periods: Mapped[list["Period"]] = relationship(back_populates="workspace")


class Period(Base):
    __tablename__ = "period"

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspace.id", ondelete="RESTRICT"),
        nullable=False,
        default=1,
        server_default="1",
    )
    total_amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=localnow, nullable=False)
    # Last local day the next-day savings prompt was answered (either choice).
    prompt_ack_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    workspace: Mapped[Workspace] = relationship(back_populates="periods")
    operations: Mapped[list["Operation"]] = relationship(
        back_populates="period", cascade="all, delete-orphan", passive_deletes=True
    )
    rebase_events: Mapped[list["RebaseEvent"]] = relationship(
        back_populates="period", cascade="all, delete-orphan", passive_deletes=True
    )

    @property
    def status(self) -> str:
        today = date.today()
        if today < self.start_date:
            return "upcoming"
        if today > self.end_date:
            return "ended"
        return "current"


class Operation(Base):
    __tablename__ = "operation"

    id: Mapped[int] = mapped_column(primary_key=True)
    period_id: Mapped[int] = mapped_column(
        ForeignKey("period.id", ondelete="CASCADE"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    kind: Mapped[str] = mapped_column(
        String(10), nullable=False, default="expense", server_default="expense"
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The financial/calendar day used by budget replay. It is intentionally
    # separate from created_at so historical corrections remain deterministic.
    occurred_on: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=localnow, nullable=False)

    period: Mapped[Period] = relationship(back_populates="operations")

    @property
    def signed_amount(self) -> Decimal:
        """How much this operation takes from the pool: incomes are negative
        spending, which is exactly how the budget replay consumes them."""
        return -self.amount if self.kind == "income" else self.amount


class RebaseEvent(Base):
    """A user-chosen "increase the daily budget" day: the replay re-spreads
    the remaining money evenly from this day on and resets the carry-over.
    Stored as a record so the numbers stay a pure function of the DB."""

    __tablename__ = "rebase_event"

    id: Mapped[int] = mapped_column(primary_key=True)
    period_id: Mapped[int] = mapped_column(
        ForeignKey("period.id", ondelete="CASCADE"), nullable=False
    )
    day: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=localnow, nullable=False)

    period: Mapped[Period] = relationship(back_populates="rebase_events")
