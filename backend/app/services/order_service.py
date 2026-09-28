import uuid
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Tuple, Dict, Any, Set
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    NotFoundException,
    ConflictException,
    InsufficientStockException,
    StateTransitionException,
    ValidationException,
)
from app.models.customer import Customer
from app.models.product import Product
from app.models.inventory import Inventory
from app.models.inventory_movement import InventoryMovement
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.audit_log import OrderEvent, AuditLog
from app.schemas.order import (
    CreateOrderRequest,
    UpdateOrderStatusRequest,
    OrderResponse,
    OrderItemResponse,
    OrderEventResponse,
)

logger = logging.getLogger("opsmind.order_service")

# Allowed state machine transition graph
ALLOWED_TRANSITIONS: Dict[str, Set[str]] = {
    "RECEIVED": {"PROCESSING", "CANCELLED"},
    "PROCESSING": {"CONFIRMED", "NEEDS_REVIEW", "OUT_OF_STOCK", "CANCELLED"},
    "NEEDS_REVIEW": {"PROCESSING", "CANCELLED"},
    "OUT_OF_STOCK": {"PROCESSING", "CANCELLED"},
    "CONFIRMED": {"PACKAGING", "CANCELLED"},
    "PACKAGING": {"PACKED", "CANCELLED"},
    "PACKED": {"OUT_FOR_DELIVERY", "CANCELLED"},
    "OUT_FOR_DELIVERY": {"DELIVERED", "CANCELLED"},
    "DELIVERED": set(),  # Terminal state
    "CANCELLED": set(),  # Terminal state
}

# States where inventory is held in reserved_qty
RESERVED_STOCK_STATES = {"CONFIRMED", "PACKAGING", "PACKED", "OUT_FOR_DELIVERY"}


