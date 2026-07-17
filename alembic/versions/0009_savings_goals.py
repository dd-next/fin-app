"""cross-period savings goals, plans, and ledger transfers

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.models import Money


revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "savings_goal",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspace.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("normalized_name", sa.String(100), nullable=False),
        sa.Column("target_amount", Money(), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column(
            "created_by_user_id",
            sa.Integer(),
            sa.ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint(
            "workspace_id", "normalized_name", name="uq_savings_goal_workspace_name"
        ),
    )
    op.create_index("ix_savings_goal_workspace_id", "savings_goal", ["workspace_id"])

    op.create_table(
        "period_goal_plan",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "period_id",
            sa.Integer(),
            sa.ForeignKey("period.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "goal_id",
            sa.Integer(),
            sa.ForeignKey("savings_goal.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("planned_amount", Money(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("period_id", "goal_id", name="uq_period_goal_plan"),
    )
    op.create_index("ix_period_goal_plan_period_id", "period_goal_plan", ["period_id"])
    op.create_index("ix_period_goal_plan_goal_id", "period_goal_plan", ["goal_id"])

    with op.batch_alter_table("operation") as batch_op:
        batch_op.add_column(sa.Column("savings_goal_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_operation_savings_goal_id_savings_goal",
            "savings_goal",
            ["savings_goal_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_index("ix_operation_savings_goal_id", ["savings_goal_id"])


def downgrade() -> None:
    with op.batch_alter_table("operation") as batch_op:
        batch_op.drop_index("ix_operation_savings_goal_id")
        batch_op.drop_constraint(
            "fk_operation_savings_goal_id_savings_goal", type_="foreignkey"
        )
        batch_op.drop_column("savings_goal_id")
    op.drop_index("ix_period_goal_plan_goal_id", table_name="period_goal_plan")
    op.drop_index("ix_period_goal_plan_period_id", table_name="period_goal_plan")
    op.drop_table("period_goal_plan")
    op.drop_index("ix_savings_goal_workspace_id", table_name="savings_goal")
    op.drop_table("savings_goal")
