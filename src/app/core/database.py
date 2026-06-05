"""Async SQLAlchemy engine, session factory and FastAPI session dependency."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

_db_uri = settings.sqlalchemy_database_uri
_engine_kwargs: dict = {
    "echo": settings.debug and settings.environment == "development",
    "future": True,
}
# QueuePool sizing only applies to server-backed dialects (e.g. PostgreSQL);
# SQLite (used in tests) rejects these arguments.
if not _db_uri.startswith("sqlite"):
    _engine_kwargs.update(pool_pre_ping=True, pool_size=10, max_overflow=20)

engine: AsyncEngine = create_async_engine(_db_uri, **_engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a transactional session.

    Commits on success, rolls back on error, always closes.
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
