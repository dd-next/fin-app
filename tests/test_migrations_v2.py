import os
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
import subprocess
import sys
import textwrap
import warnings
import re
from zoneinfo import ZoneInfo

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError, SAWarning


RELEASE_TABLES = {
    "account",
    "account_access",
    "account_invitation",
    "account_period",
    "alembic_version",
    "asset",
    "auth_session",
    "category",
    "exchange_rate",
    "financial_transaction",
    "manual_valuation_rate",
    "operations_undo_state",
    "plan_occurrence",
    "plan_rule",
    "rebase_event",
    "transaction_leg",
    "user",
    "workspace",
}


def test_clean_v2_upgrade_builds_foundation_and_seeds_assets(
    tmp_path: Path, monkeypatch
):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    database = tmp_path / "fresh-v2.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database}")
    command.upgrade(config, "head")

    engine = create_engine(f"sqlite:///{database}")
    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version"))
            .scalar_one()
            == "0002_period_snapshot_model"
        )
        assert connection.execute(text("SELECT count(*) FROM asset")).scalar_one() == 8
        assert connection.execute(
            text("SELECT group_concat(code, ',') FROM (SELECT code FROM asset ORDER BY id)")
        ).scalar_one() == "VND,USD,RUB,EUR,USDT,BTC,ETH,TRX"
        assert set(inspect(connection).get_table_names()) == RELEASE_TABLES

        inspector = inspect(connection)
        transaction_columns = {
            item["name"] for item in inspector.get_columns("financial_transaction")
        }
        assert "origin" in transaction_columns
        assert {
            "source",
            "budget_period_id",
            "base_amount",
            "base_rate",
            "rate_source",
        }.isdisjoint(transaction_columns)
        assert "created_at" in {
            item["name"] for item in inspector.get_columns("transaction_leg")
        }
        assert "workspace_id" in {
            item["name"] for item in inspector.get_columns("exchange_rate")
        }
        assert {
            "account_id",
            "asset_id",
            "start_date",
            "end_date",
            "snapshot_at",
            "opening_balance",
            "rollover_policy",
            "created_at",
            "closed_at",
            "closing_balance",
        } <= {item["name"] for item in inspector.get_columns("account_period")}
        assert "funding_amount" not in {
            item["name"] for item in inspector.get_columns("account_period")
        }
        assert "workspace_id" not in {
            item["name"] for item in inspector.get_columns("account_period")
        }
        assert {
            "workspace_id",
            "main_asset_id",
            "asset_id",
            "displayed_rate",
            "created_at",
            "updated_at",
        } <= {
            item["name"]
            for item in inspector.get_columns("manual_valuation_rate")
        }
        assert any(
            constraint["column_names"]
            == ["workspace_id", "main_asset_id", "asset_id"]
            for constraint in inspector.get_unique_constraints(
                "manual_valuation_rate"
            )
        )
        assert {
            "user_id",
            "account_id",
            "cursor_transaction_id",
            "consumed_at",
            "created_at",
            "updated_at",
        } <= {
            item["name"]
            for item in inspector.get_columns("operations_undo_state")
        }
        assert any(
            constraint["column_names"] == ["user_id", "account_id"]
            for constraint in inspector.get_unique_constraints(
                "operations_undo_state"
            )
        )
        assert {
            "workspace_id",
            "base_asset_id",
            "opening_transaction_id",
            "opening_plan_occurrence_id",
            "prompt_ack_date",
        }.isdisjoint(
            item["name"] for item in inspector.get_columns("account_period")
        )
    engine.dispose()


