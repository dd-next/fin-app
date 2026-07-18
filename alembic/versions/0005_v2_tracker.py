"""FinApp v2 tracker periods, commitments, and replay events.

Revision ID: 0005_v2
Revises: 0004_v2
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005_v2"
down_revision: Union[str, None] = "0004_v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    money = (
        sa.String(80)
        if op.get_bind().dialect.name == "sqlite"
        else sa.Numeric(38, 18)
    )
    op.create_table(
        "budget_period",
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
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column(
            "base_asset_id",
            sa.Integer(),
            sa.ForeignKey("asset.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("funding_amount", money, nullable=False),
        sa.Column(
            "opening_transaction_id",
            sa.Integer(),
            sa.ForeignKey("financial_transaction.id", ondelete="RESTRICT"),
            nullable=True,
            unique=True,
        ),
        sa.Column(
            "opening_plan_occurrence_id",
            sa.Integer(),
            sa.ForeignKey("plan_occurrence.id", ondelete="RESTRICT"),
            nullable=True,
            unique=True,
        ),
        sa.Column("prompt_ack_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
    )
    for column in ("workspace_id", "created_by_user_id", "start_date", "end_date"):
        op.create_index(f"ix_budget_period_{column}", "budget_period", [column])

    op.create_table(
        "budget_commitment",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "budget_period_id",
            sa.Integer(),
            sa.ForeignKey("budget_period.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "plan_occurrence_id",
            sa.Integer(),
            sa.ForeignKey("plan_occurrence.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("type", sa.String(24), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("planned_amount", money, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="reserved"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "budget_period_id",
            "plan_occurrence_id",
            name="uq_budget_commitment_period_occurrence",
        ),
    )
    for column in ("budget_period_id", "plan_occurrence_id", "status"):
        op.create_index(
            f"ix_budget_commitment_{column}", "budget_commitment", [column]
        )

    op.create_table(
        "rebase_event",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "budget_period_id",
            sa.Integer(),
            sa.ForeignKey("budget_period.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("reason", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "budget_period_id", "day", name="uq_rebase_event_period_day"
        ),
    )
    op.create_index(
        "ix_rebase_event_budget_period_id", "rebase_event", ["budget_period_id"]
    )
    op.create_index("ix_rebase_event_day", "rebase_event", ["day"])

    with op.batch_alter_table("financial_transaction") as batch:
        batch.add_column(sa.Column("budget_period_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_financial_transaction_budget_period",
            "budget_period",
            ["budget_period_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_index(
            "ix_financial_transaction_budget_period_id", ["budget_period_id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("financial_transaction") as batch:
        batch.drop_index("ix_financial_transaction_budget_period_id")
        batch.drop_constraint(
            "fk_financial_transaction_budget_period", type_="foreignkey"
        )
        batch.drop_column("budget_period_id")
    op.drop_table("rebase_event")
    op.drop_table("budget_commitment")
    op.drop_table("budget_period")
