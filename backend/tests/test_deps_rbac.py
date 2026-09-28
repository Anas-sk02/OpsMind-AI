import pytest
from httpx import AsyncClient
from fastapi import APIRouter, Depends
from app.main import app
from app.api.deps import get_current_user_token, require_roles
from app.core.security import create_access_token

rbac_sample_router = APIRouter(prefix="/sample-rbac")


@rbac_sample_router.get("/protected")
async def protected_route(claims: dict = Depends(get_current_user_token)):
    return {"status": "authorized", "user": claims["user_id"]}


@rbac_sample_router.get("/admin-only")
async def admin_only_route(token_data: dict = Depends(require_roles(["ADMIN"]))):
    return {"status": "admin_granted", "role": token_data["role"]}


@rbac_sample_router.get("/operators-only")
async def operators_only_route(token_data: dict = Depends(require_roles(["PACKAGING", "DELIVERY"]))):
    return {"status": "operator_granted", "role": token_data["role"]}


app.include_router(rbac_sample_router)


@pytest.mark.asyncio
async def test_missing_auth_header_rejection(client: AsyncClient):
    res = await client.get("/sample-rbac/protected")
    assert res.status_code == 401
    payload = res.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "AUTHENTICATION_FAILED"


@pytest.mark.asyncio
async def test_invalid_token_rejection(client: AsyncClient):
    res = await client.get(
        "/sample-rbac/protected",
        headers={"Authorization": "Bearer invalid_garbage_token"}
    )
    assert res.status_code == 401
    payload = res.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "AUTHENTICATION_FAILED"


@pytest.mark.asyncio
async def test_admin_rbac_success(client: AsyncClient):
    admin_token = create_access_token(subject="admin-user-id", role="ADMIN")
    res = await client.get(
        "/sample-rbac/admin-only",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res.status_code == 200
    assert res.json()["status"] == "admin_granted"


@pytest.mark.asyncio
async def test_employee_forbidden_on_admin_route(client: AsyncClient):
    packaging_token = create_access_token(subject="pack-user-id", role="PACKAGING")
    res = await client.get(
        "/sample-rbac/admin-only",
        headers={"Authorization": f"Bearer {packaging_token}"}
    )
    assert res.status_code == 403
    payload = res.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "PERMISSION_DENIED"


@pytest.mark.asyncio
async def test_operator_rbac_multi_role(client: AsyncClient):
    delivery_token = create_access_token(subject="del-user-id", role="DELIVERY")
    res = await client.get(
        "/sample-rbac/operators-only",
        headers={"Authorization": f"Bearer {delivery_token}"}
    )
    assert res.status_code == 200
    assert res.json()["status"] == "operator_granted"


@pytest.mark.asyncio
async def test_supabase_custom_claims_token(client: AsyncClient):
    # Simulate a Supabase token with app_metadata role
    supabase_token = create_access_token(
        subject="supabase-admin-uuid-123",
        role="authenticated",
        extra_claims={
            "email": "admin@opsmind.io",
            "app_metadata": {"role": "ADMIN", "provider": "email"},
            "user_metadata": {"full_name": "Supabase Ops Admin"}
        }
    )
    res = await client.get(
        "/sample-rbac/admin-only",
        headers={"Authorization": f"Bearer {supabase_token}"}
    )
    assert res.status_code == 200
    assert res.json()["status"] == "admin_granted"
    assert res.json()["role"] == "ADMIN"
