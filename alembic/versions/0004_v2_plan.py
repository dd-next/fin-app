"""FinApp v2 plan rules and occurrences.

Revision ID: 0004_v2
Revises: 0003_v2
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004_v2"
down_revision: Union[str, None] = "0003_v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    money = sa.String(80) if op.get_bind().dialect.name == "sqlite" else sa.Numeric(38, 18)
    op.create_table(
        "plan_rule",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("amount", money, nullable=False),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("asset.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("recurrence", sa.String(16), nullable=False),
        sa.Column("first_due_date", sa.Date(), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("category.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("default_from_account_id", sa.Integer(), sa.ForeignKey("account.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("default_to_account_id", sa.Integer(), sa.ForeignKey("account.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    for column in ("workspace_id", "created_by_user_id", "kind", "asset_id", "first_due_date"):
        op.create_index(f"ix_plan_rule_{column}", "plan_rule", [column])

    op.create_table(
        "plan_occurrence",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("plan_rule_id", sa.Integer(), sa.ForeignKey("plan_rule.id", ondelete="CASCADE"), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("planned_amount", money, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="planned"),
        sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("financial_transaction.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("matched_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("plan_rule_id", "due_date", name="uq_plan_occurrence_rule_date"),
        sa.UniqueConstraint("transaction_id"),
    )
    op.create_index("ix_plan_occurrence_plan_rule_id", "plan_occurrence", ["plan_rule_id"])
    op.create_index("ix_plan_occurrence_due_date", "plan_occurrence", ["due_date"])
    op.create_index("ix_plan_occurrence_status", "plan_occurrence", ["status"])
    op.create_index("ix_plan_occurrence_transaction_id", "plan_occurrence", ["transaction_id"])


def downgrade() -> None:
    op.drop_table("plan_occurrence")
    op.drop_table("plan_rule")
