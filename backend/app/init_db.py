import asyncio
import logging
import os
import sys

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.core.database import engine, Base, async_session_factory
from app.models.user import User
from app.models.product import Product
from app.models.inventory import Inventory
from app.models.inventory_movement import InventoryMovement
from app.core.security import get_password_hash
from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("opsmind.init_db")


async def init_database():
    logger.info("Connecting to database and creating schema tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("All database tables created successfully.")

    async with async_session_factory() as db:
        # 1. Seed Demo Users if not present
        existing_admin = await db.execute(select(User).where(User.email == "admin@opsmind.io"))
        if not existing_admin.scalar_one_or_none():
            logger.info("Seeding default demo staff accounts...")
            admin = User(
                email="admin@opsmind.io",
                hashed_password=get_password_hash("Admin@123456!"),
                full_name="Alex Vance (Admin)",
                role="ADMIN",
                is_active=True,
            )
            packager = User(
                email="packager1@opsmind.io",
                hashed_password=get_password_hash("Packager@123456!"),
                full_name="Marcus Rivera (Packaging)",
                role="PACKAGING",
                is_active=True,
            )
            driver = User(
                email="driver1@opsmind.io",
                hashed_password=get_password_hash("Driver@123456!"),
                full_name="Elena Rostova (Driver)",
                role="DELIVERY",
                is_active=True,
            )
            db.add_all([admin, packager, driver])
            await db.commit()
            logger.info("Demo users created: admin@opsmind.io, packager1@opsmind.io, driver1@opsmind.io")

        # 2. Seed Initial Products in Catalog (Idempotent per SKU)
        demo_products = [
            {
                "sku": "SKU-PRO-MIC",
                "name": "Professional Condenser Microphone",
                "description": "Studio-grade cardioid microphone for broadcasting",
                "price": 199.99,
                "stock": 50,
                "reorder": 10,
            },
            {
                "sku": "SKU-ES-TECLADO",
                "name": "Teclado Mecánico RGB (Distribución Española)",
                "description": "Teclado mecánico ergonómico con switches táctiles",
                "price": 89.50,
                "stock": 40,
                "reorder": 8,
            },
            {
                "sku": "SKU-DEDUP-01",
                "name": "Ultra-Low Latency Wireless Mouse",
                "description": "Precision gaming mouse with 25K DPI sensor",
                "price": 59.99,
                "stock": 60,
                "reorder": 15,
            },
            {
                "sku": "SKU-LIMITED-01",
                "name": "Titanium Chronograph Smartwatch",
                "description": "Limited Edition luxury smartwatch",
                "price": 799.00,
                "stock": 5,
                "reorder": 2,
            },
        ]

        for item in demo_products:
            existing = await db.execute(select(Product).where(Product.sku == item["sku"]))
            if not existing.scalar_one_or_none():
                prod = Product(
                    sku=item["sku"],
                    name=item["name"],
                    description=item["description"],
                    price=item["price"],
                    is_active=True,
                )
                db.add(prod)
                await db.flush()

                inv = Inventory(
                    product_id=prod.id,
                    available_qty=item["stock"],
                    reserved_qty=0,
                    reorder_level=item["reorder"],
                )
                db.add(inv)

                movement = InventoryMovement(
                    product_id=prod.id,
                    delta_qty=item["stock"],
                    movement_type="PURCHASE_RECEIPT",
                    reason="Initial Catalog Ingestion",
                )
                db.add(movement)
                logger.info(f"Seeded product: {item['sku']} ({item['name']})")

        await db.commit()


if __name__ == "__main__":
    asyncio.run(init_database())
