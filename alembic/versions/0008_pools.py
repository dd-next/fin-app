"""workspace pools and per-period envelope allocations

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.models import Money


revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pool",
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
            "created_by_user_id",
            sa.Integer(),
            sa.ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint(
            "workspace_id", "normalized_name", name="uq_pool_workspace_name"
        ),
    )
    op.create_index("ix_pool_workspace_id", "pool", ["workspace_id"])

    op.create_table(
        "period_pool_plan",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "period_id",
            sa.Integer(),
            sa.ForeignKey("period.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "pool_id",
            sa.Integer(),
            sa.ForeignKey("pool.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("allocated_amount", Money(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("period_id", "pool_id", name="uq_period_pool_plan"),
    )
    op.create_index(
        "ix_period_pool_plan_period_id", "period_pool_plan", ["period_id"]
    )
    op.create_index("ix_period_pool_plan_pool_id", "period_pool_plan", ["pool_id"])

    with op.batch_alter_table("period_category_plan") as batch_op:
        batch_op.add_column(sa.Column("pool_plan_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_period_category_plan_pool_plan_id_period_pool_plan",
            "period_pool_plan",
            ["pool_plan_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_period_category_plan_pool_plan_id", ["pool_plan_id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("period_category_plan") as batch_op:
        batch_op.drop_index("ix_period_category_plan_pool_plan_id")
        batch_op.drop_constraint(
            "fk_period_category_plan_pool_plan_id_period_pool_plan",
            type_="foreignkey",
        )
        batch_op.drop_column("pool_plan_id")
    op.drop_index("ix_period_pool_plan_pool_id", table_name="period_pool_plan")
    op.drop_index("ix_period_pool_plan_period_id", table_name="period_pool_plan")
    op.drop_table("period_pool_plan")
    op.drop_index("ix_pool_workspace_id", table_name="pool")
    op.drop_table("pool")
