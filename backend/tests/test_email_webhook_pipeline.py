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
        extra_claims={"email": "admin_hook@opsmind.io", "app_metadata": {"role": "ADMIN"}},
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def packager_headers():
    pkg_id = str(uuid.uuid4())
    token = create_access_token(
        subject=pkg_id,
        role="PACKAGING",
        extra_claims={"email": "pack_hook@opsmind.io", "app_metadata": {"role": "PACKAGING"}},
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_end_to_end_inbound_email_order_fulfillment(
    client: AsyncClient, admin_headers: dict, packager_headers: dict
):
    # 1. Seed a packaging employee by hitting my tasks
    await client.get("/api/v1/employee/tasks/my", headers=packager_headers)

    # 2. Create Catalog Product with stock
    prod_res = await client.post(
        "/api/v1/admin/products",
        json={
            "sku": "SKU-PRO-MIC",
            "name": "Professional Condenser Microphone",
            "price": 199.99,
            "initial_stock": 25,
            "reorder_level": 5,
        },
        headers=admin_headers,
    )
    assert prod_res.status_code == 201
    prod = prod_res.json()["data"]

    # 3. Simulate Inbound Email Webhook
    msg_id = f"<order_msg_{uuid.uuid4().hex[:10]}@clientcorp.com>"
    webhook_payload = {
        "message_id": msg_id,
        "sender_email": "purchasing@clientcorp.com",
        "sender_name": "Alexander Pierce",
        "subject": "Urgent Purchase Order: Microphones",
        "body_plain": "Hello OpsMind team,\n\nPlease ship 3x SKU-PRO-MIC to our headquarters:\n742 Evergreen Terrace, Springfield, IL 62704.\n\nThank you,\nAlexander Pierce\nPhone: +1-217-555-0199",
    }

    res = await client.post("/api/v1/webhooks/email/inbound", json=webhook_payload)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["review_reasons"] == []
    assert data["status"] == "PROCESSED"
    assert data["order_id"] is not None
    assert data["order_number"] is not None
    assert data["customer_email"] == "purchasing@clientcorp.com"
    assert data["is_order_intent"] is True
    assert data["needs_human_review"] is False
    assert data["outbound_email_id"] is not None

    order_id = data["order_id"]

    # 4. Verify Order was created, confirmed, reserved stock, and moved to PACKAGING
    order_check = (await client.get(f"/api/v1/admin/orders/{order_id}", headers=admin_headers)).json()["data"]
    assert order_check["status"] == "PACKAGING"
    assert len(order_check["items"]) == 1
    assert order_check["items"][0]["quantity"] == 3
    assert "742 Evergreen Terrace" in order_check["shipping_address"]

    # 5. Verify Inventory was reserved atomically (25 total -> 22 available, 3 reserved)
    inv_check = (await client.get(f"/api/v1/admin/products/{prod['id']}", headers=admin_headers)).json()["data"]
    assert inv_check["available_qty"] == 22
    assert inv_check["reserved_qty"] == 3
    assert inv_check["total_qty"] == 25

    # 6. Verify Packaging Task was auto-spawned for the warehouse operator
    tasks_res = (await client.get("/api/v1/employee/tasks/my", headers=packager_headers)).json()["data"]
    assert len(tasks_res) >= 1
    matched_task = next((t for t in tasks_res if t["order_id"] == order_id), None)
    assert matched_task is not None
    assert matched_task["task_type"] == "PACKAGING"
    assert matched_task["status"] == "PENDING"


@pytest.mark.asyncio
async def test_webhook_deduplication_idempotency(client: AsyncClient, admin_headers: dict):
    # Create product
    prod = (
        await client.post(
            "/api/v1/admin/products",
            json={"sku": "SKU-DEDUP-01", "name": "Wireless Mouse", "price": 49.99, "initial_stock": 50},
            headers=admin_headers,
        )
    ).json()["data"]

    msg_id = f"<dedup_test_{uuid.uuid4().hex[:10]}@test.com>"
    payload = {
        "message_id": msg_id,
        "sender_email": "dedup_user@test.com",
        "sender_name": "Dedup Tester",
        "subject": "Order Mouse",
        "body_plain": "Please send 2x SKU-DEDUP-01 to 100 Main Street, Boston MA.",
    }

    # First ingestion -> PROCESSED
    first_res = await client.post("/api/v1/webhooks/email/inbound", json=payload)
    assert first_res.status_code == 200
    first_data = first_res.json()["data"]
    assert first_data["review_reasons"] == []
    assert first_data["status"] == "PROCESSED"

    first_order_id = first_data["order_id"]

    # Second ingestion with identical message_id -> DUPLICATE
    second_res = await client.post("/api/v1/webhooks/email/inbound", json=payload)
    assert second_res.status_code == 200
    second_data = second_res.json()["data"]
    assert second_data["status"] == "DUPLICATE"
    assert second_data["order_id"] == first_order_id

    # Verify inventory was only reserved ONCE (50 - 2 = 48 available)
    inv = (await client.get(f"/api/v1/admin/products/{prod['id']}", headers=admin_headers)).json()["data"]
    assert inv["available_qty"] == 48
    assert inv["reserved_qty"] == 2


@pytest.mark.asyncio
async def test_out_of_stock_inbound_email_handling(client: AsyncClient, admin_headers: dict):
    # Product with only 2 items in stock
    prod = (
        await client.post(
            "/api/v1/admin/products",
            json={"sku": "SKU-LIMITED-01", "name": "Limited Edition Watch", "price": 999.00, "initial_stock": 2},
            headers=admin_headers,
        )
    ).json()["data"]

    # Customer orders 10 units!
    msg_id = f"<stockout_{uuid.uuid4().hex[:10]}@vip.com>"
    payload = {
        "message_id": msg_id,
        "sender_email": "collector@vip.com",
        "sender_name": "Bruce Wayne",
        "subject": "Order 10 watches",
        "body_plain": "Please send 10x SKU-LIMITED-01 to Wayne Manor, Gotham City.",
    }

    res = await client.post("/api/v1/webhooks/email/inbound", json=payload)
    assert res.status_code == 200
    data = res.json()["data"]

    assert data["status"] == "PROCESSED"
    order_id = data["order_id"]

    # Order should be in OUT_OF_STOCK state
    order = (await client.get(f"/api/v1/admin/orders/{order_id}", headers=admin_headers)).json()["data"]
    assert order["status"] == "OUT_OF_STOCK"

    # Stock should NOT have been deducted/reserved
    inv = (await client.get(f"/api/v1/admin/products/{prod['id']}", headers=admin_headers)).json()["data"]
    assert inv["available_qty"] == 2
    assert inv["reserved_qty"] == 0


@pytest.mark.asyncio
async def test_low_confidence_routes_to_needs_review(client: AsyncClient, admin_headers: dict):
    # Email with missing shipping address
    msg_id = f"<no_address_{uuid.uuid4().hex[:10]}@unclear.com>"
    payload = {
        "message_id": msg_id,
        "sender_email": "vague_client@unclear.com",
        "sender_name": "Vague Client",
        "subject": "Want to buy headphones",
        "body_plain": "I want to buy 2x SKU-TEST-001. How much is it?",  # No address given!
    }

    res = await client.post("/api/v1/webhooks/email/inbound", json=payload)
    assert res.status_code == 200
    data = res.json()["data"]

    assert data["status"] == "NEEDS_REVIEW"
    assert data["needs_human_review"] is True
    assert len(data["review_reasons"]) >= 1

    order_id = data["order_id"]
    order = (await client.get(f"/api/v1/admin/orders/{order_id}", headers=admin_headers)).json()["data"]
    assert order["status"] == "NEEDS_REVIEW"


@pytest.mark.asyncio
async def test_multilingual_spanish_email_flow(
    client: AsyncClient, admin_headers: dict, packager_headers: dict
):
    await client.get("/api/v1/employee/tasks/my", headers=packager_headers)

    prod = (
        await client.post(
            "/api/v1/admin/products",
            json={"sku": "SKU-ES-TECLADO", "name": "Teclado Mecanico Espanol", "price": 75.00, "initial_stock": 10},
            headers=admin_headers,
        )
    ).json()["data"]

    msg_id = f"<pedido_es_{uuid.uuid4().hex[:10]}@madrid.es>"
    payload = {
        "message_id": msg_id,
        "sender_email": "carlos.gomez@madrid.es",
        "sender_name": "Carlos Gomez",
        "subject": "Pedido de teclados para oficina",
        "body_plain": "Hola, por favor enviar 2x SKU-ES-TECLADO a nuestra oficina en:\nGran Via 28, 4A, 28013 Madrid, Espana.\n\nMuchas gracias,\nCarlos Gomez",
    }

    res = await client.post("/api/v1/webhooks/email/inbound", json=payload)
    assert res.status_code == 200
    data = res.json()["data"]

    assert data["status"] == "PROCESSED"
    assert data["detected_language"] == "es"

    # Verify Outbound email is in Spanish
    outbound_id = data["outbound_email_id"]
    email_detail = (await client.get(f"/api/v1/admin/emails/{outbound_id}", headers=admin_headers)).json()["data"]
    assert email_detail["direction"] == "OUTBOUND"
    assert email_detail["detected_language"] == "es"
    assert "Confirmación de Pedido" in email_detail["subject"]
    assert "Carlos Gomez" in email_detail["body_plain"]


@pytest.mark.asyncio
async def test_admin_email_audit_logs_and_rbac(
    client: AsyncClient, admin_headers: dict, packager_headers: dict
):
    # Ingest a sample email first
    msg_id = f"<audit_test_{uuid.uuid4().hex[:10]}@domain.com>"
    inbound_res = await client.post(
        "/api/v1/webhooks/email/inbound",
        json={
            "message_id": msg_id,
            "sender_email": "audit_sender@domain.com",
            "subject": "Inquiry",
            "body_plain": "Hello, is this product available?",
        },
    )
    assert inbound_res.status_code == 200

    # 1. Non-admin forbidden from email audit log
    forbidden_res = await client.get("/api/v1/admin/emails", headers=packager_headers)
    assert forbidden_res.status_code == 403

    # 2. Admin retrieves email logs
    logs_res = await client.get("/api/v1/admin/emails", headers=admin_headers)
    assert logs_res.status_code == 200
    logs = logs_res.json()["data"]
    meta = logs_res.json()["meta"]
    assert isinstance(logs, list)
    assert meta["total"] >= 1

    # 3. Admin retrieves specific email detail
    sample_email_id = logs[0]["id"]
    detail_res = await client.get(f"/api/v1/admin/emails/{sample_email_id}", headers=admin_headers)
    assert detail_res.status_code == 200
    assert detail_res.json()["data"]["id"] == sample_email_id
