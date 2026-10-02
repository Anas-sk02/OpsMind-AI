from contextlib import asynccontextmanager
import logging
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1.health import health_check
from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.database import engine
from app.core.exceptions import register_exception_handlers
from app.schemas.common import HealthResponse

import asyncio
from app.init_db import init_database
from app.core.database import async_session_factory
from app.services.imap_service import ImapService

# Configure structured logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("opsmind.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager for startup, database initialization, background IMAP poller, and graceful shutdown.
    """
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION} [{settings.ENVIRONMENT}]")
    try:
        await init_database()
    except Exception as exc:
        logger.warning(f"Database initialization hook warning (will retry on query): {exc}")

    poller_task: Optional[asyncio.Task] = None
    imap_user = settings.IMAP_USER or settings.SMTP_USER
    if settings.ENVIRONMENT != "testing" and settings.IMAP_ENABLED and imap_user:
        logger.info(f"[Lifespan] Launching asynchronous IMAP mailbox poller for '{imap_user}'...")
        poller_task = asyncio.create_task(
            ImapService.run_poller_background_loop(async_session_factory)
        )

    yield

    if poller_task and not poller_task.done():
        logger.info("[Lifespan] Cancelling IMAP background poller...")
        poller_task.cancel()
        try:
            await asyncio.wait_for(poller_task, timeout=5.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass

    logger.info("Shutting down application and disposing database connection pools...")
    await engine.dispose()
    logger.info("Database connection pools disposed successfully.")


def create_application() -> FastAPI:
    """
    FastAPI Application Factory.
    """
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url=f"{settings.API_V1_STR}/docs",
        redoc_url=f"{settings.API_V1_STR}/redoc",
        lifespan=lifespan,
    )

    # Configure CORS Middleware
    if settings.BACKEND_CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Register Exception Handlers
    register_exception_handlers(app)

    # Root health endpoint for container probes
    app.get("/health", response_model=HealthResponse, tags=["Health & Status"])(health_check)

    # Include consolidated API v1 router
    app.include_router(api_v1_router, prefix=settings.API_V1_STR)

    return app


app = create_application()