class OrderService:
    """
    Core state machine service managing the lifecycle of customer orders,
    atomic inventory reservations, cancellation restores, and idempotent delivery deductions.
    """

    @staticmethod
    def generate_order_number() -> str:
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        unique_suffix = uuid.uuid4().hex[:6].upper()
        return f"ORD-{date_str}-{unique_suffix}"

    @staticmethod
    async def get_or_create_customer(
        db: AsyncSession, email: str, name: Optional[str] = None, address: Optional[str] = None
    ) -> Customer:
        normalized_email = email.lower().strip()
        stmt = select(Customer).where(func.lower(Customer.email) == normalized_email)
        res = await db.execute(stmt)
        customer = res.scalar_one_or_none()

        if not customer:
            customer = Customer(
                email=normalized_email,
                name=name.strip() if name else normalized_email.split("@")[0],
                address=address.strip() if address else None,
                is_active=True,
            )
            db.add(customer)
            await db.flush()
            logger.info(f"Auto-created Customer entity '{customer.email}' (ID: {customer.id})")
        elif address and not customer.address:
            customer.address = address.strip()
            await db.flush()


        return customer

    @staticmethod
    async def get_order_by_id(db: AsyncSession, order_id: uuid.UUID) -> Optional[Order]:
        stmt = (
            select(Order)
            .options(
                selectinload(Order.customer),
                selectinload(Order.items).selectinload(OrderItem.product),
                selectinload(Order.order_events),
            )
            .where(Order.id == order_id)
        )
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def get_order_by_number(db: AsyncSession, order_number: str) -> Optional[Order]:
        stmt = (
            select(Order)
            .options(
                selectinload(Order.customer),
                selectinload(Order.items).selectinload(OrderItem.product),
                selectinload(Order.order_events),
            )
            .where(Order.order_number == order_number.strip().upper())
        )
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def create_order(
        db: AsyncSession, data: CreateOrderRequest, actor_id: Optional[uuid.UUID] = None
    ) -> OrderResponse:
        """
        Creates a new order in RECEIVED state with resolved products and total amount.
        """
        customer = await OrderService.get_or_create_customer(
            db, email=data.customer_email, name=data.customer_name, address=data.shipping_address
        )

        order_number = OrderService.generate_order_number()
        new_order = Order(
            order_number=order_number,
            customer_id=customer.id,
            status="RECEIVED",
            total_amount=Decimal("0.00"),
            delivery_address=data.shipping_address.strip(),
            source_email_id=data.source,
        )

        db.add(new_order)
        await db.flush()

        total_amount = Decimal("0.00")
        items_responses: List[OrderItemResponse] = []

        for item_in in data.items:
            product_stmt = select(Product).where(Product.id == item_in.product_id)
            prod_res = await db.execute(product_stmt)
            product = prod_res.scalar_one_or_none()

            if not product:
                raise NotFoundException(f"Product with ID '{item_in.product_id}' not found")
            if not product.is_active:
                raise ValidationException(f"Product '{product.sku}' is deactivated and cannot be ordered")

            unit_price = item_in.unit_price if item_in.unit_price is not None else product.price
            line_total = unit_price * item_in.quantity
            total_amount += line_total

            order_item = OrderItem(
                order_id=new_order.id,
                product_id=product.id,
                quantity=item_in.quantity,
                unit_price=unit_price,
                total_price=line_total,
            )
            db.add(order_item)
            await db.flush()

            items_responses.append(
                OrderItemResponse(
                    id=order_item.id,
                    order_id=new_order.id,
                    product_id=product.id,
                    quantity=order_item.quantity,
                    unit_price=order_item.unit_price,
                    total_price=order_item.total_price,
                    product_sku=product.sku,
                    product_name=product.name,
                )
            )

        new_order.total_amount = total_amount

        # Log initial event
        event = OrderEvent(
            order_id=new_order.id,
            from_status=None,
            to_status="RECEIVED",
            event_type="STATUS_CHANGE",
            description=f"Order created via {data.source}",
            actor_id=actor_id,
            event_metadata=data.metadata or {},
        )
        db.add(event)

        audit = AuditLog(
            actor_id=actor_id,
            action="CREATE",
            entity_name="orders",
            entity_id=new_order.id,
            change_diff={"order_number": order_number, "total_amount": str(total_amount)},
        )
        db.add(audit)

        await db.commit()
        await db.refresh(new_order)
        logger.info(f"Order '{new_order.order_number}' created for customer '{customer.email}'")

        return OrderResponse(
            id=new_order.id,
            order_number=new_order.order_number,
            customer_id=customer.id,
            customer_email=customer.email,
            customer_name=customer.full_name,
            status=new_order.status,
            total_amount=new_order.total_amount,
            currency=new_order.currency,
            shipping_address=new_order.shipping_address,
            raw_source=new_order.raw_source,
            created_at=new_order.created_at,
            updated_at=new_order.updated_at,
            items=items_responses,
        )

    @staticmethod
    async def update_order_status(
        db: AsyncSession,
        order_id: uuid.UUID,
        data: UpdateOrderStatusRequest,
        actor_id: Optional[uuid.UUID] = None,
    ) -> OrderResponse:
        """
        Executes a validated lifecycle status transition, triggering stock reservation,
        cancellation restoration, or idempotent delivery deduction.
        """
        order = await OrderService.get_order_by_id(db, order_id)
        if not order:
            raise NotFoundException(f"Order with ID '{order_id}' not found")

        current_status = order.status
        target_status = data.new_status

        # Idempotency check: If already in target status (e.g. repeated DELIVERED webhook), no-op
        if current_status == target_status:
            logger.info(f"Order '{order.order_number}' is already in status '{target_status}'. Idempotent return.")
            return OrderService._to_order_response(order)

        # Validate allowed transition
        allowed = ALLOWED_TRANSITIONS.get(current_status, set())
        if target_status not in allowed:
            raise StateTransitionException(
                f"Illegal order transition from '{current_status}' to '{target_status}'. Allowed: {sorted(list(allowed))}"
            )

        # ==========================================
        # 1. STOCK RESERVATION (Transition to CONFIRMED)
        # ==========================================
        if target_status == "CONFIRMED":
            # Check stock availability for all items first
            for item in order.items:
                inv_stmt = select(Inventory).where(Inventory.product_id == item.product_id)
                inv_res = await db.execute(inv_stmt)
                inv = inv_res.scalar_one_or_none()
                if not inv or inv.available_qty < item.quantity:
                    avail = inv.available_qty if inv else 0
                    logger.warning(
                        f"Stock check failed for order {order.order_number}: Product {item.product_id} "
                        f"requested {item.quantity}, available {avail}"
                    )
                    # Automatically transition to OUT_OF_STOCK
                    order.status = "OUT_OF_STOCK"
                    ev = OrderEvent(
                        order_id=order.id,
                        from_status=current_status,
                        to_status="OUT_OF_STOCK",
                        event_type="STOCK_UNAVAILABLE",
                        description=f"Insufficient inventory for item {item.product_id}",
                        actor_id=actor_id,
                    )
                    db.add(ev)
                    await db.commit()
                    raise InsufficientStockException(
                        f"Cannot confirm order {order.order_number}: Insufficient available stock for product {item.product_id} (Available: {avail}, Requested: {item.quantity})"
                    )


            # Atomically reserve stock
            for item in order.items:
                inv_stmt = select(Inventory).where(Inventory.product_id == item.product_id)
                inv = (await db.execute(inv_stmt)).scalar_one()
                inv.available_qty -= item.quantity
                inv.reserved_qty += item.quantity

                movement = InventoryMovement(
                    product_id=item.product_id,
                    delta_qty=-item.quantity,
                    movement_type="ORDER_RESERVATION",
                    reason=f"Stock reserved for Order {order.order_number}",
                    order_id=order.id,
                    actor_user_id=actor_id,
                )
                db.add(movement)

        # ==========================================
        # 2. STOCK RESTORATION (Transition to CANCELLED from reserved state)
        # ==========================================
        elif target_status == "CANCELLED" and current_status in RESERVED_STOCK_STATES:
            for item in order.items:
                inv_stmt = select(Inventory).where(Inventory.product_id == item.product_id)
                inv_res = await db.execute(inv_stmt)
                inv = inv_res.scalar_one_or_none()
                if inv:
                    inv.reserved_qty = max(0, inv.reserved_qty - item.quantity)
                    inv.available_qty += item.quantity

                    movement = InventoryMovement(
                        product_id=item.product_id,
                        delta_qty=item.quantity,
                        movement_type="ORDER_CANCEL_RESTORE",
                        reason=f"Restored stock from cancelled Order {order.order_number}",
                        order_id=order.id,
                        actor_user_id=actor_id,
                    )
                    db.add(movement)

        # ==========================================
        # 3. STOCK DEDUCTION (Transition to DELIVERED)
        # ==========================================
        elif target_status == "DELIVERED":
            for item in order.items:
                inv_stmt = select(Inventory).where(Inventory.product_id == item.product_id)
                inv_res = await db.execute(inv_stmt)
                inv = inv_res.scalar_one_or_none()
                if inv:
                    inv.reserved_qty = max(0, inv.reserved_qty - item.quantity)

                    movement = InventoryMovement(
                        product_id=item.product_id,
                        delta_qty=-item.quantity,
                        movement_type="DELIVERY_DEDUCTION",
                        reason=f"Final stock deduction upon delivery of Order {order.order_number}",
                        order_id=order.id,
                        actor_user_id=actor_id,
                    )
                    db.add(movement)

        # Update order state
        order.status = target_status
        event = OrderEvent(
            order_id=order.id,
            from_status=current_status,
            to_status=target_status,
            event_type="STATUS_CHANGE",
            description=data.reason or f"Transitioned from {current_status} to {target_status}",
            actor_id=actor_id,
        )
        db.add(event)

        audit = AuditLog(
            actor_id=actor_id,
            action="UPDATE",
            entity_name="orders",
            entity_id=order.id,
            change_diff={"status": {"old": current_status, "new": target_status}, "reason": data.reason},
        )
        db.add(audit)

        await db.commit()
        refreshed_order = await OrderService.get_order_by_id(db, order.id)
        logger.info(f"Order '{order.order_number}' transitioned from '{current_status}' -> '{target_status}'")

        return OrderService._to_order_response(refreshed_order)  # type: ignore


    @staticmethod
    async def list_orders(
        db: AsyncSession,
        status: Optional[str] = None,
        customer_id: Optional[uuid.UUID] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[OrderResponse], int]:
        query = (
            select(Order)
            .options(
                selectinload(Order.customer),
                selectinload(Order.items).selectinload(OrderItem.product),
            )
        )
        count_query = select(func.count(Order.id))

        if status:
            query = query.where(Order.status == status.upper().strip())
            count_query = count_query.where(Order.status == status.upper().strip())

        if customer_id:
            query = query.where(Order.customer_id == customer_id)
            count_query = count_query.where(Order.customer_id == customer_id)

        if search:
            search_pat = f"%{search.strip().upper()}%"
            query = query.where(Order.order_number.like(search_pat))
            count_query = count_query.where(Order.order_number.like(search_pat))

        total_res = await db.execute(count_query)
        total = total_res.scalar() or 0

        query = query.order_by(Order.created_at.desc()).offset(skip).limit(limit)
        res = await db.execute(query)
        orders = res.scalars().all()

        return [OrderService._to_order_response(o) for o in orders], total

    @staticmethod
    async def get_order_events(db: AsyncSession, order_id: uuid.UUID) -> List[OrderEventResponse]:
        stmt = (
            select(OrderEvent)
            .where(OrderEvent.order_id == order_id)
            .order_by(OrderEvent.created_at.asc())
        )
        res = await db.execute(stmt)
        events = res.scalars().all()
        return [
            OrderEventResponse(
                id=ev.id,
                order_id=ev.order_id,
                from_status=ev.from_status,
                to_status=ev.to_status,
                event_type=ev.event_type,
                description=ev.description,
                actor_id=ev.actor_id,
                metadata=ev.event_metadata,
                created_at=ev.created_at,
            )
            for ev in events
        ]

    @staticmethod
    def _to_order_response(order: Order) -> OrderResponse:
        items = []
        for item in order.items or []:
            items.append(
                OrderItemResponse(
                    id=item.id,
                    order_id=order.id,
                    product_id=item.product_id,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    total_price=item.total_price,
                    product_sku=item.product.sku if item.product else None,
                    product_name=item.product.name if item.product else None,
                )
            )

        return OrderResponse(
            id=order.id,
            order_number=order.order_number,
            customer_id=order.customer_id,
            customer_email=order.customer.email if order.customer else None,
            customer_name=order.customer.full_name if order.customer else None,
            status=order.status,
            total_amount=order.total_amount,
            currency=order.currency,
            shipping_address=order.shipping_address,
            raw_source=order.raw_source,
            created_at=order.created_at,
            updated_at=order.updated_at,
            items=items,
        )
