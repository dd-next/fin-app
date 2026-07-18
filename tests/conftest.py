"""Isolated FinApp v2 API fixture."""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.assets import seed_default_assets
from app.db import get_session
from app.main import app
from app.models import Base


@pytest_asyncio.fixture
async def client():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        await seed_default_assets(session)

    async def override_session():
        async with sessions() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as value:
        yield value
    app.dependency_overrides.clear()
    await engine.dispose()


async def register(client: AsyncClient, username: str = "alice") -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "password": "correct-horse-battery",
            "display_name": username.title(),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()
