from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def test_clean_v2_upgrade_builds_foundation_and_seeds_assets(tmp_path: Path):
    database = tmp_path / "fresh-v2.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database}")
    command.upgrade(config, "head")

    engine = create_engine(f"sqlite:///{database}")
    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0003_v2"
        assert connection.execute(text("SELECT count(*) FROM asset")).scalar_one() == 8
        assert set(inspect(connection).get_table_names()) == {
            "account", "account_access", "account_invitation", "alembic_version",
            "asset", "auth_session", "category", "exchange_rate",
            "financial_transaction", "transaction_leg", "user", "workspace",
        }
    engine.dispose()
