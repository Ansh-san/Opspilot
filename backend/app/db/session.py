"""
OpsPilot — Database Session Management

Provides:
- async SQLAlchemy engine
- async session factory
- get_db() FastAPI dependency
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

from sqlalchemy import event
import pgvector.asyncpg

# ─── Engine ──────────────────────────────────────────────────────────────────
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.is_development,  # Log SQL in dev
    pool_pre_ping=True,            # Verify connection health
    pool_size=10,
    max_overflow=20,
)

@event.listens_for(engine.sync_engine, "connect")
def register_custom_types(dbapi_connection, connection_record):
    """Register pgvector's asyncpg codec upon new connection."""
    dbapi_connection.run_async(pgvector.asyncpg.register_vector)

# ─── Session factory ──────────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ─── Dependency ───────────────────────────────────────────────────────────────
async def get_db() -> AsyncSession:  # type: ignore[return]
    """
    FastAPI dependency that yields an async database session.

    Usage:
        @router.get("/...")
        async def my_endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
