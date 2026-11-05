"""Test fixtures for Decision Ledger.

Uses a real PostgreSQL database (TEST_DATABASE_URL env var).
Each test gets its own engine + transactional rollback for isolation.
CI applies schema.sql and views.sql via psql before pytest runs.
"""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from api.database import get_db
from api.main import app

TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://ledger_user:test_password@localhost:5432/decision_ledger_test",
)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(TEST_DB_URL, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with engine.connect() as conn:
        await conn.begin()
        async with factory(bind=conn) as session:
            yield session
        await conn.rollback()
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    @asynccontextmanager
    async def _test_lifespan(_app):
        yield

    orig_lifespan = app.router.lifespan_context
    app.router.lifespan_context = _test_lifespan

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
    app.router.lifespan_context = orig_lifespan


TEST_API_KEY = "test-secret-key"

os.environ.setdefault("API_KEY", TEST_API_KEY)
os.environ.setdefault("DB_PASSWORD", "test_password")

WRITE_HEADERS = {"X-API-Key": TEST_API_KEY}


def make_decision_payload(**overrides) -> dict:
    from datetime import date, timedelta

    defaults = {
        "title": "Test decision about pricing strategy",
        "category": "pricing",
        "context": "We need to decide on a pricing change. " * 3,
        "options_considered": [
            {
                "option": "Hold price",
                "pros": ["no churn risk"],
                "cons": ["margin compression"],
            },
            {
                "option": "Raise by $4",
                "pros": ["margin recovery"],
                "cons": ["potential 3% churn"],
            },
        ],
        "data_consulted": ["NPS survey", "Competitor pricing analysis"],
        "decision_made": "Raise price by $4 effective next month.",
        "rationale": "Margin compression is unsustainable. Elasticity data supports this move.",
        "expected_outcome": "Churn ≤3% at 90 days; ARR lift ≥$500K.",
        "review_date": (date.today() + timedelta(days=90)).isoformat(),
        "team": "Finance",
        "owner": "Nadia Osei",
    }
    defaults.update(overrides)
    return defaults
