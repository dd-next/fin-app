import os
from pathlib import Path
import subprocess
import sys
import textwrap
import warnings
import re

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
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0001_release_v2"
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
            "funding_amount",
            "created_at",
            "closed_at",
        } <= {item["name"] for item in inspector.get_columns("account_period")}
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
    progress = Path("docs/PROGRESS.md").read_text()
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
            == "0001_release_v2"
        )
        assert connection.execute(text("SELECT count(*) FROM asset")).scalar_one() == 8
        assert connection.execute(text("SELECT count(*) FROM user")).scalar_one() == 0
    engine.dispose()
