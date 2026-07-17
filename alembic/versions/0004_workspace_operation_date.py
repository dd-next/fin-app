"""workspace foundation, operation table name, and financial date

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite batch_alter_table rebuilds `period` by dropping the old table.
    # With FK enforcement enabled that DROP cascades into legacy expenses.
    # Disable enforcement for this migration connection only; app/db.py turns
    # it on for every new runtime connection.
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.execute(sa.text("PRAGMA foreign_keys=OFF"))

    op.create_table(
        "workspace",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
    )
    op.execute(
        sa.text(
            "INSERT INTO workspace "
            "(id, name, kind, timezone, created_at) VALUES "
            "(1, 'Personal', 'personal', 'Asia/Ho_Chi_Minh', CURRENT_TIMESTAMP)"
        )
    )

    with op.batch_alter_table("period") as batch_op:
        batch_op.add_column(
            sa.Column("workspace_id", sa.Integer(), nullable=True)
        )
    op.execute(sa.text("UPDATE period SET workspace_id = 1"))
    with op.batch_alter_table("period") as batch_op:
        batch_op.alter_column("workspace_id", nullable=False)
        batch_op.create_foreign_key(
            "fk_period_workspace_id_workspace",
            "workspace",
            ["workspace_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    op.rename_table("expense", "operation")
    with op.batch_alter_table("operation") as batch_op:
        batch_op.add_column(sa.Column("occurred_on", sa.Date(), nullable=True))
    op.execute(
        sa.text("UPDATE operation SET occurred_on = date(created_at)")
    )
    with op.batch_alter_table("operation") as batch_op:
        batch_op.alter_column("occurred_on", nullable=False)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.execute(sa.text("PRAGMA foreign_keys=OFF"))

    with op.batch_alter_table("operation") as batch_op:
        batch_op.drop_column("occurred_on")
    op.rename_table("operation", "expense")

    with op.batch_alter_table("period") as batch_op:
        batch_op.drop_constraint(
            "fk_period_workspace_id_workspace", type_="foreignkey"
        )
        batch_op.drop_column("workspace_id")
    op.drop_table("workspace")