def _seed_populated_legacy_periods(connection, *, future_start: bool = False):
    workspace_timezone = ZoneInfo("America/New_York")
    today = datetime.now(workspace_timezone).date()
    now = datetime.now(UTC).replace(tzinfo=None, microsecond=0)

    def boundary(day):
        return (
            datetime.combine(day, time.min, tzinfo=workspace_timezone)
            .astimezone(UTC)
            .replace(tzinfo=None)
        )

    connection.execute(
        text(
            "INSERT INTO user "
            "(id, username, normalized_username, display_name, password_hash, "
            "timezone, is_active, created_at, updated_at) VALUES "
            "(1, 'owner', 'owner', 'Owner', 'hash', 'UTC', 1, :now, :now)"
        ),
        {"now": now},
    )
    asset_id = connection.execute(
        text("SELECT id FROM asset WHERE code = 'BTC'")
    ).scalar_one()
    connection.execute(
        text(
            "INSERT INTO workspace "
            "(id, owner_user_id, name, base_asset_id, timezone, created_at) "
            "VALUES (1, 1, 'Workspace', :asset_id, 'America/New_York', :now)"
        ),
        {"asset_id": asset_id, "now": now},
    )
    connection.execute(
        text(
            "INSERT INTO account "
            "(id, workspace_id, owner_user_id, name, normalized_name, "
            "storage_type, purpose, asset_id, include_in_available, created_at, "
            "updated_at) VALUES "
            "(:id, 1, 1, :name, :normalized_name, 'bank', 'spending', "
            ":asset_id, 1, :now, :now)"
        ),
        [
            {
                "id": account_id,
                "name": name,
                "normalized_name": name.lower(),
                "asset_id": asset_id,
                "now": now,
            }
            for account_id, name in (
                (1, "Ended"),
                (2, "Current"),
                (3, "Closed"),
                (4, "Successor"),
            )
        ],
    )

    ended_start = today + timedelta(days=1 if future_start else -10)
    ended_end = ended_start + timedelta(days=2)
    current_start = today
    closed_start = today - timedelta(days=3)
    closed_at = boundary(today) + timedelta(hours=12)
    predecessor_start = today - timedelta(days=7)
    predecessor_end = today - timedelta(days=5)
    successor_start = predecessor_end + timedelta(days=1)
    predecessor_closed_at = boundary(successor_start) + timedelta(hours=2)
    periods = [
        {
            "id": 1,
            "account_id": 1,
            "start_date": ended_start,
            "end_date": ended_end,
            "funding": "999.123456789012345678",
            "created_at": datetime.combine(ended_start, time.min)
            + timedelta(hours=3),
            "closed_at": None,
        },
        {
            "id": 2,
            "account_id": 2,
            "start_date": current_start,
            "end_date": today + timedelta(days=5),
            "funding": "888.123456789012345678",
            "created_at": datetime.combine(current_start, time.min)
            + timedelta(hours=3),
            "closed_at": None,
        },
        {
            "id": 3,
            "account_id": 3,
            "start_date": closed_start,
            "end_date": today + timedelta(days=3),
            "funding": "777.123456789012345678",
            "created_at": datetime.combine(closed_start, time.min)
            + timedelta(hours=3),
            "closed_at": closed_at,
        },
        {
            "id": 4,
            "account_id": 4,
            "start_date": predecessor_start,
            "end_date": predecessor_end,
            "funding": "666.123456789012345678",
            "created_at": boundary(predecessor_start) + timedelta(hours=3),
            "closed_at": predecessor_closed_at,
        },
        {
            "id": 5,
            "account_id": 4,
            "start_date": successor_start,
            "end_date": today - timedelta(days=2),
            "funding": "555.123456789012345678",
            "created_at": predecessor_closed_at + timedelta(hours=1),
            "closed_at": None,
        },
    ]
    connection.execute(
        text(
            "INSERT INTO account_period "
            "(id, account_id, asset_id, created_by_user_id, start_date, end_date, "
            "funding_amount, created_at, closed_at) VALUES "
            "(:id, :account_id, :asset_id, 1, :start_date, :end_date, "
            ":funding, :created_at, :closed_at)"
        ),
        [{**period, "asset_id": asset_id} for period in periods],
    )
    connection.execute(
        text(
            "INSERT INTO rebase_event "
            "(id, account_period_id, day, reason, created_at) "
            "VALUES (1, 1, :day, 'overspend', :created_at)"
        ),
        {
            "day": ended_start,
            "created_at": boundary(ended_start),
        },
    )

    leg_specs = (
        (1, 1, "10.123456789012345678", boundary(ended_start), "posted"),
        (2, 1, "-2", boundary(ended_start) + timedelta(hours=1), "posted"),
        (3, 2, "100", boundary(current_start) - timedelta(hours=1), "posted"),
        (4, 2, "-20", boundary(current_start) + timedelta(hours=1), "posted"),
        (5, 3, "50", boundary(closed_start) - timedelta(hours=1), "posted"),
        (6, 3, "-5", boundary(closed_start) + timedelta(hours=1), "posted"),
        (7, 3, "999", boundary(closed_start) - timedelta(hours=2), "voided"),
        (8, 4, "200", boundary(predecessor_start) - timedelta(hours=1), "posted"),
        (9, 4, "-50", predecessor_closed_at, "posted"),
    )
    for transaction_id, account_id, amount, created_at, status in leg_specs:
        connection.execute(
            text(
                "INSERT INTO financial_transaction "
                "(id, workspace_id, created_by_user_id, type, occurred_at, "
                "local_date, origin, status, created_at, updated_at) VALUES "
                "(:id, 1, 1, 'adjustment', :created_at, :local_date, 'manual', "
                ":status, :created_at, :created_at)"
            ),
            {
                "id": transaction_id,
                "created_at": created_at,
                "local_date": created_at.date(),
                "status": status,
            },
        )
        connection.execute(
            text(
                "INSERT INTO transaction_leg "
                "(id, transaction_id, account_id, asset_id, amount, created_at) "
                "VALUES (:id, :id, :account_id, :asset_id, :amount, :created_at)"
            ),
            {
                "id": transaction_id,
                "account_id": account_id,
                "asset_id": asset_id,
                "amount": amount,
                "created_at": created_at,
            },
        )
    return {
        "ended_snapshot": boundary(ended_start),
        "current_snapshot": boundary(current_start),
        "closed_snapshot": boundary(closed_start),
        "closed_at": closed_at,
        "successor_snapshot": predecessor_closed_at,
    }


