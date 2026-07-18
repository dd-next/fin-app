import os
from pathlib import Path
import subprocess
import sys
import textwrap
import warnings

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SAWarning


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
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0005_v2"
        assert connection.execute(text("SELECT count(*) FROM asset")).scalar_one() == 8
        assert set(inspect(connection).get_table_names()) == {
            "account", "account_access", "account_invitation", "alembic_version",
            "asset", "auth_session", "category", "exchange_rate",
            "financial_transaction", "plan_occurrence", "plan_rule",
            "budget_period", "budget_commitment", "rebase_event",
            "transaction_leg", "user", "workspace",
        }
    engine.dispose()


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
            == "0005_v2"
        )
        assert connection.execute(text("SELECT count(*) FROM asset")).scalar_one() == 8
        assert connection.execute(text("SELECT count(*) FROM user")).scalar_one() == 0
    engine.dispose()
