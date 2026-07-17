"""Migration checks against the real pre-family schema and stored values."""

from pathlib import Path
import sqlite3

from alembic import command
from alembic.config import Config


def _config(db_path: Path) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{db_path}")
    return config


def test_family_migrations_preserve_legacy_period_and_operations(tmp_path):
    db_path = tmp_path / "legacy.db"
    config = _config(db_path)
    command.upgrade(config, "0003")

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO period "
            "(id,total_amount,start_date,end_date,created_at,prompt_ack_date) "
            "VALUES (7,'1000','2026-07-01','2026-07-31',"
            "'2026-07-01 08:00:00',NULL)"
        )
        conn.execute(
            "INSERT INTO expense "
            "(id,period_id,amount,comment,created_at,kind) "
            "VALUES (11,7,'123.45','food','2026-07-03 12:30:00','expense')"
        )
        conn.commit()

    command.upgrade(config, "head")

    with sqlite3.connect(db_path) as conn:
        period = conn.execute(
            "SELECT id,total_amount,workspace_id FROM period"
        ).fetchone()
        operation = conn.execute(
            "SELECT id,period_id,amount,comment,kind,occurred_on FROM operation"
        ).fetchone()
        workspace = conn.execute(
            "SELECT id,name,kind FROM workspace"
        ).fetchone()
        auth_tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name IN ('user','auth_session')"
            )
        }
        operation_columns = {
            row[1]: row[2] for row in conn.execute("PRAGMA table_info(operation)")
        }

    assert period == (7, "1000", 1)
    assert operation == (
        11,
        7,
        "123.45",
        "food",
        "expense",
        "2026-07-03",
    )
    assert workspace == (1, "Personal", "personal")
    assert auth_tables == {"user", "auth_session"}
    assert operation_columns["kind"] == "VARCHAR(32)"
