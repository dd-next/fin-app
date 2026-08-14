"""Persist immutable short-lived transfer quotes.

Revision ID: 0004_transfer_quotes
Revises: 0003_manual_rate_direction
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0004_transfer_quotes"
down_revision: str | None = "0003_manual_rate_direction"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _exact_decimal_type(connection: sa.Connection) -> sa.types.TypeEngine:
    if connection.dialect.name == "sqlite":
        return sa.String(80)
    return sa.Numeric(38, 18)


def _preflight_downgrade(connection: sa.Connection) -> None:
    quote_id = connection.execute(
        sa.text("SELECT id FROM transfer_quote ORDER BY id LIMIT 1")
    ).scalar_one_or_none()
    if quote_id is not None:
        raise RuntimeError(
            f"Transfer quote row {quote_id} prevents downgrade; "
            "audit evidence would be discarded"
        )


def _sqlite_positive_decimal(column: str) -> str:
    integer_digits = (
        f"CASE WHEN instr({column}, '.') = 0 THEN length({column}) "
        f"ELSE instr({column}, '.') - 1 END"
    )
    fraction_digits = (
        f"CASE WHEN instr({column}, '.') = 0 THEN 0 "
        f"ELSE length({column}) - instr({column}, '.') END"
    )
    return (
        f"typeof({column}) = 'text' AND length({column}) > 0 AND "
        f"{column} NOT GLOB '*[^0-9.]*' AND "
        f"{column} NOT LIKE '%.%.%' AND "
        f"substr({column}, 1, 1) <> '.' AND substr({column}, -1, 1) <> '.' AND "
        f"(substr({column}, 1, 1) <> '0' OR length({column}) = 1 OR "
        f"substr({column}, 2, 1) = '.') AND "
        f"(instr({column}, '.') = 0 OR substr({column}, -1, 1) <> '0') AND "
        f"{column} GLOB '*[1-9]*' AND ({integer_digits}) BETWEEN 1 AND 20 AND "
        f"({fraction_digits}) BETWEEN 0 AND 18"
    )


def _postgres_positive_finite_decimal(column: str) -> str:
    return (
        f"{column} > 0 AND "
        f"{column}::text NOT IN ('NaN', 'Infinity', '-Infinity')"
    )


def upgrade() -> None:
    connection = op.get_bind()
    exact_decimal = _exact_decimal_type(connection)
    sqlite = connection.dialect.name == "sqlite"
    positive_values = (
        " AND ".join(
            _sqlite_positive_decimal(column)
            for column in ("from_amount", "to_amount", "rate")
        )
        if sqlite
        else " AND ".join(
            _postgres_positive_finite_decimal(column)
            for column in ("from_amount", "to_amount", "rate")
        )
    )
    source_value_positive = (
        _sqlite_positive_decimal("source_manual_rate_value")
        if sqlite
        else _postgres_positive_finite_decimal("source_manual_rate_value")
    )
    target_value_positive = (
        _sqlite_positive_decimal("target_manual_rate_value")
        if sqlite
        else _postgres_positive_finite_decimal("target_manual_rate_value")
    )
    identity_equality = (
        "from_amount = to_amount AND rate = '1'"
        if sqlite
        else "from_amount = to_amount AND rate = 1"
    )

    op.create_table(
        "transfer_quote",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspace.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_by_user_id",
            sa.Integer(),
            sa.ForeignKey("user.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "from_account_id",
            sa.Integer(),
            sa.ForeignKey("account.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "to_account_id",
            sa.Integer(),
            sa.ForeignKey("account.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "from_asset_id",
            sa.Integer(),
            sa.ForeignKey("asset.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "to_asset_id",
            sa.Integer(),
            sa.ForeignKey("asset.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "main_asset_id",
            sa.Integer(),
            sa.ForeignKey("asset.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("from_amount", exact_decimal, nullable=False),
        sa.Column("to_amount", exact_decimal, nullable=False),
        sa.Column("rate", exact_decimal, nullable=False),
        sa.Column("rate_source", sa.String(16), nullable=False),
        sa.Column("source_manual_rate_id", sa.Integer(), nullable=True),
        sa.Column("source_manual_rate_value", exact_decimal, nullable=True),
        sa.Column("source_manual_rate_direction", sa.String(24), nullable=True),
        sa.Column("source_manual_rate_updated_at", sa.DateTime(), nullable=True),
        sa.Column("target_manual_rate_id", sa.Integer(), nullable=True),
        sa.Column("target_manual_rate_value", exact_decimal, nullable=True),
        sa.Column("target_manual_rate_direction", sa.String(24), nullable=True),
        sa.Column("target_manual_rate_updated_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("executed_at", sa.DateTime(), nullable=True),
        sa.Column(
            "executed_transaction_id",
            sa.Integer(),
            sa.ForeignKey("financial_transaction.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.UniqueConstraint(
            "executed_transaction_id",
            name="uq_transfer_quote_executed_transaction",
        ),
        sa.CheckConstraint(
            "from_account_id <> to_account_id",
            name="ck_transfer_quote_accounts_distinct",
        ),
        sa.CheckConstraint(
            positive_values,
            name="ck_transfer_quote_positive_values",
        ),
        sa.CheckConstraint(
            "rate_source = 'manual'",
            name="ck_transfer_quote_rate_source",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'executed')",
            name="ck_transfer_quote_status",
        ),
        sa.CheckConstraint(
            "expires_at > created_at",
            name="ck_transfer_quote_expiry",
        ),
        sa.CheckConstraint(
            "(status = 'open' AND executed_at IS NULL AND "
            "executed_transaction_id IS NULL) OR "
            "(status = 'executed' AND executed_at IS NOT NULL AND "
            "executed_transaction_id IS NOT NULL)",
            name="ck_transfer_quote_execution_state",
        ),
        sa.CheckConstraint(
            "(source_manual_rate_id IS NULL AND "
            "source_manual_rate_value IS NULL AND "
            "source_manual_rate_direction IS NULL AND "
            "source_manual_rate_updated_at IS NULL) OR "
            "(source_manual_rate_id IS NOT NULL AND source_manual_rate_id > 0 AND "
            "source_manual_rate_value IS NOT NULL AND "
            f"{source_value_positive} AND "
            "source_manual_rate_direction IS NOT NULL AND "
            "source_manual_rate_direction = 'asset_to_main' AND "
            "source_manual_rate_updated_at IS NOT NULL)",
            name="ck_transfer_quote_source_dependency",
        ),
        sa.CheckConstraint(
            "(target_manual_rate_id IS NULL AND "
            "target_manual_rate_value IS NULL AND "
            "target_manual_rate_direction IS NULL AND "
            "target_manual_rate_updated_at IS NULL) OR "
            "(target_manual_rate_id IS NOT NULL AND target_manual_rate_id > 0 AND "
            "target_manual_rate_value IS NOT NULL AND "
            f"{target_value_positive} AND "
            "target_manual_rate_direction IS NOT NULL AND "
            "target_manual_rate_direction = 'asset_to_main' AND "
            "target_manual_rate_updated_at IS NOT NULL)",
            name="ck_transfer_quote_target_dependency",
        ),
        sa.CheckConstraint(
            "(from_asset_id = to_asset_id AND "
            f"{identity_equality} AND "
            "source_manual_rate_id IS NULL AND target_manual_rate_id IS NULL) "
            "OR (from_asset_id <> to_asset_id AND "
            "((from_asset_id = main_asset_id AND source_manual_rate_id IS NULL) OR "
            "(from_asset_id <> main_asset_id AND source_manual_rate_id IS NOT NULL)) AND "
            "((to_asset_id = main_asset_id AND target_manual_rate_id IS NULL) OR "
            "(to_asset_id <> main_asset_id AND target_manual_rate_id IS NOT NULL)))",
            name="ck_transfer_quote_conversion_shape",
        ),
    )
    op.create_index(
        "ix_transfer_quote_workspace_creator_status_expiry",
        "transfer_quote",
        ["workspace_id", "created_by_user_id", "status", "expires_at"],
    )


def downgrade() -> None:
    connection = op.get_bind()
    _preflight_downgrade(connection)
    op.drop_index(
        "ix_transfer_quote_workspace_creator_status_expiry",
        table_name="transfer_quote",
    )
    op.drop_table("transfer_quote")