def test_period_snapshot_migration_backfills_populated_release_database(tmp_path: Path):
    database = tmp_path / "populated-periods.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database}")
    command.upgrade(config, "0001_release_v2")
    engine = create_engine(f"sqlite:///{database}")
    with engine.begin() as connection:
        expected = _seed_populated_legacy_periods(connection)
    engine.dispose()

    command.upgrade(config, "head")

    engine = create_engine(f"sqlite:///{database}")
    with engine.connect() as connection:
        rows = {
            row.id: row
            for row in connection.execute(
                text("SELECT * FROM account_period ORDER BY id")
            ).mappings()
        }
        assert set(rows) == {1, 2, 3, 4, 5}
        assert datetime.fromisoformat(rows[1]["snapshot_at"]) == expected["ended_snapshot"]
        assert Decimal(rows[1]["opening_balance"]) == Decimal("10.123456789012345678")
        assert rows[1]["closed_at"] is None
        assert rows[1]["closing_balance"] is None
        assert datetime.fromisoformat(rows[2]["snapshot_at"]) == expected["current_snapshot"]
        assert Decimal(rows[2]["opening_balance"]) == Decimal("100")
        assert datetime.fromisoformat(rows[3]["snapshot_at"]) == expected["closed_snapshot"]
        assert Decimal(rows[3]["opening_balance"]) == Decimal("50")
        assert datetime.fromisoformat(rows[3]["closed_at"]) == expected["closed_at"]
        assert Decimal(rows[3]["closing_balance"]) == Decimal("45")
        assert datetime.fromisoformat(rows[5]["snapshot_at"]) == expected[
            "successor_snapshot"
        ]
        assert Decimal(rows[5]["opening_balance"]) == Decimal("150")
        assert {
            row["rollover_policy"] for row in rows.values()
        } == {"redistribute_remaining_days"}
        columns = {
            column["name"] for column in inspect(connection).get_columns("account_period")
        }
        assert "funding_amount" not in columns
        assert connection.execute(text("SELECT count(*) FROM rebase_event")).scalar_one() == 1
        assert connection.execute(
            text("SELECT account_period_id FROM rebase_event WHERE id = 1")
        ).scalar_one() == 1
    engine.dispose()


