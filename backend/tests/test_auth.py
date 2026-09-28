import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.core.security import get_password_hash, create_access_token
from app.main import app
from app.models.user import User


@pytest_asyncio.fixture
async def test_db():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

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

    # Seed an initial Admin, Packaging, and Delivery user
    async with session_maker() as session:
        admin = User(
            email="admin@opsmind.io",
            hashed_password=get_password_hash("AdminPass123!"),
            full_name="Operations Admin",
            role="ADMIN",
            is_active=True,
        )
        packager = User(
            email="packager@opsmind.io",
            hashed_password=get_password_hash("PackPass123!"),
            full_name="Packager One",
            role="PACKAGING",
            is_active=True,
        )
        deactivated = User(
            email="inactive@opsmind.io",
            hashed_password=get_password_hash("InactivePass123!"),
            full_name="Deactivated Staff",
            role="DELIVERY",
            is_active=False,
        )
        session.add_all([admin, packager, deactivated])
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    await test_engine.dispose()


@pytest.mark.asyncio
async def test_login_success(test_db: AsyncClient):
    response = await test_db.post(
        "/api/v1/auth/login",
        json={"email": "admin@opsmind.io", "password": "AdminPass123!"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert "access_token" in payload["data"]
    assert "refresh_token" in payload["data"]
    assert payload["data"]["user"]["email"] == "admin@opsmind.io"
    assert payload["data"]["user"]["role"] == "ADMIN"


@pytest.mark.asyncio
async def test_login_invalid_password(test_db: AsyncClient):
    response = await test_db.post(
        "/api/v1/auth/login",
        json={"email": "admin@opsmind.io", "password": "WrongPassword123!"},
    )
    assert response.status_code == 401
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "AUTHENTICATION_FAILED"


@pytest.mark.asyncio
async def test_login_deactivated_user(test_db: AsyncClient):
    response = await test_db.post(
        "/api/v1/auth/login",
        json={"email": "inactive@opsmind.io", "password": "InactivePass123!"},
    )
    assert response.status_code == 401
    payload = response.json()
    assert payload["success"] is False
    assert "deactivated" in payload["error"]["message"].lower()


@pytest.mark.asyncio
async def test_get_current_user_me(test_db: AsyncClient):
    # First login to get token
    login_res = await test_db.post(
        "/api/v1/auth/login",
        json={"email": "packager@opsmind.io", "password": "PackPass123!"},
    )
    token = login_res.json()["data"]["access_token"]

    # Call /auth/me
    response = await test_db.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["email"] == "packager@opsmind.io"
    assert payload["data"]["role"] == "PACKAGING"


@pytest.mark.asyncio
async def test_refresh_token_lifecycle(test_db: AsyncClient):
    login_res = await test_db.post(
        "/api/v1/auth/login",
        json={"email": "admin@opsmind.io", "password": "AdminPass123!"},
    )
    refresh_token = login_res.json()["data"]["refresh_token"]

    refresh_res = await test_db.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_res.status_code == 200
    payload = refresh_res.json()
    assert payload["success"] is True
    assert "access_token" in payload["data"]


@pytest.mark.asyncio
async def test_admin_crud_employee_management(test_db: AsyncClient):
    # Login as admin
    login_res = await test_db.post(
        "/api/v1/auth/login",
        json={"email": "admin@opsmind.io", "password": "AdminPass123!"},
    )
    admin_token = login_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Create a new Delivery driver
    create_res = await test_db.post(
        "/api/v1/admin/employees",
        headers=headers,
        json={
            "email": "driver1@opsmind.io",
            "password": "SecureDriverPassword123!",
            "full_name": "Dave Driver",
            "role": "DELIVERY",
        },
    )
    assert create_res.status_code == 201
    driver_data = create_res.json()["data"]
    driver_id = driver_data["id"]
    assert driver_data["role"] == "DELIVERY"
    assert driver_data["is_active"] is True

    # 2. List employees
    list_res = await test_db.get("/api/v1/admin/employees", headers=headers)
    assert list_res.status_code == 200
    assert list_res.json()["meta"]["total"] >= 4

    # 3. Update employee details
    patch_res = await test_db.patch(
        f"/api/v1/admin/employees/{driver_id}",
        headers=headers,
        json={"full_name": "Dave Senior Driver"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["data"]["full_name"] == "Dave Senior Driver"

    # 4. Soft-delete employee
    del_res = await test_db.delete(
        f"/api/v1/admin/employees/{driver_id}",
        headers=headers,
    )
    assert del_res.status_code == 200
    assert del_res.json()["data"]["is_active"] is False


@pytest.mark.asyncio
async def test_rbac_operator_forbidden_from_admin_employees(test_db: AsyncClient):
    # Login as Packaging operator
    login_res = await test_db.post(
        "/api/v1/auth/login",
        json={"email": "packager@opsmind.io", "password": "PackPass123!"},
    )
    packager_token = login_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {packager_token}"}

    # Try accessing admin employee management
    res = await test_db.get("/api/v1/admin/employees", headers=headers)
    assert res.status_code == 403
    payload = res.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "PERMISSION_DENIED"


@pytest.mark.asyncio
async def test_unauthenticated_request_rejected(test_db: AsyncClient):
    res = await test_db.get("/api/v1/auth/me")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "AUTHENTICATION_FAILED"
