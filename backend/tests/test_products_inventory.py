import uuid
import pytest
from httpx import AsyncClient
from decimal import Decimal

from app.core.security import create_access_token


@pytest.fixture
def admin_headers():
    admin_id = str(uuid.uuid4())
    token = create_access_token(
        subject=admin_id,
        role="ADMIN",
        extra_claims={"email": "admin_inv@opsmind.io", "app_metadata": {"role": "ADMIN"}},
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def operator_headers():
    op_id = str(uuid.uuid4())
    token = create_access_token(
        subject=op_id,
        role="PACKAGING",
        extra_claims={"email": "pack_inv@opsmind.io", "app_metadata": {"role": "PACKAGING"}},
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_product_creation_and_inventory_initialization(
    client: AsyncClient, admin_headers: dict
):
    payload = {
        "sku": "SKU-TEST-001",
        "name": "Wireless Mechanical Keyboard",
        "description": "RGB mechanical keyboard",
        "price": 129.99,
        "category": "Electronics",
        "initial_stock": 50,
        "reorder_level": 15,
    }
    res = await client.post("/api/v1/admin/products", json=payload, headers=admin_headers)
    assert res.status_code == 201
    data = res.json()["data"]
    assert data["sku"] == "SKU-TEST-001"
    assert data["available_qty"] == 50
    assert data["reserved_qty"] == 0
    assert data["total_qty"] == 50
    assert data["is_low_stock"] is False


@pytest.mark.asyncio
async def test_duplicate_sku_rejection(client: AsyncClient, admin_headers: dict):
    payload = {
        "sku": "SKU-DUP-001",
        "name": "Item One",
        "price": 10.00,
        "initial_stock": 5,
        "reorder_level": 2,
    }
    res1 = await client.post("/api/v1/admin/products", json=payload, headers=admin_headers)
    assert res1.status_code == 201

    res2 = await client.post("/api/v1/admin/products", json=payload, headers=admin_headers)
    assert res2.status_code == 409
    assert res2.json()["error"]["code"] == "RESOURCE_CONFLICT"


@pytest.mark.asyncio
async def test_stock_adjustment_and_movement_ledger(
    client: AsyncClient, admin_headers: dict
):
    # 1. Create product
    prod_payload = {
        "sku": "SKU-ADJUST-001",
        "name": "Noise Cancelling Headphones",
        "price": 199.99,
        "initial_stock": 20,
        "reorder_level": 5,
    }
    prod_res = await client.post("/api/v1/admin/products", json=prod_payload, headers=admin_headers)
    assert prod_res.status_code == 201
    product_id = prod_res.json()["data"]["id"]

    # 2. Adjust stock upwards (+15)
    adj_payload = {
        "product_id": product_id,
        "delta_qty": 15,
        "movement_type": "PURCHASE_RECEIPT",
        "reason": "Supplier shipment intake",
    }
    adj_res = await client.post("/api/v1/admin/inventory/adjust", json=adj_payload, headers=admin_headers)
    assert adj_res.status_code == 200
    assert adj_res.json()["data"]["available_qty"] == 35

    # 3. Adjust stock downwards (-10)
    deduct_payload = {
        "product_id": product_id,
        "delta_qty": -10,
        "movement_type": "MANUAL_CORRECTION",
        "reason": "Damaged items write-off",
    }
    deduct_res = await client.post("/api/v1/admin/inventory/adjust", json=deduct_payload, headers=admin_headers)
    assert deduct_res.status_code == 200
    assert deduct_res.json()["data"]["available_qty"] == 25

    # 4. Verify movement audit records
    mov_res = await client.get(f"/api/v1/admin/inventory/movements?product_id={product_id}", headers=admin_headers)
    assert mov_res.status_code == 200
    movements = mov_res.json()["data"]
    assert len(movements) >= 3  # Initial + 2 adjustments



@pytest.mark.asyncio
async def test_stock_adjustment_insufficient_stock_rejection(
    client: AsyncClient, admin_headers: dict
):
    prod_res = await client.post(
        "/api/v1/admin/products",
        json={"sku": "SKU-OVERDRAFT", "name": "USB Flash Drive", "price": 15.00, "initial_stock": 5},
        headers=admin_headers,
    )
    product_id = prod_res.json()["data"]["id"]

    # Attempt to deduct 10 when only 5 are available
    res = await client.post(
        "/api/v1/admin/inventory/adjust",
        json={"product_id": product_id, "delta_qty": -10, "movement_type": "MANUAL_CORRECTION"},
        headers=admin_headers,
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INSUFFICIENT_STOCK"



@pytest.mark.asyncio
async def test_low_stock_threshold_detection(client: AsyncClient, admin_headers: dict):
    # Create an item with stock (3) <= reorder_level (10)
    await client.post(
        "/api/v1/admin/products",
        json={"sku": "SKU-LOWSTOCK", "name": "4K HDMI Cable", "price": 12.00, "initial_stock": 3, "reorder_level": 10},
        headers=admin_headers,
    )

    res = await client.get("/api/v1/admin/inventory/low-stock", headers=admin_headers)
    assert res.status_code == 200
    low_stock = res.json()["data"]
    skus = [item["sku"] for item in low_stock]
    assert "SKU-LOWSTOCK" in skus


@pytest.mark.asyncio
async def test_product_soft_delete(client: AsyncClient, admin_headers: dict):
    prod_res = await client.post(
        "/api/v1/admin/products",
        json={"sku": "SKU-SOFT-DEL", "name": "Old Monitor", "price": 99.00, "initial_stock": 10},
        headers=admin_headers,
    )
    product_id = prod_res.json()["data"]["id"]

    del_res = await client.delete(f"/api/v1/admin/products/{product_id}", headers=admin_headers)
    assert del_res.status_code == 200
    assert del_res.json()["data"]["is_active"] is False

    # Check that product still exists with is_active = False
    get_res = await client.get(f"/api/v1/admin/products/{product_id}", headers=admin_headers)
    assert get_res.status_code == 200
    assert get_res.json()["data"]["is_active"] is False


@pytest.mark.asyncio
async def test_operator_rbac_permissions(
    client: AsyncClient, admin_headers: dict, operator_headers: dict
):
    # Operators CAN view products and low stock items
    view_res = await client.get("/api/v1/admin/products", headers=operator_headers)
    assert view_res.status_code == 200

    # Operators CANNOT create products
    create_res = await client.post(
        "/api/v1/admin/products",
        json={"sku": "SKU-OP-FORBIDDEN", "name": "Illegal item", "price": 10.00},
        headers=operator_headers,
    )
    assert create_res.status_code == 403

    # Operators CANNOT adjust stock
    adj_res = await client.post(
        "/api/v1/admin/inventory/adjust",
        json={"product_id": str(uuid.uuid4()), "delta_qty": 10},
        headers=operator_headers,
    )
    assert adj_res.status_code == 403
