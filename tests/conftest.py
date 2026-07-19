"""Isolated FinApp v2 API fixture."""

import pytest_asyncio
from datetime import date
from decimal import Decimal
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.assets import seed_default_assets
from app.db import get_session
from app.main import app
from app.models import Asset, Base, Transaction, TransactionLeg, User, Workspace, utcnow


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
        value._finapp_test_sessions = sessions
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


async def seed_unassigned_transaction(
    client: AsyncClient,
    *,
    amount: str,
    asset_code: str = "USD",
    local_date: date | None = None,
    username: str = "alice",
) -> int:
    """Seed an import-like unassigned row without restoring a public create route."""
    sessions = client._finapp_test_sessions
    async with sessions() as session:
        user = (
            await session.execute(select(User).where(User.username == username))
        ).scalar_one()
        workspace = (
            await session.execute(
                select(Workspace).where(Workspace.owner_user_id == user.id)
            )
        ).scalar_one()
        asset = (
            await session.execute(select(Asset).where(Asset.code == asset_code))
        ).scalar_one()
        now = utcnow()
        transaction = Transaction(
            workspace_id=workspace.id,
            created_by_user_id=user.id,
            type="expense",
            occurred_at=now,
            local_date=local_date or now.date(),
            origin="manual",
            status="unassigned",
        )
        transaction.legs.append(
            TransactionLeg(
                account_id=None,
                asset_id=asset.id,
                amount=-Decimal(amount),
            )
        )
        session.add(transaction)
        await session.commit()
        await session.refresh(transaction)
        return transaction.id
