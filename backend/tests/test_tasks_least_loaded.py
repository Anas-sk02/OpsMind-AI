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
        extra_claims={"email": "admin_tasks@opsmind.io", "app_metadata": {"role": "ADMIN"}},
    )
    return {"Authorization": f"Bearer {token}", "user_id": admin_id}


@pytest.fixture
def packager_1():
    user_id = str(uuid.uuid4())
    token = create_access_token(
        subject=user_id,
        role="PACKAGING",
        extra_claims={
            "email": "packager1@opsmind.io",
            "app_metadata": {"role": "PACKAGING", "provider": "email"},
            "user_metadata": {"full_name": "Packager Alice"},
        },
    )
    return {"headers": {"Authorization": f"Bearer {token}"}, "id": user_id, "name": "Packager Alice"}


@pytest.fixture
def packager_2():
    user_id = str(uuid.uuid4())
    token = create_access_token(
        subject=user_id,
        role="PACKAGING",
        extra_claims={
            "email": "packager2@opsmind.io",
            "app_metadata": {"role": "PACKAGING", "provider": "email"},
            "user_metadata": {"full_name": "Packager Bob"},
        },
    )
    return {"headers": {"Authorization": f"Bearer {token}"}, "id": user_id, "name": "Packager Bob"}


@pytest.fixture
def delivery_driver():
    user_id = str(uuid.uuid4())
    token = create_access_token(
        subject=user_id,
        role="DELIVERY",
        extra_claims={
            "email": "driver1@opsmind.io",
            "app_metadata": {"role": "DELIVERY", "provider": "email"},
            "user_metadata": {"full_name": "Driver Dave"},
        },
    )
    return {"headers": {"Authorization": f"Bearer {token}"}, "id": user_id, "name": "Driver Dave"}


@pytest.mark.asyncio
async def test_least_loaded_auto_assignment_and_workload_balancing(
    client: AsyncClient, admin_headers: dict, packager_1: dict, packager_2: dict
):
    # 1. Warm up employees so their profiles exist in the DB
    await client.get("/api/v1/employee/tasks/my", headers=packager_1["headers"])
    await client.get("/api/v1/employee/tasks/my", headers=packager_2["headers"])

    # 2. Create product with stock
    prod_res = await client.post(
        "/api/v1/admin/products",
        json={"sku": "SKU-LOAD-001", "name": "Espresso Machine", "price": 499.00, "initial_stock": 20},
        headers=admin_headers,
    )
    product_id = prod_res.json()["data"]["id"]

    # 3. Create Order 1 and move to PACKAGING
    o1 = await client.post(
        "/api/v1/admin/orders",
        json={
            "customer_email": "cust1@opsmind.io",
            "shipping_address": "100 Broadway, NY",
            "items": [{"product_id": product_id, "quantity": 1}],
        },
        headers=admin_headers,
    )
    o1_id = o1.json()["data"]["id"]
    await client.patch(f"/api/v1/admin/orders/{o1_id}/status", json={"new_status": "PROCESSING"}, headers=admin_headers)
    await client.patch(f"/api/v1/admin/orders/{o1_id}/status", json={"new_status": "CONFIRMED"}, headers=admin_headers)
    await client.patch(f"/api/v1/admin/orders/{o1_id}/status", json={"new_status": "PACKAGING"}, headers=admin_headers)

    # 4. Create Order 2 and move to PACKAGING
    o2 = await client.post(
        "/api/v1/admin/orders",
        json={
            "customer_email": "cust2@opsmind.io",
            "shipping_address": "200 Broadway, NY",
            "items": [{"product_id": product_id, "quantity": 1}],
        },
        headers=admin_headers,
    )
    o2_id = o2.json()["data"]["id"]
    await client.patch(f"/api/v1/admin/orders/{o2_id}/status", json={"new_status": "PROCESSING"}, headers=admin_headers)
    await client.patch(f"/api/v1/admin/orders/{o2_id}/status", json={"new_status": "CONFIRMED"}, headers=admin_headers)
    await client.patch(f"/api/v1/admin/orders/{o2_id}/status", json={"new_status": "PACKAGING"}, headers=admin_headers)

    # Check tasks: Both packager 1 and packager 2 should each receive 1 task!
    p1_tasks = (await client.get("/api/v1/employee/tasks/my", headers=packager_1["headers"])).json()["data"]
    p2_tasks = (await client.get("/api/v1/employee/tasks/my", headers=packager_2["headers"])).json()["data"]

    assert len(p1_tasks) == 1
    assert len(p2_tasks) == 1
    assert p1_tasks[0]["assigned_employee_id"] != p2_tasks[0]["assigned_employee_id"]


