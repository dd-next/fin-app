"""FinApp v2 accounts and financial ledger.

Revision ID: 0002_v2
Revises: 0001_v2
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_v2"
down_revision: Union[str, None] = "0001_v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    money = sa.String(80) if op.get_bind().dialect.name == "sqlite" else sa.Numeric(38, 18)
    op.create_table(
        "account",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("normalized_name", sa.String(100), nullable=False),
        sa.Column("storage_type", sa.String(24), nullable=False),
        sa.Column("purpose", sa.String(24), nullable=False),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("asset.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("institution", sa.String(100), nullable=True),
        sa.Column("include_in_available", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("workspace_id", "normalized_name", name="uq_account_workspace_name"),
    )
    op.create_index("ix_account_workspace_id", "account", ["workspace_id"])
    op.create_index("ix_account_owner_user_id", "account", ["owner_user_id"])
    op.create_index("ix_account_asset_id", "account", ["asset_id"])

    op.create_table(
        "financial_transaction",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("category.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("parent_transaction_id", sa.Integer(), sa.ForeignKey("financial_transaction.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("counterparty", sa.String(160), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("source", sa.String(16), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(16), nullable=False, server_default="posted"),
        sa.Column("external_id", sa.String(160), nullable=True),
        sa.Column("base_amount", money, nullable=True),
        sa.Column("base_rate", money, nullable=True),
        sa.Column("rate_source", sa.String(24), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("voided_at", sa.DateTime(), nullable=True),
    )
    for column in ("workspace_id", "created_by_user_id", "type", "category_id", "parent_transaction_id", "local_date", "status"):
        op.create_index(f"ix_financial_transaction_{column}", "financial_transaction", [column])

    op.create_table(
        "transaction_leg",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("financial_transaction.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("account.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("asset.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("amount", money, nullable=False),
    )
    op.create_index("ix_transaction_leg_transaction_id", "transaction_leg", ["transaction_id"])
    op.create_index("ix_transaction_leg_account_id", "transaction_leg", ["account_id"])
    op.create_index("ix_transaction_leg_asset_id", "transaction_leg", ["asset_id"])

    op.create_table(
        "exchange_rate",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_transaction_id", sa.Integer(), sa.ForeignKey("financial_transaction.id", ondelete="CASCADE"), nullable=False),
        sa.Column("base_asset_id", sa.Integer(), sa.ForeignKey("asset.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quote_asset_id", sa.Integer(), sa.ForeignKey("asset.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("rate", money, nullable=False),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("source_transaction_id", "base_asset_id", "quote_asset_id", name="uq_exchange_rate_transaction_pair"),
    )
    op.create_index("ix_exchange_rate_source_transaction_id", "exchange_rate", ["source_transaction_id"])
    op.create_index("ix_exchange_rate_base_asset_id", "exchange_rate", ["base_asset_id"])
    op.create_index("ix_exchange_rate_quote_asset_id", "exchange_rate", ["quote_asset_id"])


def downgrade() -> None:
    op.drop_table("exchange_rate")
    op.drop_table("transaction_leg")
    op.drop_table("financial_transaction")
    op.drop_table("account")
