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
        extra_claims={"email": "admin_order@opsmind.io", "app_metadata": {"role": "ADMIN"}},
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def packaging_headers():
    op_id = str(uuid.uuid4())
    token = create_access_token(
        subject=op_id,
        role="PACKAGING",
        extra_claims={"email": "pack_order@opsmind.io", "app_metadata": {"role": "PACKAGING"}},
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_order_creation_and_lifecycle_transitions(
    client: AsyncClient, admin_headers: dict
):
    # 1. Create a product with 10 units in stock
    prod_res = await client.post(
        "/api/v1/admin/products",
        json={"sku": "SKU-ORDER-001", "name": "Smart Watch", "price": 250.00, "initial_stock": 10},
        headers=admin_headers,
    )
    assert prod_res.status_code == 201
    product_id = prod_res.json()["data"]["id"]

    # 2. Place an order for 2 units
    order_payload = {
        "customer_email": "customer1@example.com",
        "customer_name": "Alice Customer",
        "shipping_address": "123 Main St, New York, NY",
        "source": "EMAIL",
        "items": [{"product_id": product_id, "quantity": 2}],
    }
    order_res = await client.post("/api/v1/admin/orders", json=order_payload, headers=admin_headers)
    assert order_res.status_code == 201
    order_data = order_res.json()["data"]
    order_id = order_data["id"]
    assert order_data["status"] == "RECEIVED"
    assert Decimal(str(order_data["total_amount"])) == Decimal("500.00")

    # 3. Transition RECEIVED -> PROCESSING
    p_res = await client.patch(
        f"/api/v1/admin/orders/{order_id}/status",
        json={"new_status": "PROCESSING", "reason": "AI validation complete"},
        headers=admin_headers,
    )
    assert p_res.status_code == 200
    assert p_res.json()["data"]["status"] == "PROCESSING"

    # 4. Transition PROCESSING -> CONFIRMED (Triggers Stock Reservation)
    conf_res = await client.patch(
        f"/api/v1/admin/orders/{order_id}/status",
        json={"new_status": "CONFIRMED", "reason": "Order approved for fulfillment"},
        headers=admin_headers,
    )
    assert conf_res.status_code == 200
    assert conf_res.json()["data"]["status"] == "CONFIRMED"

    # Verify stock reservation: available should now be 8 (10 - 2), reserved 2
    prod_check = await client.get(f"/api/v1/admin/products/{product_id}", headers=admin_headers)
    pdata = prod_check.json()["data"]
    assert pdata["available_qty"] == 8
    assert pdata["reserved_qty"] == 2

    # 5. Transition CONFIRMED -> PACKAGING -> PACKED -> OUT_FOR_DELIVERY -> DELIVERED
    for next_status in ["PACKAGING", "PACKED", "OUT_FOR_DELIVERY", "DELIVERED"]:
        step_res = await client.patch(
            f"/api/v1/admin/orders/{order_id}/status",
            json={"new_status": next_status},
            headers=admin_headers,
        )
        assert step_res.status_code == 200
        assert step_res.json()["data"]["status"] == next_status

    # Verify final stock deduction: available remains 8, reserved returns to 0
    prod_final = await client.get(f"/api/v1/admin/products/{product_id}", headers=admin_headers)
    pfdata = prod_final.json()["data"]
    assert pfdata["available_qty"] == 8
    assert pfdata["reserved_qty"] == 0
    assert pfdata["total_qty"] == 8

    # 6. Check order event audit trail
    events_res = await client.get(f"/api/v1/admin/orders/{order_id}/events", headers=admin_headers)
    assert events_res.status_code == 200
    events = events_res.json()["data"]
    assert len(events) >= 6


@pytest.mark.asyncio
async def test_order_cancellation_restores_reserved_stock(
    client: AsyncClient, admin_headers: dict
):
    # 1. Create product with stock = 5
    prod_res = await client.post(
        "/api/v1/admin/products",
        json={"sku": "SKU-CANCEL-001", "name": "Wireless Mouse", "price": 40.00, "initial_stock": 5},
        headers=admin_headers,
    )
    product_id = prod_res.json()["data"]["id"]

    # 2. Place order for 3 items
    order_res = await client.post(
        "/api/v1/admin/orders",
        json={
            "customer_email": "cancel_cust@example.com",
            "shipping_address": "456 Market St, SF, CA",
            "items": [{"product_id": product_id, "quantity": 3}],
        },
        headers=admin_headers,
    )
    order_id = order_res.json()["data"]["id"]

    # 3. Move to CONFIRMED (reserving 3 items)
    await client.patch(
        f"/api/v1/admin/orders/{order_id}/status",
        json={"new_status": "PROCESSING"},
        headers=admin_headers,
    )
    await client.patch(
        f"/api/v1/admin/orders/{order_id}/status",
        json={"new_status": "CONFIRMED"},
        headers=admin_headers,
    )

    # Verify stock reserved: available = 2, reserved = 3
    p_mid = (await client.get(f"/api/v1/admin/products/{product_id}", headers=admin_headers)).json()["data"]
    assert p_mid["available_qty"] == 2
    assert p_mid["reserved_qty"] == 3

    # 4. Cancel the order
    cancel_res = await client.patch(
        f"/api/v1/admin/orders/{order_id}/status",
        json={"new_status": "CANCELLED", "reason": "Customer requested cancellation"},
        headers=admin_headers,
    )
    assert cancel_res.status_code == 200
    assert cancel_res.json()["data"]["status"] == "CANCELLED"

    # Verify stock restored: available = 5, reserved = 0
    p_post = (await client.get(f"/api/v1/admin/products/{product_id}", headers=admin_headers)).json()["data"]
    assert p_post["available_qty"] == 5
    assert p_post["reserved_qty"] == 0


@pytest.mark.asyncio
async def test_order_delivered_idempotency(client: AsyncClient, admin_headers: dict):
    # Create product with stock = 10
    prod_res = await client.post(
        "/api/v1/admin/products",
        json={"sku": "SKU-IDEMPOTENT-001", "name": "Tablet Stand", "price": 25.00, "initial_stock": 10},
        headers=admin_headers,
    )
    product_id = prod_res.json()["data"]["id"]

    # Place and fulfill order
    order_res = await client.post(
        "/api/v1/admin/orders",
        json={
            "customer_email": "idemp_cust@example.com",
            "shipping_address": "789 Pine St, Seattle, WA",
            "items": [{"product_id": product_id, "quantity": 2}],
        },
        headers=admin_headers,
    )
    order_id = order_res.json()["data"]["id"]

    for s in ["PROCESSING", "CONFIRMED", "PACKAGING", "PACKED", "OUT_FOR_DELIVERY", "DELIVERED"]:
        await client.patch(f"/api/v1/admin/orders/{order_id}/status", json={"new_status": s}, headers=admin_headers)

    # Verify stock after delivery
    p1 = (await client.get(f"/api/v1/admin/products/{product_id}", headers=admin_headers)).json()["data"]
    assert p1["available_qty"] == 8
    assert p1["reserved_qty"] == 0

    # Repeat DELIVERED status update (webhook retry)
    retry_res = await client.patch(
        f"/api/v1/admin/orders/{order_id}/status",
        json={"new_status": "DELIVERED", "reason": "Repeated webhook dispatch"},
        headers=admin_headers,
    )
    assert retry_res.status_code == 200
    assert retry_res.json()["data"]["status"] == "DELIVERED"

    # Verify stock was NOT double deducted!
    p2 = (await client.get(f"/api/v1/admin/products/{product_id}", headers=admin_headers)).json()["data"]
    assert p2["available_qty"] == 8
    assert p2["reserved_qty"] == 0


@pytest.mark.asyncio
async def test_insufficient_stock_rejects_confirmation(
    client: AsyncClient, admin_headers: dict
):
    # Create product with only 1 in stock
    prod_res = await client.post(
        "/api/v1/admin/products",
        json={"sku": "SKU-SHORTAGE-001", "name": "Limited Edition Poster", "price": 50.00, "initial_stock": 1},
        headers=admin_headers,
    )
    product_id = prod_res.json()["data"]["id"]

    # Create order requesting 5 units
    order_res = await client.post(
        "/api/v1/admin/orders",
        json={
            "customer_email": "shortage_cust@example.com",
            "shipping_address": "999 Oak St",
            "items": [{"product_id": product_id, "quantity": 5}],
        },
        headers=admin_headers,
    )
    order_id = order_res.json()["data"]["id"]

    await client.patch(
        f"/api/v1/admin/orders/{order_id}/status",
        json={"new_status": "PROCESSING"},
        headers=admin_headers,
    )

    # Attempt to confirm order with inadequate inventory
    res = await client.patch(
        f"/api/v1/admin/orders/{order_id}/status",
        json={"new_status": "CONFIRMED"},
        headers=admin_headers,
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INSUFFICIENT_STOCK"


    # Order should now be marked OUT_OF_STOCK
    order_check = (await client.get(f"/api/v1/admin/orders/{order_id}", headers=admin_headers)).json()["data"]
    assert order_check["status"] == "OUT_OF_STOCK"


@pytest.mark.asyncio
async def test_illegal_state_transition_rejected(
    client: AsyncClient, admin_headers: dict
):
    # Create an order in RECEIVED state
    prod_res = await client.post(
        "/api/v1/admin/products",
        json={"sku": "SKU-TRANS-001", "name": "Gaming Chair", "price": 300.00, "initial_stock": 10},
        headers=admin_headers,
    )
    product_id = prod_res.json()["data"]["id"]

    order_res = await client.post(
        "/api/v1/admin/orders",
        json={
            "customer_email": "illegal_trans@example.com",
            "shipping_address": "123 State St",
            "items": [{"product_id": product_id, "quantity": 1}],
        },
        headers=admin_headers,
    )
    order_id = order_res.json()["data"]["id"]

    # Attempt illegal leap: RECEIVED -> DELIVERED
    res = await client.patch(
        f"/api/v1/admin/orders/{order_id}/status",
        json={"new_status": "DELIVERED"},
        headers=admin_headers,
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "ILLEGAL_STATE_TRANSITION"
