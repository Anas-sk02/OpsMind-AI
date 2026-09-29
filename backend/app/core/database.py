from typing import AsyncGenerator
import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

logger = logging.getLogger("opsmind.database")


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy 2.0 declarative ORM models.
    """
    pass


import ssl

# Database engine configuration
engine_kwargs = {
    "echo": settings.DB_ECHO,
    "future": True,
}

# Add connection pool parameters & SSL for PostgreSQL / Supabase engines
if not settings.SQLALCHEMY_DATABASE_URI.startswith("sqlite"):
    engine_kwargs.update({
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
        "pool_pre_ping": True,
    })
    # If using Supabase or SSL mode is specified
    if "supabase" in settings.SQLALCHEMY_DATABASE_URI or settings.DB_SSL_MODE:
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        engine_kwargs["connect_args"] = {
            "ssl": ssl_ctx
        }

engine: AsyncEngine = create_async_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    **engine_kwargs
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency yielding an asynchronous SQLAlchemy database session.
    Automatically handles session closing upon request completion.
    """
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_db_health() -> bool:
    """
    Executes a simple probe query (SELECT 1) to verify database connectivity.
    """
    try:
        async with async_session_factory() as session:
            result = await session.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception as exc:
        logger.warning(f"Database health check probe failed: {exc}")
        return False
