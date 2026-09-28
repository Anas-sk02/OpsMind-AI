import asyncio
import os
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from typing import AsyncGenerator

# Set testing environment variable before importing app
os.environ["ENVIRONMENT"] = "testing"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

from app.main import app
from app.core.config import settings


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """
    Async HTTP client fixture for endpoint testing.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
