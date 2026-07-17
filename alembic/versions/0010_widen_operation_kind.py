"""allow descriptive operation kinds used by savings transfers

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("operation") as batch_op:
        batch_op.alter_column(
            "kind",
            existing_type=sa.String(10),
            type_=sa.String(32),
            existing_nullable=False,
            existing_server_default="expense",
        )


def downgrade() -> None:
    with op.batch_alter_table("operation") as batch_op:
        batch_op.alter_column(
            "kind",
            existing_type=sa.String(32),
            type_=sa.String(10),
            existing_nullable=False,
            existing_server_default="expense",
        )
