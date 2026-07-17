"""workspace categories, operation classification, and period limits

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.models import Money


revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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
            "created_by_user_id",
            sa.Integer(),
            sa.ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint(
            "workspace_id", "normalized_name", name="uq_category_workspace_name"
        ),
    )
    op.create_index("ix_category_workspace_id", "category", ["workspace_id"])

    with op.batch_alter_table("operation") as batch_op:
        batch_op.add_column(sa.Column("category_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("created_by_user_id", sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_operation_category_id_category",
            "category",
            ["category_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_foreign_key(
            "fk_operation_created_by_user_id_user",
            "user",
            ["created_by_user_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_operation_category_id", ["category_id"])
        batch_op.create_index(
            "ix_operation_created_by_user_id", ["created_by_user_id"]
        )

    op.create_table(
        "period_category_plan",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "period_id",
            sa.Integer(),
            sa.ForeignKey("period.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "category_id",
            sa.Integer(),
            sa.ForeignKey("category.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("limit_amount", Money(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("period_id", "category_id", name="uq_period_category_plan"),
    )
    op.create_index(
        "ix_period_category_plan_period_id", "period_category_plan", ["period_id"]
    )
    op.create_index(
        "ix_period_category_plan_category_id", "period_category_plan", ["category_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_period_category_plan_category_id", table_name="period_category_plan"
    )
    op.drop_index(
        "ix_period_category_plan_period_id", table_name="period_category_plan"
    )
    op.drop_table("period_category_plan")
    with op.batch_alter_table("operation") as batch_op:
        batch_op.drop_index("ix_operation_created_by_user_id")
        batch_op.drop_index("ix_operation_category_id")
        batch_op.drop_constraint(
            "fk_operation_created_by_user_id_user", type_="foreignkey"
        )
        batch_op.drop_constraint(
            "fk_operation_category_id_category", type_="foreignkey"
        )
        batch_op.drop_column("created_by_user_id")
        batch_op.drop_column("category_id")
    op.drop_index("ix_category_workspace_id", table_name="category")
    op.drop_table("category")
