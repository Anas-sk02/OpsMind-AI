from fastapi import APIRouter
from app.core.config import settings
from app.core.database import check_db_health
from app.schemas.common import HealthResponse

router = APIRouter(tags=["Health & Status"])


@router.get("/health", response_model=HealthResponse, summary="System Health Check")
async def health_check() -> HealthResponse:
    """
    Checks operational health of the OpsMind backend API and attached PostgreSQL database.
    """
    db_ok = await check_db_health()
    status = "healthy" if db_ok or settings.ENVIRONMENT == "testing" else "degraded"

    return HealthResponse(
        status=status,
        service=settings.PROJECT_NAME,
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        database_connected=db_ok,
    )
