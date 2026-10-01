"""
Test configuration and fixtures.

Uses pytest-asyncio with the "outer transaction + savepoint" isolation pattern:

  • setup_database (session-scoped) — creates tables once, drops after all tests using a sync engine.
  • db_session     (function-scoped) — each test gets its own DB connection with
    an outer BEGIN. The AsyncSession is bound to that connection with
    join_transaction_mode="create_savepoint", so every session.commit() inside
    a service method releases the current savepoint and starts a new one
    (data is visible within the test) instead of issuing a real COMMIT.
    After the test the outer connection is ROLLED BACK, giving zero data leakage
    between tests without touching asyncpg's transaction state incorrectly.
  • client         (function-scoped) — injects db_session via get_db override.
  • test_user      (function-scoped) — a fresh User + Org registered for each test.
  • test_user_headers (function-scoped) — valid JWT Bearer headers for test_user.
  • isolate_rate_limiter (autouse, function-scoped) — disables the limiter for ALL
    tests by default and restores original state in teardown. Tests that need to
    verify rate limiting must explicitly set limiter.enabled = True themselves.
"""

from __future__ import annotations

import os
import uuid as _uuid_mod
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.rate_limiter import limiter
from app.db.base import Base
from app.db.session import get_db
from app.main import app

# ─── Test database URL ────────────────────────────────────────────────────────
TEST_DATABASE_URL_ASYNC = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://opspilot:change_me_in_production@db:5432/opspilot_test",
)
TEST_DATABASE_URL_SYNC = TEST_DATABASE_URL_ASYNC.replace("postgresql+asyncpg://", "postgresql://")


# ─── Session-scoped: create/drop tables once ─────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Create all tables once for the session; drop them on teardown."""
    engine = create_engine(TEST_DATABASE_URL_SYNC, echo=False)

    # Enable pgvector extension manually since create_all doesn't run Alembic's raw SQL
    from sqlalchemy import text
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))

    Base.metadata.create_all(engine)

    # Seed the database so hardcoded test credentials (admin@demo-corp.io) work.
    from scripts.seed_data import seed
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    import asyncio

    async def _seed_test_db():
        async_engine = create_async_engine(TEST_DATABASE_URL_ASYNC, echo=False)
        async with AsyncSession(async_engine) as session:
            await seed(session)
        await async_engine.dispose()

    asyncio.run(_seed_test_db())

    yield
    Base.metadata.drop_all(engine)
    engine.dispose()


# ─── Rate limiter isolation (CRITICAL — autouse, function-scoped) ─────────────

@pytest.fixture(autouse=True)
def isolate_rate_limiter():
    """
    CRITICAL: Disable the rate limiter for ALL tests by default to prevent
    cascading 429 errors from rate-limit state bleeding between tests.
    Saves and restores the original limiter.enabled state around each test.

    Tests that explicitly need to verify rate-limiting behaviour (e.g.,
    test_rate_limiting_triggers) must set `limiter.enabled = True` inside
    their own body — it will be automatically restored after the test ends.
    """
    original_state = limiter.enabled
    limiter.enabled = False
    yield
    limiter.enabled = original_state


# ─── Function-scoped: outer-transaction + savepoint isolation ─────────────────

@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Each test gets its own engine and connection wrapped in an outer transaction.

    session.commit() inside service code becomes a savepoint release
    (join_transaction_mode="create_savepoint"), NOT a real DB commit.
    The entire connection is rolled back after the test, leaving zero trace.
    """
    # Create engine per-test so it's bound to the test's own asyncio event loop
    engine = create_async_engine(TEST_DATABASE_URL_ASYNC, echo=False)

    async with engine.connect() as conn:
        # Start the outer (real) transaction that wraps the whole test.
        await conn.begin()

        # Bind the session to this connection.
        async with AsyncSession(
            bind=conn,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        ) as session:
            yield session

        # Roll back the outer transaction — all test data vanishes cleanly.
        await conn.rollback()

    await engine.dispose()


# ─── Function-scoped: HTTP client with injected session ──────────────────────

@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTP test client that injects the test db_session into every request."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ─── Function-scoped: test_user + test_user_headers ──────────────────────────

@pytest_asyncio.fixture
async def test_user(client: AsyncClient) -> dict:
    """
    Register a fresh user with a unique org for each test.
    Returns the full response payload (including org_id, user_id).
    The test transaction rollback ensures this data is cleaned up automatically.
    """
    unique_slug = f"test-org-{_uuid_mod.uuid4().hex[:8]}"
    unique_email = f"test-user-{_uuid_mod.uuid4().hex[:8]}@test-org.example.com"

    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "org_name": "Test Organization",
            "org_slug": unique_slug,
            "full_name": "Test User",
            "email": unique_email,
            "password": "TestPass1!",
        },
    )
    assert resp.status_code == 201, f"test_user registration failed: {resp.text}"
    return resp.json()


@pytest_asyncio.fixture
async def test_user_headers(client: AsyncClient, test_user: dict) -> dict:
    """
    Return valid JWT Bearer headers for the test_user fixture.
    Logs in with the test user's credentials and returns Authorization headers.
    The test_user dict is the UserOut response from /register, which includes 'email'.
    """
    email = test_user["email"]  # UserOut schema includes email field directly

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "TestPass1!"},
    )
    assert resp.status_code == 200, f"test_user_headers login failed: {resp.text}"

    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
