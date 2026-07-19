"""Clean FinApp v2 release schema.

Revision ID: 0001_release_v2
Revises: None
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0001_release_v2"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    money = (
        sa.String(80)
        if op.get_bind().dialect.name == "sqlite"
        else sa.Numeric(38, 18)
    )

    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("normalized_username", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("normalized_username"),
    )
    op.create_index("ix_user_normalized_username", "user", ["normalized_username"])

    op.create_table(
        "asset",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(16), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("decimals", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_asset_code", "asset", ["code"])
    assets = sa.table(
        "asset",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("kind", sa.String),
        sa.column("decimals", sa.Integer),
        sa.column("is_active", sa.Boolean),
    )
    op.bulk_insert(
        assets,
        [
            {
                "code": "VND",
                "name": "Vietnamese dong",
                "kind": "fiat",
                "decimals": 0,
                "is_active": True,
            },
            {
                "code": "USD",
                "name": "US dollar",
                "kind": "fiat",
                "decimals": 2,
                "is_active": True,
            },
            {
                "code": "RUB",
                "name": "Russian ruble",
                "kind": "fiat",
                "decimals": 2,
                "is_active": True,
            },
            {
                "code": "EUR",
                "name": "Euro",
                "kind": "fiat",
                "decimals": 2,
                "is_active": True,
            },
            {
                "code": "USDT",
                "name": "Tether",
                "kind": "crypto",
                "decimals": 6,
                "is_active": True,
            },
            {
                "code": "BTC",
                "name": "Bitcoin",
                "kind": "crypto",
                "decimals": 8,
                "is_active": True,
            },
            {
                "code": "ETH",
                "name": "Ethereum",
                "kind": "crypto",
                "decimals": 18,
                "is_active": True,
            },
            {
                "code": "TRX",
                "name": "TRON",
                "kind": "crypto",
                "decimals": 6,
                "is_active": True,
            },
        ],
    )

    op.create_table(
        "auth_session",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_auth_session_user_id", "auth_session", ["user_id"])
    op.create_index("ix_auth_session_token_hash", "auth_session", ["token_hash"])

    op.create_table(
        "workspace",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "owner_user_id",
            sa.Integer(),
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column(
            "base_asset_id",
            sa.Integer(),
            sa.ForeignKey("asset.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("owner_user_id"),
    )

    op.create_table(
        "manual_valuation_rate",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspace.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "main_asset_id",
            sa.Integer(),
            sa.ForeignKey("asset.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "asset_id",
            sa.Integer(),
            sa.ForeignKey("asset.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("displayed_rate", money, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "workspace_id",
            "main_asset_id",
            "asset_id",
            name="uq_manual_rate_workspace_pair",
        ),
    )
    for column in ("workspace_id", "main_asset_id", "asset_id"):
        op.create_index(
            f"ix_manual_valuation_rate_{column}",
            "manual_valuation_rate",
            [column],
        )

    op.create_table(
        "category",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspace.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("normalized_name", sa.String(100), nullable=False),
        sa.Column(
            "kind", sa.String(16), nullable=False, server_default="expense"
        ),
        sa.Column("icon", sa.String(32), nullable=True),
        sa.Column("color", sa.String(16), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint(
            "workspace_id",
            "normalized_name",
            name="uq_category_workspace_name",
        ),
    )
    op.create_index("ix_category_workspace_id", "category", ["workspace_id"])

    op.create_table(
        "account",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspace.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "owner_user_id",
            sa.Integer(),
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("normalized_name", sa.String(100), nullable=False),
        sa.Column("storage_type", sa.String(24), nullable=False),
        sa.Column("purpose", sa.String(24), nullable=False),
        sa.Column(
            "asset_id",
            sa.Integer(),
            sa.ForeignKey("asset.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("institution", sa.String(100), nullable=True),
        sa.Column(
            "include_in_available",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint(
            "workspace_id",
            "normalized_name",
            name="uq_account_workspace_name",
        ),
    )
    for column in ("workspace_id", "owner_user_id", "asset_id"):
        op.create_index(f"ix_account_{column}", "account", [column])

    op.create_table(
        "account_access",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("account.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("account_id", "user_id", name="uq_account_access_user"),
    )
    op.create_index("ix_account_access_account_id", "account_access", ["account_id"])
    op.create_index("ix_account_access_user_id", "account_access", ["user_id"])

    op.create_table(
        "account_invitation",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("account.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_by_user_id",
            sa.Integer(),
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
        sa.Column(
            "accepted_by_user_id",
            sa.Integer(),
            sa.ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "ix_account_invitation_account_id", "account_invitation", ["account_id"]
    )
    op.create_index(
        "ix_account_invitation_token_hash", "account_invitation", ["token_hash"]
    )

    op.create_table(
        "financial_transaction",
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
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column(
            "category_id",
            sa.Integer(),
            sa.ForeignKey("category.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "parent_transaction_id",
            sa.Integer(),
            sa.ForeignKey("financial_transaction.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("counterparty", sa.String(160), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("origin", sa.String(16), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(16), nullable=False, server_default="posted"),
        sa.Column("external_id", sa.String(160), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("voided_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "origin IN ('manual', 'operations')",
            name="ck_financial_transaction_origin",
        ),
    )
    for column in (
        "workspace_id",
        "created_by_user_id",
        "type",
        "category_id",
        "parent_transaction_id",
        "local_date",
        "status",
    ):
        op.create_index(
            f"ix_financial_transaction_{column}", "financial_transaction", [column]
        )

    op.create_table(
        "transaction_leg",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "transaction_id",
            sa.Integer(),
            sa.ForeignKey("financial_transaction.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("account.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "asset_id",
            sa.Integer(),
            sa.ForeignKey("asset.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("amount", money, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    for column in ("transaction_id", "account_id", "asset_id"):
        op.create_index(f"ix_transaction_leg_{column}", "transaction_leg", [column])

    op.create_table(
        "exchange_rate",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspace.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_transaction_id",
            sa.Integer(),
            sa.ForeignKey("financial_transaction.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "base_asset_id",
            sa.Integer(),
            sa.ForeignKey("asset.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "quote_asset_id",
            sa.Integer(),
            sa.ForeignKey("asset.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("rate", money, nullable=False),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "workspace_id",
            "source_transaction_id",
            "base_asset_id",
            "quote_asset_id",
            name="uq_exchange_rate_transaction_pair",
        ),
    )
    for column in (
        "workspace_id",
        "source_transaction_id",
        "base_asset_id",
        "quote_asset_id",
    ):
        op.create_index(f"ix_exchange_rate_{column}", "exchange_rate", [column])

    op.create_table(
        "plan_rule",
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
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("amount", money, nullable=False),
        sa.Column(
            "asset_id",
            sa.Integer(),
            sa.ForeignKey("asset.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("recurrence", sa.String(16), nullable=False),
        sa.Column("first_due_date", sa.Date(), nullable=False),
        sa.Column(
            "category_id",
            sa.Integer(),
            sa.ForeignKey("category.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "default_from_account_id",
            sa.Integer(),
            sa.ForeignKey("account.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "default_to_account_id",
            sa.Integer(),
            sa.ForeignKey("account.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "is_required", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    for column in (
        "workspace_id",
        "created_by_user_id",
        "kind",
        "asset_id",
        "first_due_date",
    ):
        op.create_index(f"ix_plan_rule_{column}", "plan_rule", [column])

    op.create_table(
        "plan_occurrence",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "plan_rule_id",
            sa.Integer(),
            sa.ForeignKey("plan_rule.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("planned_amount", money, nullable=False),
        sa.Column(
            "status", sa.String(16), nullable=False, server_default="planned"
        ),
        sa.Column(
            "transaction_id",
            sa.Integer(),
            sa.ForeignKey("financial_transaction.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("matched_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "plan_rule_id", "due_date", name="uq_plan_occurrence_rule_date"
        ),
        sa.UniqueConstraint("transaction_id"),
    )
    for column in ("plan_rule_id", "due_date", "status", "transaction_id"):
        op.create_index(f"ix_plan_occurrence_{column}", "plan_occurrence", [column])

    op.create_table(
        "account_period",
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
    for column in (
        "account_id",
        "asset_id",
        "created_by_user_id",
        "start_date",
        "end_date",
    ):
        op.create_index(f"ix_account_period_{column}", "account_period", [column])

    op.create_table(
        "rebase_event",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "account_period_id",
            sa.Integer(),
            sa.ForeignKey("account_period.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("reason", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "account_period_id", "day", name="uq_rebase_event_period_day"
        ),
    )
    op.create_index(
        "ix_rebase_event_account_period_id", "rebase_event", ["account_period_id"]
    )
    op.create_index("ix_rebase_event_day", "rebase_event", ["day"])

    op.create_table(
        "operations_undo_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("account.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "cursor_transaction_id",
            sa.Integer(),
            sa.ForeignKey("financial_transaction.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint(
            "user_id", "account_id", name="uq_operations_undo_state_user_account"
        ),
    )
    for column in ("user_id", "account_id", "cursor_transaction_id"):
        op.create_index(
            f"ix_operations_undo_state_{column}",
            "operations_undo_state",
            [column],
        )


def downgrade() -> None:
    for table_name in (
        "operations_undo_state",
        "rebase_event",
        "account_period",
        "plan_occurrence",
        "plan_rule",
        "exchange_rate",
        "transaction_leg",
        "financial_transaction",
        "account_invitation",
        "account_access",
        "account",
        "category",
        "manual_valuation_rate",
        "workspace",
        "auth_session",
        "asset",
        "user",
    ):
        op.drop_table(table_name)
