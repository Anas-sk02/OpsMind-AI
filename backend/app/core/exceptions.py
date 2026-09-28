from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("opsmind.exceptions")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AppException(Exception):
    """
    Base domain exception for all OpsMind application errors.
    """
    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_SERVER_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[List[Dict[str, Any]]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or []


class NotFoundException(AppException):
    def __init__(self, message: str = "Resource not found", code: str = "RESOURCE_NOT_FOUND", details: Optional[List[Dict[str, Any]]] = None):
        super().__init__(message=message, code=code, status_code=status.HTTP_404_NOT_FOUND, details=details)


class ValidationException(AppException):
    def __init__(self, message: str = "Validation failed", code: str = "VALIDATION_ERROR", details: Optional[List[Dict[str, Any]]] = None):
        super().__init__(message=message, code=code, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, details=details)


class AuthenticationException(AppException):
    def __init__(self, message: str = "Authentication required or invalid credentials", code: str = "AUTHENTICATION_FAILED", details: Optional[List[Dict[str, Any]]] = None):
        super().__init__(message=message, code=code, status_code=status.HTTP_401_UNAUTHORIZED, details=details)


class ForbiddenException(AppException):
    def __init__(self, message: str = "Insufficient permissions for this resource", code: str = "PERMISSION_DENIED", details: Optional[List[Dict[str, Any]]] = None):
        super().__init__(message=message, code=code, status_code=status.HTTP_403_FORBIDDEN, details=details)


class ConflictException(AppException):
    def __init__(self, message: str = "Resource conflict", code: str = "RESOURCE_CONFLICT", details: Optional[List[Dict[str, Any]]] = None):
        super().__init__(message=message, code=code, status_code=status.HTTP_409_CONFLICT, details=details)


class StateTransitionException(AppException):
    def __init__(self, message: str = "Illegal state transition", code: str = "ILLEGAL_STATE_TRANSITION", details: Optional[List[Dict[str, Any]]] = None):
        super().__init__(message=message, code=code, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, details=details)


class InsufficientStockException(AppException):
    def __init__(self, message: str = "Insufficient stock available for requested quantity", code: str = "INSUFFICIENT_STOCK", details: Optional[List[Dict[str, Any]]] = None):
        super().__init__(message=message, code=code, status_code=status.HTTP_400_BAD_REQUEST, details=details)


def format_error_response(code: str, message: str, details: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    return {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "details": details or [],
        },
        "timestamp": utc_now_iso(),
    }


def register_exception_handlers(app: FastAPI) -> None:
    """
    Registers custom exception handlers on the FastAPI instance to ensure
    all error responses adhere strictly to the standard JSON error envelope.
    """

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        logger.warning(f"AppException on {request.method} {request.url.path}: {exc.code} - {exc.message}")
        return JSONResponse(
            status_code=exc.status_code,
            content=format_error_response(code=exc.code, message=exc.message, details=exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        formatted_details = []
        for error in exc.errors():
            loc = " -> ".join(str(l) for l in error.get("loc", []))
            formatted_details.append({
                "field": loc,
                "type": error.get("type", "value_error"),
                "message": error.get("msg", "Invalid value"),
            })
        logger.info(f"Validation error on {request.method} {request.url.path}: {formatted_details}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=format_error_response(
                code="REQUEST_VALIDATION_ERROR",
                message="The submitted request payload failed schema validation.",
                details=formatted_details,
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code_map = {
            400: "BAD_REQUEST",
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            409: "CONFLICT",
            422: "UNPROCESSABLE_ENTITY",
            500: "INTERNAL_SERVER_ERROR",
        }
        error_code = code_map.get(exc.status_code, "HTTP_ERROR")
        detail_msg = str(exc.detail) if exc.detail else "An HTTP error occurred."
        return JSONResponse(
            status_code=exc.status_code,
            content=format_error_response(
                code=error_code,
                message=detail_msg,
                details=[],
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(f"Unhandled Exception on {request.method} {request.url.path}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=format_error_response(
                code="INTERNAL_SERVER_ERROR",
                message="An unexpected internal server error occurred. Please contact system support.",
                details=[],
            ),
        )
