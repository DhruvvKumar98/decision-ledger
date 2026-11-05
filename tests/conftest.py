"""Test fixtures for Decision Ledger.

Uses a real PostgreSQL database (TEST_DATABASE_URL env var).
Each test function gets a fresh schema via transactional rollback.
CI spins up a PostgreSQL 16 service container (see .github/workflows/ci.yml).
"""

import asyncio
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from api.database import get_db
from api.main import app
from api.models import Base

TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://ledger_user:test_password@localhost:5432/decision_ledger_test",
)

_VIEWS_SQL_PATH = Path(__file__).resolve().parent.parent / "db" / "views.sql"

_DROP_VIEWS = text(
    "DO $$ DECLARE r RECORD; BEGIN "
    "FOR r IN SELECT viewname FROM pg_views WHERE schemaname = 'public' LOOP "
    "EXECUTE 'DROP VIEW IF EXISTS ' || quote_ident(r.viewname) || ' CASCADE'; "
    "END LOOP; END $$;"
)

# ponytail: single event loop for all tests — required so the engine pool
# and every fixture share the same loop.
@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


_test_engine = None
_test_session_factory = None


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_tables():
    global _test_engine, _test_session_factory
    _test_engine = create_async_engine(TEST_DB_URL, echo=False)
    _test_session_factory = async_sessionmaker(
        _test_engine, expire_on_commit=False, class_=AsyncSession
    )
    async with _test_engine.begin() as conn:
        await conn.execute(_DROP_VIEWS)
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        raw = await conn.get_raw_connection()
        await raw.driver_connection.execute(_VIEWS_SQL_PATH.read_text())
    yield
    async with _test_engine.begin() as conn:
        await conn.execute(_DROP_VIEWS)
        await conn.run_sync(Base.metadata.drop_all)
    await _test_engine.dispose()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with _test_engine.connect() as conn:
        await conn.begin()
        async with _test_session_factory(bind=conn) as session:
            yield session
        await conn.rollback()


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