@pytest.mark.asyncio
async def test_end_to_end_packaging_to_delivery_progression(
    client: AsyncClient, admin_headers: dict, packager_1: dict, delivery_driver: dict
):
    # Warm up users
    await client.get("/api/v1/employee/tasks/my", headers=packager_1["headers"])
    await client.get("/api/v1/employee/tasks/my", headers=delivery_driver["headers"])

    # 1. Create Product & Order
    prod = (
        await client.post(
            "/api/v1/admin/products",
            json={"sku": "SKU-E2E-TASK", "name": "Studio Microphone", "price": 150.00, "initial_stock": 10},
            headers=admin_headers,
        )
    ).json()["data"]

    order = (
        await client.post(
            "/api/v1/admin/orders",
            json={
                "customer_email": "e2e_cust@opsmind.io",
                "shipping_address": "55 Wall Street, NY",
                "items": [{"product_id": prod["id"], "quantity": 2}],
            },
            headers=admin_headers,
        )
    ).json()["data"]

    order_id = order["id"]

    # 2. Advance to PACKAGING
    await client.patch(f"/api/v1/admin/orders/{order_id}/status", json={"new_status": "PROCESSING"}, headers=admin_headers)
    await client.patch(f"/api/v1/admin/orders/{order_id}/status", json={"new_status": "CONFIRMED"}, headers=admin_headers)
    await client.patch(f"/api/v1/admin/orders/{order_id}/status", json={"new_status": "PACKAGING"}, headers=admin_headers)

    # 3. Packager retrieves task
    my_tasks = (await client.get("/api/v1/employee/tasks/my", headers=packager_1["headers"])).json()["data"]
    assert len(my_tasks) >= 1
    pkg_task = my_tasks[0]
    task_id = pkg_task["id"]

    # 4. Packager starts and completes packaging
    await client.patch(
        f"/api/v1/employee/tasks/{task_id}/status",
        json={"new_status": "IN_PROGRESS"},
        headers=packager_1["headers"],
    )
    comp_res = await client.patch(
        f"/api/v1/employee/tasks/{task_id}/status",
        json={"new_status": "COMPLETED"},
        headers=packager_1["headers"],
    )
    assert comp_res.status_code == 200
    assert comp_res.json()["data"]["status"] == "COMPLETED"

    # Verify Order automatically transitioned to PACKED!
    order_check = (await client.get(f"/api/v1/admin/orders/{order_id}", headers=admin_headers)).json()["data"]
    assert order_check["status"] == "PACKED"

    # Verify Delivery Task was automatically spawned and assigned to Driver!
    driver_tasks = (await client.get("/api/v1/employee/tasks/my", headers=delivery_driver["headers"])).json()["data"]
    assert len(driver_tasks) >= 1
    del_task = driver_tasks[0]
    assert del_task["task_type"] == "DELIVERY"
    assert del_task["status"] == "PENDING"

    # 5. Driver delivers
    del_task_id = del_task["id"]
    await client.patch(
        f"/api/v1/employee/tasks/{del_task_id}/status",
        json={"new_status": "IN_PROGRESS"},
        headers=delivery_driver["headers"],
    )
    del_comp = await client.patch(
        f"/api/v1/employee/tasks/{del_task_id}/status",
        json={"new_status": "COMPLETED"},
        headers=delivery_driver["headers"],
    )
    assert del_comp.status_code == 200

    # Verify Order automatically transitioned to DELIVERED and stock was deducted!
    final_order = (await client.get(f"/api/v1/admin/orders/{order_id}", headers=admin_headers)).json()["data"]
    assert final_order["status"] == "DELIVERED"

    final_prod = (await client.get(f"/api/v1/admin/products/{prod['id']}", headers=admin_headers)).json()["data"]
    assert final_prod["available_qty"] == 8
    assert final_prod["reserved_qty"] == 0


