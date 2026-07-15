"""SQLAlchemy models: period and operation (expense or income).

The operation table is still named "expense" for historical reasons; the
`kind` column ('expense' | 'income') generalizes it. Amounts are stored
positive; `kind` carries the sign."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, TypeDecorator
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


class Base(DeclarativeBase):
    pass


class Period(Base):
    __tablename__ = "period"

    id: Mapped[int] = mapped_column(primary_key=True)
    total_amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=localnow, nullable=False)

    operations: Mapped[list["Operation"]] = relationship(
        back_populates="period", cascade="all, delete-orphan", passive_deletes=True
    )


class Operation(Base):
    __tablename__ = "expense"  # historical name; rows are expenses AND incomes

    id: Mapped[int] = mapped_column(primary_key=True)
    period_id: Mapped[int] = mapped_column(
        ForeignKey("period.id", ondelete="CASCADE"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    kind: Mapped[str] = mapped_column(
        String(10), nullable=False, default="expense", server_default="expense"
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=localnow, nullable=False)

    period: Mapped[Period] = relationship(back_populates="operations")

    @property
    def signed_amount(self) -> Decimal:
        """How much this operation takes from the pool: incomes are negative
        spending, which is exactly how the budget replay consumes them."""
        return -self.amount if self.kind == "income" else self.amount
