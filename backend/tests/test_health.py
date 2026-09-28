import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_health_endpoint(client: AsyncClient):
    """
    Tests that root /health endpoint returns 200 OK and expected structure.
    """
    response = await client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in ["healthy", "degraded"]
    assert "service" in payload
    assert "version" in payload
    assert "database_connected" in payload
    assert "timestamp" in payload


@pytest.mark.asyncio
async def test_api_v1_health_endpoint(client: AsyncClient):
    """
    Tests that /api/v1/health endpoint responds with matching health status.
    """
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "OpsMind AI Platform"
    assert "timestamp" in payload
