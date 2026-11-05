"""Test fixtures for Decision Ledger.

Uses a real PostgreSQL database (TEST_DATABASE_URL env var).
Each test function gets a fresh schema via transactional rollback.
CI spins up a PostgreSQL 16 service container (see .github/workflows/ci.yml).
"""

import os
from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import api.main as _main_mod
from api.database import get_db
from api.main import app
from api.models import Base

TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://ledger_user:test_password@localhost:5432/decision_ledger_test",
)

# ponytail: views depend on tables, so drop_all fails without CASCADE
_DROP_VIEWS = text(
    "DO $$ DECLARE r RECORD; BEGIN "
    "FOR r IN SELECT viewname FROM pg_views WHERE schemaname = 'public' LOOP "
    "EXECUTE 'DROP VIEW IF EXISTS ' || quote_ident(r.viewname) || ' CASCADE'; "
    "END LOOP; END $$;"
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_tables():
    """Create engine on the session event loop, create tables, tear down after."""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.execute(_DROP_VIEWS)
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.execute(_DROP_VIEWS)
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(create_tables) -> AsyncGenerator[AsyncSession, None]:
    """Each test runs inside a transaction that is rolled back on completion."""
    session_factory = async_sessionmaker(create_tables, expire_on_commit=False, class_=AsyncSession)
    async with create_tables.connect() as conn:
        await conn.begin()
        async with session_factory(bind=conn) as session:
            yield session
        await conn.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession, create_tables) -> AsyncGenerator[AsyncClient, None]:
    """Async test client with the test DB session injected."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    # ponytail: patch the engine the lifespan uses so it's on the test event loop
    _orig_engine = _main_mod.engine
    _main_mod.engine = create_tables

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
    _main_mod.engine = _orig_engine


# Test API key matches what verify_api_key will check
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
