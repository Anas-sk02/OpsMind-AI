import uuid
from decimal import Decimal
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.user import User
from app.models.customer import Customer
from app.models.product import Product
from app.models.inventory import Inventory
from app.models.inventory_movement import InventoryMovement
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.task import Task
from app.models.email_message import EmailMessage
from app.models.audit_log import OrderEvent, AuditLog


import pytest_asyncio


@pytest_asyncio.fixture
async def db_session():
    """
    Creates an isolated in-memory SQLite async database engine and tables for testing models.
    """
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_maker() as session:
        yield session

    await test_engine.dispose()


@pytest.mark.asyncio
async def test_user_model_creation(db_session: AsyncSession):
    user = User(
        email="operator1@opsmind.io",
        hashed_password="secure_argon2_hash",
        full_name="Packaging Lead",
        role="PACKAGING",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    assert user.id is not None
    assert user.role == "PACKAGING"
    assert user.is_active is True
    assert user.created_at is not None


@pytest.mark.asyncio
async def test_customer_model_creation(db_session: AsyncSession):
    customer = Customer(
        email="customer@example.com",
        name="Alice Smith",
        phone="+1234567890",
        address="123 Industrial Way, Warehouse 4",
        preferred_language="es",
    )
    db_session.add(customer)
    await db_session.commit()
    await db_session.refresh(customer)

    assert customer.id is not None
    assert customer.preferred_language == "es"
    assert customer.is_active is True


@pytest.mark.asyncio
async def test_product_and_inventory_relationship(db_session: AsyncSession):
    product = Product(
        sku="SKU-WIDGET-01",
        name="Industrial Steel Widget",
        description="High durability steel widget",
        unit_price=Decimal("49.99"),
    )
    db_session.add(product)
    await db_session.flush()

    inventory = Inventory(
        product_id=product.id,
        available_qty=100,
        reserved_qty=20,
        reorder_level=15,
    )
    db_session.add(inventory)
    await db_session.commit()

    # Query back with relationship
    res = await db_session.execute(
        select(Product).where(Product.sku == "SKU-WIDGET-01")
    )
    queried_product = res.scalar_one()

    assert queried_product.inventory is not None
    assert queried_product.inventory.available_qty == 100
    assert queried_product.inventory.total_physical_qty == 120
    assert queried_product.inventory.is_low_stock is False


@pytest.mark.asyncio
async def test_order_and_order_items_lifecycle(db_session: AsyncSession):
    # Setup Customer & Product
    customer = Customer(email="bob@example.com", name="Bob Builder")
    product = Product(sku="SKU-BOLT-99", name="Hex Bolt Pack", unit_price=Decimal("15.50"))
    db_session.add_all([customer, product])
    await db_session.flush()

    # Create Order
    order = Order(
        order_number="ORD-20260928-0001",
        customer_id=customer.id,
        status="RECEIVED",
        delivery_address="456 Construct Ave",
        total_amount=Decimal("31.00"),
    )
    db_session.add(order)
    await db_session.flush()

    # Add Order Item
    item = OrderItem(
        order_id=order.id,
        product_id=product.id,
        quantity=2,
        unit_price=Decimal("15.50"),
    )
    item.calculate_total()
    db_session.add(item)
    await db_session.commit()

    assert item.total_price == Decimal("31.00")

    # Query Order with items
    res = await db_session.execute(
        select(Order).where(Order.order_number == "ORD-20260928-0001")
    )
    queried_order = res.scalar_one()
    assert len(queried_order.items) == 1
    assert queried_order.items[0].quantity == 2


@pytest.mark.asyncio
async def test_task_model_workflow(db_session: AsyncSession):
    customer = Customer(email="c1@test.com", name="Test Customer")
    db_session.add(customer)
    await db_session.flush()

    order = Order(
        order_number="ORD-TASK-001",
        customer_id=customer.id,
        delivery_address="789 Park Rd",
    )
    user = User(
        email="packager@opsmind.io",
        hashed_password="hash",
        full_name="Sam Pack",
        role="PACKAGING",
    )
    db_session.add_all([order, user])
    await db_session.flush()

    task = Task(
        order_id=order.id,
        assigned_employee_id=user.id,
        task_type="PACKAGING",
        status="PENDING",
    )
    db_session.add(task)
    await db_session.commit()

    assert task.status == "PENDING"
    task.mark_completed()
    await db_session.commit()
    assert task.status == "COMPLETED"
    assert task.completed_at is not None


@pytest.mark.asyncio
async def test_inventory_movement_ledger(db_session: AsyncSession):
    product = Product(sku="SKU-LEDGER-01", name="Ledger Item", unit_price=Decimal("10.00"))
    db_session.add(product)
    await db_session.flush()

    movement = InventoryMovement(
        product_id=product.id,
        delta_qty=50,
        movement_type="PURCHASE_RECEIPT",
        reason="Initial batch receipt from vendor",
    )
    db_session.add(movement)
    await db_session.commit()

    assert movement.id is not None
    assert movement.delta_qty == 50
    assert movement.movement_type == "PURCHASE_RECEIPT"


@pytest.mark.asyncio
async def test_email_message_and_ai_payload(db_session: AsyncSession):
    email = EmailMessage(
        message_id="<msg-12345@mail.example.com>",
        direction="INBOUND",
        sender_email="buyer@company.com",
        recipient_email="orders@opsmind.io",
        subject="Urgent Order for 10 units",
        body_plain="Please send 10 units to Main St.",
        detected_language="en",
        ai_extraction_payload={
            "sku": "SKU-WIDGET-01",
            "quantity": 10,
            "confidence": 0.98,
        },
    )
    db_session.add(email)
    await db_session.commit()
    await db_session.refresh(email)

    assert email.ai_extraction_payload["confidence"] == 0.98
    assert email.ai_extraction_payload["sku"] == "SKU-WIDGET-01"


@pytest.mark.asyncio
async def test_order_event_and_audit_log(db_session: AsyncSession):
    customer = Customer(email="audit_user@example.com", name="Audit User")
    user = User(email="admin@test.com", hashed_password="pw", full_name="Admin", role="ADMIN")
    db_session.add_all([customer, user])
    await db_session.flush()

    order = Order(
        order_number="ORD-AUDIT-001",
        customer_id=customer.id,
        delivery_address="Audit Street",
    )
    db_session.add(order)
    await db_session.flush()

    event = OrderEvent(
        order_id=order.id,
        from_status="RECEIVED",
        to_status="CONFIRMED",
        event_type="STATUS_CHANGE",
        description="Order confirmed and stock reserved",
        actor_id=user.id,
    )

    audit = AuditLog(
        actor_id=user.id,
        action="UPDATE",
        entity_name="orders",
        entity_id=order.id,
        change_diff={"status": {"old": "RECEIVED", "new": "CONFIRMED"}},
        ip_address="192.168.1.1",
    )

    db_session.add_all([event, audit])
    await db_session.commit()

    assert event.id is not None
    assert audit.change_diff["status"]["new"] == "CONFIRMED"
