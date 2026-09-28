from datetime import datetime, timezone
from typing import Any, Dict, Generic, List, Optional, TypeVar
from pydantic import BaseModel, ConfigDict, Field


def get_current_utc_timestamp() -> datetime:
    return datetime.now(timezone.utc)


T = TypeVar("T")


class BaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    success: bool = True
    timestamp: datetime = Field(default_factory=get_current_utc_timestamp)


class ApiResponse(BaseResponse, Generic[T]):
    """
    Standard envelope for all successful single-object API responses.
    """
    data: T
    message: Optional[str] = None


class PaginationMeta(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool


class PaginatedResponse(BaseResponse, Generic[T]):
    """
    Standard envelope for paginated listing API responses.
    """
    data: List[T]
    meta: PaginationMeta


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: List[Dict[str, Any]] = Field(default_factory=list)


class ErrorEnvelope(BaseModel):
    success: bool = False
    error: ErrorDetail
    timestamp: datetime = Field(default_factory=get_current_utc_timestamp)


class HealthResponse(BaseModel):
    status: str = "healthy"
    service: str
    version: str
    environment: str
    database_connected: bool
    timestamp: datetime = Field(default_factory=get_current_utc_timestamp)
