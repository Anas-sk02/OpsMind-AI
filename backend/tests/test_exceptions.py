import pytest
from httpx import AsyncClient
from fastapi import APIRouter
from app.main import app
from app.core.exceptions import (
    NotFoundException,
    ForbiddenException,
    StateTransitionException,
    InsufficientStockException,
)

# Create a temporary demo router to trigger exception handling
sample_exception_router = APIRouter(prefix="/sample-exceptions")


@sample_exception_router.get("/not-found")
async def trigger_not_found():
    raise NotFoundException(message="Item with ID 999 not found", code="ITEM_NOT_FOUND")


@sample_exception_router.get("/forbidden")
async def trigger_forbidden():
    raise ForbiddenException(message="Role delivery cannot access admin panel")


@sample_exception_router.get("/state-transition")
async def trigger_state_transition():
    raise StateTransitionException(message="Cannot transition from CANCELLED to PACKAGING")


@sample_exception_router.get("/insufficient-stock")
async def trigger_stock_error():
    raise InsufficientStockException(message="Requested 10 units, but only 2 available")


app.include_router(sample_exception_router)


@pytest.mark.asyncio
async def test_not_found_exception_envelope(client: AsyncClient):
    response = await client.get("/sample-exceptions/not-found")
    assert response.status_code == 404
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "ITEM_NOT_FOUND"
    assert "999 not found" in payload["error"]["message"]
    assert "timestamp" in payload


@pytest.mark.asyncio
async def test_forbidden_exception_envelope(client: AsyncClient):
    response = await client.get("/sample-exceptions/forbidden")
    assert response.status_code == 403
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "PERMISSION_DENIED"


@pytest.mark.asyncio
async def test_state_transition_exception_envelope(client: AsyncClient):
    response = await client.get("/sample-exceptions/state-transition")
    assert response.status_code == 422
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "ILLEGAL_STATE_TRANSITION"


@pytest.mark.asyncio
async def test_insufficient_stock_exception_envelope(client: AsyncClient):
    response = await client.get("/sample-exceptions/insufficient-stock")
    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "INSUFFICIENT_STOCK"

