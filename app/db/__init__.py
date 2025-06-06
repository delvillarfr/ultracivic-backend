"""
Database Connection Management

This module provides async database connectivity using SQLAlchemy's async engine
with PostgreSQL. It establishes connection pooling with health checks and
provides a dependency injection function for FastAPI routes to obtain
database sessions.

The async session pattern ensures proper resource cleanup and supports
concurrent request handling without blocking the event loop.
"""

from typing import AsyncGenerator
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url, 
    echo=False, 
    pool_pre_ping=True,
    future=True
)

AsyncSessionLocal = async_sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide async database session for dependency injection."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

