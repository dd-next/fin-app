"""Replace editable period funding with exact ledger snapshots.

Revision ID: 0002_period_snapshot_model
Revises: 0001_release_v2
"""

from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from alembic import op
import sqlalchemy as sa


revision: str = "0002_period_snapshot_model"
down_revision: str | None = "0001_release_v2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_ROLLOVER_POLICY = "redistribute_remaining_days"


def _money_type(connection: sa.Connection) -> sa.types.TypeEngine:
    if connection.dialect.name == "sqlite":
        return sa.String(80)
    return sa.Numeric(38, 18)


def _as_date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _as_naive_utc(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(UTC).replace(tzinfo=None)
    return parsed


def _local_boundary(day: date, timezone: ZoneInfo) -> datetime:
    return datetime.combine(day, time.min, tzinfo=timezone).astimezone(UTC).replace(
        tzinfo=None
    )


def _ledger_balance(
    connection: sa.Connection, account_id: int, boundary: datetime
) -> Decimal:
    amounts = connection.execute(
        sa.text(
            "SELECT transaction_leg.amount "
            "FROM transaction_leg "
            "JOIN financial_transaction ON financial_transaction.id = "
            "transaction_leg.transaction_id "
            "WHERE transaction_leg.account_id = :account_id "
            "AND financial_transaction.status = 'posted' "
            "AND transaction_leg.created_at <= :boundary"
        ),
        {"account_id": account_id, "boundary": boundary},
    ).scalars()
    return sum((Decimal(str(amount)) for amount in amounts), Decimal("0"))


def _stored_money(connection: sa.Connection, value: Decimal | None) -> object:
    if value is None:
        return None
    return str(value) if connection.dialect.name == "sqlite" else value


def _migration_rows(connection: sa.Connection) -> list[dict[str, object]]:
    raw_rows = list(
        connection.execute(
            sa.text(
                "SELECT account_period.id, account_period.account_id, "
                "account_period.asset_id, account_period.created_by_user_id, "
                "account_period.start_date, account_period.end_date, "
                "account_period.created_at, account_period.closed_at, "
                "account.asset_id AS account_asset_id, "
                "workspace.timezone AS workspace_timezone "
                "FROM account_period "
                "JOIN account ON account.id = account_period.account_id "
                "JOIN workspace ON workspace.id = account.workspace_id "
                "ORDER BY account_period.account_id, account_period.start_date, "
                "account_period.created_at, account_period.id"
            )
        ).mappings()
    )
    migrated: list[dict[str, object]] = []
    prior_by_account: dict[int, dict[str, object]] = {}

    for raw in raw_rows:
        period_id = int(raw["id"])
        account_id = int(raw["account_id"])
        asset_id = int(raw["asset_id"])
        start_date = _as_date(raw["start_date"])
        end_date = _as_date(raw["end_date"])
        created_at = _as_naive_utc(raw["created_at"])
        closed_at = (
            _as_naive_utc(raw["closed_at"])
            if raw["closed_at"] is not None
            else None
        )

        if asset_id != int(raw["account_asset_id"]):
            raise RuntimeError(
                f"Cannot migrate account_period {period_id}: asset does not "
                "match its account"
            )
        if end_date < start_date:
            raise RuntimeError(
                f"Cannot migrate account_period {period_id}: end_date precedes "
                "start_date"
            )
        try:
            timezone = ZoneInfo(str(raw["workspace_timezone"]))
        except ZoneInfoNotFoundError as error:
            raise RuntimeError(
                f"Cannot migrate account_period {period_id}: invalid workspace "
                "timezone"
            ) from error
        if start_date > datetime.now(timezone).date():
            raise RuntimeError(
                f"Cannot migrate account_period {period_id}: future start_date "
                "has no v2.1 representation"
            )

        predecessor = prior_by_account.get(account_id)
        if predecessor is not None and start_date <= predecessor["end_date"]:
            raise RuntimeError(
                f"Cannot migrate account_period {period_id}: overlapping "
                "same-account period ranges"
            )

        snapshot_at = _local_boundary(start_date, timezone)
        if predecessor is not None:
            predecessor_boundary = predecessor["closed_at"]
            if predecessor_boundary is None:
                predecessor_boundary = _local_boundary(
                    predecessor["end_date"] + timedelta(days=1), timezone
                )
            snapshot_at = max(snapshot_at, predecessor_boundary)
        if closed_at is not None and closed_at < snapshot_at:
            raise RuntimeError(
                f"Cannot migrate account_period {period_id}: closed_at precedes "
                "snapshot_at"
            )

        migrated.append(
            {
                "id": period_id,
                "account_id": account_id,
                "asset_id": asset_id,
                "created_by_user_id": int(raw["created_by_user_id"]),
                "start_date": start_date,
                "end_date": end_date,
                "snapshot_at": snapshot_at,
                "opening_balance": _stored_money(
                    connection,
                    _ledger_balance(connection, account_id, snapshot_at),
                ),
                "rollover_policy": DEFAULT_ROLLOVER_POLICY,
                "created_at": created_at,
                "closed_at": closed_at,
                "closing_balance": _stored_money(
                    connection,
                    _ledger_balance(connection, account_id, closed_at)
                    if closed_at is not None
                    else None,
                ),
            }
        )
        prior_by_account[account_id] = {
            "end_date": end_date,
            "closed_at": closed_at,
        }
    return migrated


def _create_snapshot_period_table(
    connection: sa.Connection, table_name: str
) -> sa.Table:
    money = _money_type(connection)
    return op.create_table(
        table_name,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("account.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "asset_id",
            sa.Integer(),
            sa.ForeignKey("asset.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_by_user_id",
            sa.Integer(),
            sa.ForeignKey("user.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("snapshot_at", sa.DateTime(), nullable=False),
        sa.Column("opening_balance", money, nullable=False),
        sa.Column("rollover_policy", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("closing_balance", money, nullable=True),
        sa.CheckConstraint(
            "end_date >= start_date", name="ck_account_period_date_order"
        ),
        sa.CheckConstraint(
            "rollover_policy IN ('carry_next_day', "
            "'redistribute_remaining_days')",
            name="ck_account_period_rollover_policy",
        ),
        sa.CheckConstraint(
            "(closed_at IS NULL AND closing_balance IS NULL) OR "
            "(closed_at IS NOT NULL AND closing_balance IS NOT NULL)",
            name="ck_account_period_closing_pair",
        ),
    )


def _create_rebase_table(table_name: str, period_table: str) -> sa.Table:
    return op.create_table(
        table_name,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "account_period_id",
            sa.Integer(),
            sa.ForeignKey(f"{period_table}.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("reason", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "account_period_id", "day", name="uq_rebase_event_period_day"
        ),
    )


def _replace_tables(
    connection: sa.Connection,
    period_rows: list[dict[str, object]],
    *,
    period_table: sa.Table,
    rebase_table: sa.Table,
) -> None:
    rebase_rows = [
        {
            **dict(row),
            "day": _as_date(row["day"]),
            "created_at": _as_naive_utc(row["created_at"]),
        }
        for row in connection.execute(
            sa.text(
                "SELECT id, account_period_id, day, reason, created_at "
                "FROM rebase_event ORDER BY id"
            )
        ).mappings()
    ]
    if period_rows:
        connection.execute(period_table.insert(), period_rows)
    if rebase_rows:
        connection.execute(rebase_table.insert(), rebase_rows)

    op.drop_table("rebase_event")
    op.drop_table("account_period")
    op.rename_table(period_table.name, "account_period")
    op.rename_table(rebase_table.name, "rebase_event")
    for column in (
        "account_id",
        "asset_id",
        "created_by_user_id",
        "start_date",
        "end_date",
    ):
        op.create_index(f"ix_account_period_{column}", "account_period", [column])
    op.create_index(
        "ix_rebase_event_account_period_id",
        "rebase_event",
        ["account_period_id"],
    )
    op.create_index("ix_rebase_event_day", "rebase_event", ["day"])


def upgrade() -> None:
    connection = op.get_bind()
    period_rows = _migration_rows(connection)
    period_table = _create_snapshot_period_table(
        connection, "account_period_v21"
    )
    rebase_table = _create_rebase_table("rebase_event_v21", "account_period_v21")
    _replace_tables(
        connection,
        period_rows,
        period_table=period_table,
        rebase_table=rebase_table,
    )


def downgrade() -> None:
    connection = op.get_bind()
    money = _money_type(connection)
    period_rows = [
        {
            **dict(row),
            "start_date": _as_date(row["start_date"]),
            "end_date": _as_date(row["end_date"]),
            "created_at": _as_naive_utc(row["created_at"]),
            "closed_at": (
                _as_naive_utc(row["closed_at"])
                if row["closed_at"] is not None
                else None
            ),
        }
        for row in connection.execute(
            sa.text(
                "SELECT id, account_id, asset_id, created_by_user_id, "
                "start_date, end_date, opening_balance AS funding_amount, "
                "created_at, closed_at FROM account_period ORDER BY id"
            )
        ).mappings()
    ]
    period_table = op.create_table(
        "account_period_legacy",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("account.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "asset_id",
            sa.Integer(),
            sa.ForeignKey("asset.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_by_user_id",
            sa.Integer(),
            sa.ForeignKey("user.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("funding_amount", money, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
    )
    rebase_table = _create_rebase_table(
        "rebase_event_legacy", "account_period_legacy"
    )
    _replace_tables(
        connection,
        period_rows,
        period_table=period_table,
        rebase_table=rebase_table,
    )