@pytest.mark.asyncio
async def test_task_exception_reporting(
    client: AsyncClient, admin_headers: dict, packager_1: dict
):
    await client.get("/api/v1/employee/tasks/my", headers=packager_1["headers"])

    prod = (
        await client.post(
            "/api/v1/admin/products",
            json={"sku": "SKU-EXC-001", "name": "Ceramic Mug", "price": 15.00, "initial_stock": 5},
            headers=admin_headers,
        )
    ).json()["data"]

    order = (
        await client.post(
            "/api/v1/admin/orders",
            json={
                "customer_email": "exc_cust@opsmind.io",
                "shipping_address": "123 Broken Item Rd",
                "items": [{"product_id": prod["id"], "quantity": 1}],
            },
            headers=admin_headers,
        )
    ).json()["data"]

    await client.patch(f"/api/v1/admin/orders/{order['id']}/status", json={"new_status": "PROCESSING"}, headers=admin_headers)
    await client.patch(f"/api/v1/admin/orders/{order['id']}/status", json={"new_status": "CONFIRMED"}, headers=admin_headers)
    await client.patch(f"/api/v1/admin/orders/{order['id']}/status", json={"new_status": "PACKAGING"}, headers=admin_headers)

    my_tasks = (await client.get("/api/v1/employee/tasks/my", headers=packager_1["headers"])).json()["data"]
    task_id = my_tasks[0]["id"]

    # Report exception
    exc_res = await client.patch(
        f"/api/v1/employee/tasks/{task_id}/status",
        json={"new_status": "EXCEPTION", "exception_notes": "Item cracked during packaging box assembly"},
        headers=packager_1["headers"],
    )
    assert exc_res.status_code == 200
    assert exc_res.json()["data"]["status"] == "EXCEPTION"
    assert exc_res.json()["data"]["exception_notes"] == "Item cracked during packaging box assembly"


@pytest.mark.asyncio
async def test_admin_task_reassignment_and_metrics(
    client: AsyncClient, admin_headers: dict, packager_1: dict, packager_2: dict
):
    await client.get("/api/v1/employee/tasks/my", headers=packager_1["headers"])
    await client.get("/api/v1/employee/tasks/my", headers=packager_2["headers"])

    prod = (
        await client.post(
            "/api/v1/admin/products",
            json={"sku": "SKU-REASSIGN", "name": "Drone Controller", "price": 199.00, "initial_stock": 5},
            headers=admin_headers,
        )
    ).json()["data"]

    order = (
        await client.post(
            "/api/v1/admin/orders",
            json={
                "customer_email": "reassign_cust@opsmind.io",
                "shipping_address": "888 Mission St, SF",
                "items": [{"product_id": prod["id"], "quantity": 1}],
            },
            headers=admin_headers,
        )
    ).json()["data"]

    await client.patch(f"/api/v1/admin/orders/{order['id']}/status", json={"new_status": "PROCESSING"}, headers=admin_headers)
    await client.patch(f"/api/v1/admin/orders/{order['id']}/status", json={"new_status": "CONFIRMED"}, headers=admin_headers)
    await client.patch(f"/api/v1/admin/orders/{order['id']}/status", json={"new_status": "PACKAGING"}, headers=admin_headers)

    all_tasks = (await client.get("/api/v1/admin/tasks", headers=admin_headers)).json()["data"]
    task_id = all_tasks[0]["id"]

    # Reassign to packager 2
    reassign_res = await client.post(
        f"/api/v1/admin/tasks/{task_id}/reassign",
        json={"assigned_employee_id": packager_2["id"]},
        headers=admin_headers,
    )
    assert reassign_res.status_code == 200
    assert reassign_res.json()["data"]["assigned_employee_id"] == packager_2["id"]

    # Check workload metrics
    metrics_res = await client.get("/api/v1/admin/tasks/workload-metrics", headers=admin_headers)
    assert metrics_res.status_code == 200
    metrics = metrics_res.json()["data"]
    assert len(metrics) >= 2
