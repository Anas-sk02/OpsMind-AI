import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from sqlalchemy import Integer, DateTime, ForeignKey, CheckConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.product import Product


class Inventory(Base):
    """
    SQLAlchemy 2.0 model representing current stock level for a product.
    Maintains available vs. reserved quantities with non-negative check constraints.
    """
    __tablename__ = "inventory"
    __table_args__ = (
        CheckConstraint("available_qty >= 0", name="chk_inventory_available_qty_non_negative"),
        CheckConstraint("reserved_qty >= 0", name="chk_inventory_reserved_qty_non_negative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    available_qty: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    reserved_qty: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    reorder_level: Mapped[int] = mapped_column(
        Integer,
        default=10,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # 1-to-1 Relationship back to Product
    product: Mapped["Product"] = relationship(
        "Product",
        back_populates="inventory",
    )

    @property
    def total_physical_qty(self) -> int:
        return self.available_qty + self.reserved_qty

    @property
    def is_low_stock(self) -> bool:
        return self.available_qty <= self.reorder_level

    def __repr__(self) -> str:
        return (
            f"<Inventory product_id={self.product_id} available={self.available_qty} "
            f"reserved={self.reserved_qty} reorder_level={self.reorder_level}>"
        )