def test_period_snapshot_migration_rejects_future_legacy_start_without_changes(
    tmp_path: Path,
):
    database = tmp_path / "future-period.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database}")
    command.upgrade(config, "0001_release_v2")
    engine = create_engine(f"sqlite:///{database}")
    with engine.begin() as connection:
        _seed_populated_legacy_periods(connection, future_start=True)
    engine.dispose()

    with pytest.raises(RuntimeError, match="future start_date"):
        command.upgrade(config, "head")

    engine = create_engine(f"sqlite:///{database}")
    with engine.connect() as connection:
        assert connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one() == "0001_release_v2"
        assert connection.execute(text("SELECT count(*) FROM account_period")).scalar_one() == 5
        columns = {
            column["name"] for column in inspect(connection).get_columns("account_period")
        }
        assert "funding_amount" in columns
        assert "snapshot_at" not in columns
        assert "account_period_v21" not in inspect(connection).get_table_names()
    engine.dispose()


def test_period_snapshot_populated_downgrade_and_reupgrade(tmp_path: Path):
    database = tmp_path / "period-roundtrip.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database}")
    command.upgrade(config, "0001_release_v2")
    engine = create_engine(f"sqlite:///{database}")
    with engine.begin() as connection:
        _seed_populated_legacy_periods(connection)
    engine.dispose()

    command.upgrade(config, "head")
    command.downgrade(config, "0001_release_v2")

    engine = create_engine(f"sqlite:///{database}")
    with engine.connect() as connection:
        assert connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one() == "0001_release_v2"
        assert connection.execute(text("SELECT count(*) FROM account_period")).scalar_one() == 5
        assert Decimal(
            connection.execute(
                text("SELECT funding_amount FROM account_period WHERE id = 1")
            ).scalar_one()
        ) == Decimal("10.123456789012345678")
        assert connection.execute(
            text("SELECT account_period_id FROM rebase_event WHERE id = 1")
        ).scalar_one() == 1
        period_indexes = {
            index["name"] for index in inspect(connection).get_indexes("account_period")
        }
        assert "ix_account_period_account_id" in period_indexes
        assert "ix_account_period_end_date" in period_indexes
    engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{database}")
    with engine.connect() as connection:
        assert connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one() == "0002_period_snapshot_model"
        assert connection.execute(text("SELECT count(*) FROM account_period")).scalar_one() == 5
        assert connection.execute(text("SELECT count(*) FROM rebase_event")).scalar_one() == 1
    engine.dispose()


def test_transaction_origin_constraint_accepts_only_release_values(
    tmp_path: Path, monkeypatch
):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    database = tmp_path / "origin-v2.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database}")
    command.upgrade(config, "head")

    engine = create_engine(f"sqlite:///{database}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO user "
                "(username, normalized_username, display_name, password_hash, timezone, "
                "is_active, created_at, updated_at) "
                "VALUES ('user', 'user', 'User', 'hash', 'UTC', 1, "
                "'2026-01-01', '2026-01-01')"
            )
        )
        asset_id = connection.execute(
            text("SELECT id FROM asset WHERE code = 'USD'")
        ).scalar_one()
        connection.execute(
            text(
                "INSERT INTO workspace "
                "(owner_user_id, name, base_asset_id, timezone, created_at) "
                "VALUES (1, 'Workspace', :asset_id, 'UTC', '2026-01-01')"
            ),
            {"asset_id": asset_id},
        )

    insert = text(
        "INSERT INTO financial_transaction "
        "(workspace_id, created_by_user_id, type, occurred_at, local_date, origin, "
        "status, created_at, updated_at) "
        "VALUES (1, 1, 'expense', '2026-01-01', '2026-01-01', :origin, "
        "'posted', '2026-01-01', '2026-01-01')"
    )
    with engine.begin() as connection:
        connection.execute(insert, {"origin": "manual"})
        connection.execute(insert, {"origin": "operations"})
    with engine.begin() as connection:
        try:
            connection.execute(insert, {"origin": "planned"})
        except IntegrityError:
            pass
        else:
            raise AssertionError("invalid transaction origin was accepted")
    engine.dispose()


