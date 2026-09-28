import uuid
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Tuple, Dict, Any
from sqlalchemy import select, func, or_, update
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    NotFoundException,
    ConflictException,
    InsufficientStockException,
    ValidationException,
)
from app.models.product import Product
from app.models.inventory import Inventory
from app.models.inventory_movement import InventoryMovement
from app.models.audit_log import AuditLog
from app.schemas.product import (
    CreateProductRequest,
    UpdateProductRequest,
    ProductResponse,
    ProductWithInventoryResponse,
)
from app.schemas.inventory import (
    StockAdjustmentRequest,
    InventoryResponse,
    InventoryMovementResponse,
    LowStockItemResponse,
)

logger = logging.getLogger("opsmind.inventory_service")


class InventoryService:
    """
    Business logic service managing Product catalog lifecycle,
    atomic inventory updates, low-stock threshold queries, and immutable movement auditing.
    """

    @staticmethod
    async def create_product_with_inventory(
        db: AsyncSession,
        data: CreateProductRequest,
        actor_id: Optional[uuid.UUID] = None,
    ) -> ProductWithInventoryResponse:
        """
        Atomically provisions a Product catalog item and its corresponding Inventory ledger record.
        """
        existing_stmt = select(Product).where(Product.sku == data.sku.upper().strip())
        existing = (await db.execute(existing_stmt)).scalar_one_or_none()
        if existing:
            raise ConflictException(f"A product with SKU '{data.sku}' already exists.")

        new_product = Product(
            sku=data.sku.upper().strip(),
            name=data.name.strip(),
            description=data.description,
            unit_price=data.price,
            category=data.category.strip() if data.category else None,
            is_active=True,
        )

        db.add(new_product)
        await db.flush()

        inventory = Inventory(
            product_id=new_product.id,
            available_qty=data.initial_stock,
            reserved_qty=0,
            reorder_level=data.reorder_level,
            last_restocked_at=datetime.now(timezone.utc) if data.initial_stock > 0 else None,
        )
        db.add(inventory)
        await db.flush()

        if data.initial_stock > 0:
            movement = InventoryMovement(
                product_id=new_product.id,
                delta_qty=data.initial_stock,
                movement_type="PURCHASE_RECEIPT",
                reason="Initial inventory intake upon product provisioning",
                actor_user_id=actor_id,
            )
            db.add(movement)

        # Audit log creation
        audit = AuditLog(
            actor_id=actor_id,
            action="CREATE",
            entity_name="products",
            entity_id=new_product.id,
            change_diff={"sku": new_product.sku, "initial_stock": data.initial_stock, "price": str(data.price)},
        )
        db.add(audit)

        await db.commit()
        await db.refresh(new_product)
        await db.refresh(inventory)

        logger.info(f"Product '{new_product.sku}' created with {data.initial_stock} initial stock")
        return ProductWithInventoryResponse(
            id=new_product.id,
            sku=new_product.sku,
            name=new_product.name,
            description=new_product.description,
            price=new_product.price,
            category=new_product.category,
            is_active=new_product.is_active,
            created_at=new_product.created_at,
            updated_at=new_product.updated_at,
            available_qty=inventory.available_qty,
            reserved_qty=inventory.reserved_qty,
            total_qty=inventory.available_qty + inventory.reserved_qty,
            reorder_level=inventory.reorder_level,
            is_low_stock=inventory.available_qty <= inventory.reorder_level,
        )

    @staticmethod
    async def get_product_by_id(db: AsyncSession, product_id: uuid.UUID) -> Optional[Product]:
        stmt = select(Product).options(selectinload(Product.inventory)).where(Product.id == product_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_product_with_inventory(
        db: AsyncSession, product_id: uuid.UUID
    ) -> Optional[ProductWithInventoryResponse]:
        product = await InventoryService.get_product_by_id(db, product_id)
        if not product:
            return None

        inv = product.inventory
        available = inv.available_qty if inv else 0
        reserved = inv.reserved_qty if inv else 0
        reorder = inv.reorder_level if inv else 10

        return ProductWithInventoryResponse(
            id=product.id,
            sku=product.sku,
            name=product.name,
            description=product.description,
            price=product.price,
            category=product.category,
            is_active=product.is_active,
            created_at=product.created_at,
            updated_at=product.updated_at,
            available_qty=available,
            reserved_qty=reserved,
            total_qty=available + reserved,
            reorder_level=reorder,
            is_low_stock=available <= reorder,
        )

    @staticmethod
    async def list_products(
        db: AsyncSession,
        category: Optional[str] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[ProductWithInventoryResponse], int]:
        query = select(Product).options(selectinload(Product.inventory))
        count_query = select(func.count(Product.id))

        if category:
            query = query.where(func.lower(Product.category) == category.lower().strip())
            count_query = count_query.where(func.lower(Product.category) == category.lower().strip())

        if is_active is not None:
            query = query.where(Product.is_active == is_active)
            count_query = count_query.where(Product.is_active == is_active)

        if search:
            search_pattern = f"%{search.strip().lower()}%"
            filter_clause = or_(
                func.lower(Product.sku).like(search_pattern),
                func.lower(Product.name).like(search_pattern),
                func.lower(Product.description).like(search_pattern),
            )
            query = query.where(filter_clause)
            count_query = count_query.where(filter_clause)

        total_res = await db.execute(count_query)
        total = total_res.scalar() or 0

        query = query.order_by(Product.created_at.desc()).offset(skip).limit(limit)
        res = await db.execute(query)
        products = res.scalars().all()

        results = []
        for p in products:
            inv = p.inventory
            avail = inv.available_qty if inv else 0
            resv = inv.reserved_qty if inv else 0
            reord = inv.reorder_level if inv else 10
            results.append(
                ProductWithInventoryResponse(
                    id=p.id,
                    sku=p.sku,
                    name=p.name,
                    description=p.description,
                    price=p.price,
                    category=p.category,
                    is_active=p.is_active,
                    created_at=p.created_at,
                    updated_at=p.updated_at,
                    available_qty=avail,
                    reserved_qty=resv,
                    total_qty=avail + resv,
                    reorder_level=reord,
                    is_low_stock=avail <= reord,
                )
            )

        return results, total

    @staticmethod
    async def update_product(
        db: AsyncSession,
        product_id: uuid.UUID,
        data: UpdateProductRequest,
        actor_id: Optional[uuid.UUID] = None,
    ) -> ProductWithInventoryResponse:
        product = await InventoryService.get_product_by_id(db, product_id)
        if not product:
            raise NotFoundException(f"Product with ID '{product_id}' not found")

        diff: Dict[str, Any] = {}
        if data.name is not None and data.name != product.name:
            diff["name"] = {"old": product.name, "new": data.name}
            product.name = data.name.strip()

        if data.description is not None and data.description != product.description:
            diff["description"] = {"old": product.description, "new": data.description}
            product.description = data.description

        if data.price is not None and data.price != product.price:
            diff["price"] = {"old": str(product.price), "new": str(data.price)}
            product.price = data.price

        if data.category is not None and data.category != product.category:
            diff["category"] = {"old": product.category, "new": data.category}
            product.category = data.category.strip() if data.category else None

        if data.is_active is not None and data.is_active != product.is_active:
            diff["is_active"] = {"old": product.is_active, "new": data.is_active}
            product.is_active = data.is_active

        if diff:
            audit = AuditLog(
                actor_id=actor_id,
                action="UPDATE" if data.is_active is not False else "SOFT_DELETE",
                entity_name="products",
                entity_id=product.id,
                change_diff=diff,
            )
            db.add(audit)

        await db.commit()
        await db.refresh(product)
        return await InventoryService.get_product_with_inventory(db, product.id)  # type: ignore

    @staticmethod
    async def soft_delete_product(
        db: AsyncSession, product_id: uuid.UUID, actor_id: Optional[uuid.UUID] = None
    ) -> ProductWithInventoryResponse:
        """
        Soft-deactivates product (is_active = False) ensuring referential integrity for historic orders.
        """
        return await InventoryService.update_product(
            db, product_id, UpdateProductRequest(is_active=False), actor_id=actor_id
        )

    @staticmethod
    async def adjust_stock(
        db: AsyncSession,
        product_id: uuid.UUID,
        delta_qty: int,
        movement_type: str = "MANUAL_CORRECTION",
        reason: Optional[str] = None,
        order_id: Optional[uuid.UUID] = None,
        actor_id: Optional[uuid.UUID] = None,
    ) -> InventoryResponse:
        """
        Atomically updates available inventory and logs an immutable InventoryMovement record.
        """
        stmt = select(Inventory).where(Inventory.product_id == product_id)
        result = await db.execute(stmt)
        inventory = result.scalar_one_or_none()

        if not inventory:
            raise NotFoundException(f"Inventory record for Product '{product_id}' not found")

        if inventory.available_qty + delta_qty < 0:
            raise InsufficientStockException(
                f"Cannot adjust stock by {delta_qty}. Current available stock is {inventory.available_qty}."
            )

        old_available = inventory.available_qty
        inventory.available_qty += delta_qty
        if delta_qty > 0:
            inventory.last_restocked_at = datetime.now(timezone.utc)

        # Create immutable movement audit
        movement = InventoryMovement(
            product_id=product_id,
            delta_qty=delta_qty,
            movement_type=movement_type,
            reason=reason or f"Stock adjustment delta {delta_qty}",
            order_id=order_id,
            actor_user_id=actor_id,
        )
        db.add(movement)

        # Record system audit
        audit = AuditLog(
            actor_id=actor_id,
            action="STOCK_ADJUST",
            entity_name="inventory",
            entity_id=inventory.id,
            change_diff={
                "delta": delta_qty,
                "old_available": old_available,
                "new_available": inventory.available_qty,
                "movement_type": movement_type,
            },
        )
        db.add(audit)

        await db.commit()
        await db.refresh(inventory)
        logger.info(
            f"Adjusted stock for product {product_id} by {delta_qty} (New available: {inventory.available_qty})"
        )
        return InventoryResponse.model_validate(inventory)

    @staticmethod
    async def get_low_stock_items(db: AsyncSession) -> List[LowStockItemResponse]:
        """
        Identifies all active products where available inventory is at or below reorder threshold.
        """
        stmt = (
            select(Product, Inventory)
            .join(Inventory, Product.id == Inventory.product_id)
            .where(Product.is_active == True)
            .where(Inventory.available_qty <= Inventory.reorder_level)
            .order_by(Inventory.available_qty.asc())
        )
        result = await db.execute(stmt)
        rows = result.all()

        low_stock_items = []
        for product, inventory in rows:
            deficit = max(0, inventory.reorder_level - inventory.available_qty)
            low_stock_items.append(
                LowStockItemResponse(
                    product_id=product.id,
                    sku=product.sku,
                    name=product.name,
                    category=product.category,
                    available_qty=inventory.available_qty,
                    reserved_qty=inventory.reserved_qty,
                    reorder_level=inventory.reorder_level,
                    deficit=deficit,
                )
            )
        return low_stock_items

    @staticmethod
    async def list_movements(
        db: AsyncSession,
        product_id: Optional[uuid.UUID] = None,
        order_id: Optional[uuid.UUID] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[InventoryMovement], int]:
        query = select(InventoryMovement)
        count_query = select(func.count(InventoryMovement.id))

        if product_id:
            query = query.where(InventoryMovement.product_id == product_id)
            count_query = count_query.where(InventoryMovement.product_id == product_id)

        if order_id:
            query = query.where(InventoryMovement.order_id == order_id)
            count_query = count_query.where(InventoryMovement.order_id == order_id)

        total_res = await db.execute(count_query)
        total = total_res.scalar() or 0

        query = query.order_by(InventoryMovement.created_at.desc()).offset(skip).limit(limit)
        res = await db.execute(query)
        movements = list(res.scalars().all())

        return movements, total
