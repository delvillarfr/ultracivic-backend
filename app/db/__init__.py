# app/db/__init__.py
from contextlib import asynccontextmanager
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url, echo=False, pool_pre_ping=True
)

@asynccontextmanager
async def get_session():
    async with AsyncSession(engine) as session:
        yield session