def test_phase9_progress_records_recoverable_backup_evidence():
    progress = Path("docs/history/PROGRESS-phases-8-13.md").read_text()
    assert ".backups/finapp-pre-v2-" in progress
    assert "/private/tmp/finapp-phase9-restore-" in progress
    assert "`PRAGMA integrity_check` — `ok`" in progress
    checksum = re.search(r"backup SHA-256\s+`([0-9a-f]{64})`", progress)
    assert checksum is not None


def test_openapi_has_no_removed_tracker_commitment_or_plan_execution_routes():
    from app.main import app

    paths = set(app.openapi()["paths"])
    forbidden_fragments = (
        "/tracker",
        "/budget-periods",
        "/budget-commitments",
        "/pay",
        "/receive",
    )
    assert not {
        path
        for path in paths
        if any(fragment in path for fragment in forbidden_fragments)
    }


def test_fresh_v2_schema_has_no_alembic_metadata_drift(
    tmp_path: Path, monkeypatch
):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    database = tmp_path / "metadata-v2.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database}")

    command.upgrade(config, "head")
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Cannot correctly sort tables.*",
            category=SAWarning,
        )
        command.check(config)

    engine = create_engine(f"sqlite:///{database}")
    inspector = inspect(engine)
    unique_columns = {
        "user": "normalized_username",
        "asset": "code",
        "auth_session": "token_hash",
        "account_invitation": "token_hash",
        "plan_occurrence": "transaction_id",
    }
    for table_name, column_name in unique_columns.items():
        assert any(
            constraint["column_names"] == [column_name]
            for constraint in inspector.get_unique_constraints(table_name)
        )
        assert any(
            index["name"] == f"ix_{table_name}_{column_name}"
            and index["column_names"] == [column_name]
            and not index["unique"]
            for index in inspector.get_indexes(table_name)
        )
    engine.dispose()


def test_migrated_scratch_database_runs_real_application_lifespan(
    tmp_path: Path, monkeypatch
):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    database = tmp_path / "lifespan-v2.db"
    async_url = f"sqlite+aiosqlite:///{database}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", async_url)
    command.upgrade(config, "head")

    script = textwrap.dedent(
        """
        import asyncio

        from httpx import ASGITransport, AsyncClient
        from sqlalchemy import func, select


        async def verify():
            from app.db import SessionLocal, engine
            from app.main import app
            from app.models import Asset

            async with app.router.lifespan_context(app):
                async with SessionLocal() as session:
                    count = await session.scalar(select(func.count(Asset.id)))
                    assert count == 8, count
                transport = ASGITransport(app=app)
                async with AsyncClient(
                    transport=transport,
                    base_url="http://scratch",
                ) as client:
                    response = await client.get("/health")
                    assert response.status_code == 200, response.text
                    assert response.json() == {"status": "ok"}
            await engine.dispose()


        asyncio.run(verify())
        """
    )
    environment = os.environ.copy()
    environment["DATABASE_URL"] = async_url
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).parents[1],
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    engine = create_engine(f"sqlite:///{database}")
    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version"))
            .scalar_one()
            == "0002_period_snapshot_model"
        )
        assert connection.execute(text("SELECT count(*) FROM asset")).scalar_one() == 8
        assert connection.execute(text("SELECT count(*) FROM user")).scalar_one() == 0
    engine.dispose()
