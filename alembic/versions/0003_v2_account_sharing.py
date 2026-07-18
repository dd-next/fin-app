"""FinApp v2 per-account access and invitations.

Revision ID: 0003_v2
Revises: 0002_v2
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_v2"
down_revision: Union[str, None] = "0002_v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "account_access",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("account.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("account_id", "user_id", name="uq_account_access_user"),
    )
    op.create_index("ix_account_access_account_id", "account_access", ["account_id"])
    op.create_index("ix_account_access_user_id", "account_access", ["user_id"])

    op.create_table(
        "account_invitation",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("account.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
        sa.Column("accepted_by_user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_account_invitation_account_id", "account_invitation", ["account_id"])
    op.create_index("ix_account_invitation_token_hash", "account_invitation", ["token_hash"])


def downgrade() -> None:
    op.drop_table("account_invitation")
    op.drop_table("account_access")
