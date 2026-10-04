import asyncio
import os
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Set testing environment variable before importing app
os.environ["ENVIRONMENT"] = "testing"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["EMAIL_ENABLED"] = "false"
os.environ["SMTP_HOST"] = ""
os.environ["SMTP_USER"] = ""
os.environ["SMTP_PASSWORD"] = ""

from app.core.database import Base, get_db
from app.main import app
from app.core.config import settings

settings.EMAIL_ENABLED = False
settings.SMTP_HOST = None
settings.SMTP_USER = None
settings.SMTP_PASSWORD = None


# Module-level test engine shared across fixtures
_test_engine = None
_test_session_maker = None


def _get_test_engine():
    global _test_engine, _test_session_maker
    if _test_engine is None:
        _test_engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            echo=False,
            future=True,
        )
        _test_session_maker = async_sessionmaker(
            bind=_test_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _test_engine, _test_session_maker


@pytest_asyncio.fixture(autouse=True)
async def init_test_db():
    """
    Initializes an isolated in-memory SQLite schema for each test function
    and overrides FastAPI get_db dependency.
    """
    global _test_engine, _test_session_maker
    test_engine, session_maker = _get_test_engine()

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_db():
        async with session_maker() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()
    # Don't dispose engine here - keep for session fixture


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """
    Async HTTP client fixture for endpoint testing.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Direct database session fixture for service-layer tests (bypasses HTTP).
    Uses the same in-memory SQLite as the client fixture.
    """
    _, session_maker = _get_test_engine()
    async with session_maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@pytest_asyncio.fixture(autouse=True)
async def cleanup_test_engine():
    """Dispose test engine at end of test session."""
    yield
    global _test_engine
    if _test_engine:
        await _test_engine.dispose()
        _test_engine = None