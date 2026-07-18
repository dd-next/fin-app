"""FinApp v2 identity, workspace, assets, and categories.

Revision ID: 0001_v2
Revises: None
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_v2"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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
    asset_table = sa.table(
        "asset",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("kind", sa.String),
        sa.column("decimals", sa.Integer),
        sa.column("is_active", sa.Boolean),
    )
    op.bulk_insert(
        asset_table,
        [
            {"code": "VND", "name": "Vietnamese dong", "kind": "fiat", "decimals": 0, "is_active": True},
            {"code": "USD", "name": "US dollar", "kind": "fiat", "decimals": 2, "is_active": True},
            {"code": "RUB", "name": "Russian ruble", "kind": "fiat", "decimals": 2, "is_active": True},
            {"code": "EUR", "name": "Euro", "kind": "fiat", "decimals": 2, "is_active": True},
            {"code": "USDT", "name": "Tether", "kind": "crypto", "decimals": 6, "is_active": True},
            {"code": "BTC", "name": "Bitcoin", "kind": "crypto", "decimals": 8, "is_active": True},
            {"code": "ETH", "name": "Ethereum", "kind": "crypto", "decimals": 18, "is_active": True},
            {"code": "TRX", "name": "TRON", "kind": "crypto", "decimals": 6, "is_active": True},
        ],
    )

    op.create_table(
        "auth_session",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
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
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("base_asset_id", sa.Integer(), sa.ForeignKey("asset.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("owner_user_id"),
    )

    op.create_table(
        "category",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("normalized_name", sa.String(100), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False, server_default="expense"),
        sa.Column("icon", sa.String(32), nullable=True),
        sa.Column("color", sa.String(16), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("workspace_id", "normalized_name", name="uq_category_workspace_name"),
    )
    op.create_index("ix_category_workspace_id", "category", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_category_workspace_id", table_name="category")
    op.drop_table("category")
    op.drop_table("workspace")
    op.drop_index("ix_auth_session_token_hash", table_name="auth_session")
    op.drop_index("ix_auth_session_user_id", table_name="auth_session")
    op.drop_table("auth_session")
    op.drop_index("ix_asset_code", table_name="asset")
    op.drop_table("asset")
    op.drop_index("ix_user_normalized_username", table_name="user")
    op.drop_table("user")
