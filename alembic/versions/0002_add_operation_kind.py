"""add operation kind (expense | income) to the expense table

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Existing rows are all expenses; the server default keeps them valid.
    op.add_column(
        "expense",
        sa.Column(
            "kind", sa.String(10), nullable=False, server_default="expense"
        ),
    )


def downgrade() -> None:
    op.drop_column("expense", "kind")
