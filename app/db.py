"""Async engine / session setup.

SQLite via aiosqlite for local dev (zero setup). Switching to Postgres later
is only a connection-string change — set DATABASE_URL, e.g.
`postgresql+asyncpg://user:pass@host/dbname`.
"""

import os
from typing import AsyncIterator

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    # SQLite ships with foreign-key enforcement OFF; turn it on so
    # ON DELETE CASCADE actually works. No-op for other databases.
    if "sqlite" in type(dbapi_connection).__module__:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///./finapp.db"
DATABASE_URL = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

# Exists solely for the one-time migration rename below; never used otherwise.
_LEGACY_DB_FILE = "tzlvt.db"

if DATABASE_URL == DEFAULT_DATABASE_URL:
    # One-time data migration for the app rename (default SQLite URL only):
    # adopt the old DB file if the new one doesn't exist yet.
    _new_db_file = DEFAULT_DATABASE_URL.rsplit("/", 1)[-1]
    if not os.path.exists(_new_db_file) and os.path.exists(_LEGACY_DB_FILE):
        os.replace(_LEGACY_DB_FILE, _new_db_file)

engine = create_async_engine(DATABASE_URL)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
