"""workspace memberships and one-time invitations

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workspace_member",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspace.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("joined_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("workspace_id", "user_id", name="uq_workspace_member"),
    )
    op.create_index(
        "ix_workspace_member_workspace_id", "workspace_member", ["workspace_id"]
    )
    op.create_index("ix_workspace_member_user_id", "workspace_member", ["user_id"])

    op.create_table(
        "workspace_invite",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspace.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column(
            "created_by_user_id",
            sa.Integer(),
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_workspace_invite_workspace_id", "workspace_invite", ["workspace_id"]
    )
    op.create_index(
        "ix_workspace_invite_token_hash", "workspace_invite", ["token_hash"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_workspace_invite_token_hash", table_name="workspace_invite")
    op.drop_index("ix_workspace_invite_workspace_id", table_name="workspace_invite")
    op.drop_table("workspace_invite")
    op.drop_index("ix_workspace_member_user_id", table_name="workspace_member")
    op.drop_index("ix_workspace_member_workspace_id", table_name="workspace_member")
    op.drop_table("workspace_member")
