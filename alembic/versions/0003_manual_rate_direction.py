"""Store manual valuation rates with an explicit direction.

Revision ID: 0003_manual_rate_direction
Revises: 0002_period_snapshot_model
"""

from collections.abc import Sequence
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext

from alembic import op
import sqlalchemy as sa


revision: str = "0003_manual_rate_direction"
down_revision: str | None = "0002_period_snapshot_model"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RATE_QUANTUM = Decimal("0.000000000000000001")
LEGACY_DIRECTION = "main_to_asset_legacy"
CANONICAL_DIRECTION = "asset_to_main"


def _rate_type(connection: sa.Connection) -> sa.types.TypeEngine:
    if connection.dialect.name == "sqlite":
        return sa.String(80)
    return sa.Numeric(38, 18)


def _legacy_public_rate(value: object) -> Decimal:
    try:
        stored = Decimal(str(value))
        if not stored.is_finite() or stored <= 0:
            raise ValueError
        with localcontext() as context:
            context.prec = 100
            converted = (Decimal(1) / stored).quantize(
                RATE_QUANTUM,
                rounding=ROUND_HALF_UP,
            )
    except (InvalidOperation, ValueError, ArithmeticError) as error:
        raise ValueError from error
    if converted <= 0 or converted.adjusted() + 1 > 20:
        raise ValueError
    return converted


def _preflight_upgrade(connection: sa.Connection) -> None:
    rows = connection.execute(
        sa.text(
            "SELECT id, displayed_rate FROM manual_valuation_rate ORDER BY id"
        )
    )
    for row in rows:
        try:
            _legacy_public_rate(row.displayed_rate)
        except ValueError as error:
            raise RuntimeError(
                f"Manual valuation rate row {row.id} cannot be migrated"
            ) from error


def _preflight_downgrade(connection: sa.Connection) -> None:
    row_id = connection.execute(
        sa.text(
            "SELECT id FROM manual_valuation_rate "
            "WHERE direction = :direction ORDER BY id LIMIT 1"
        ),
        {"direction": CANONICAL_DIRECTION},
    ).scalar_one_or_none()
    if row_id is not None:
        raise RuntimeError(
            f"Manual valuation rate row {row_id} uses canonical direction; "
            "downgrade would reinterpret it"
        )


def upgrade() -> None:
    connection = op.get_bind()
    _preflight_upgrade(connection)
    recreate = "always" if connection.dialect.name == "sqlite" else "auto"
    rate_type = _rate_type(connection)

    with op.batch_alter_table(
        "manual_valuation_rate",
        recreate=recreate,
    ) as batch_op:
        batch_op.alter_column(
            "displayed_rate",
            new_column_name="rate_value",
            existing_type=rate_type,
            existing_nullable=False,
        )
        batch_op.add_column(
            sa.Column(
                "direction",
                sa.String(24),
                nullable=False,
                server_default=LEGACY_DIRECTION,
            )
        )
        batch_op.create_check_constraint(
            "ck_manual_valuation_rate_direction",
            "direction IN ('asset_to_main', 'main_to_asset_legacy')",
        )

    with op.batch_alter_table(
        "manual_valuation_rate",
        recreate=recreate,
    ) as batch_op:
        batch_op.alter_column(
            "direction",
            existing_type=sa.String(24),
            existing_nullable=False,
            server_default=None,
        )


def downgrade() -> None:
    connection = op.get_bind()
    _preflight_downgrade(connection)
    recreate = "always" if connection.dialect.name == "sqlite" else "auto"

    with op.batch_alter_table(
        "manual_valuation_rate",
        recreate=recreate,
    ) as batch_op:
        batch_op.drop_constraint(
            "ck_manual_valuation_rate_direction",
            type_="check",
        )
        batch_op.drop_column("direction")
        batch_op.alter_column(
            "rate_value",
            new_column_name="displayed_rate",
            existing_type=_rate_type(connection),
            existing_nullable=False,
        )
