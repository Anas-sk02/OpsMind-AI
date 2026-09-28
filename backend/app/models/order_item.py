import uuid
from decimal import Decimal
from typing import TYPE_CHECKING
from sqlalchemy import Integer, Numeric, ForeignKey, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.product import Product


class OrderItem(Base):
    """
    SQLAlchemy 2.0 model representing a line item within a customer order.
    Captures snapshot of unit_price and historical total at time of purchase.
    """
    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="chk_order_item_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="chk_order_item_unit_price_non_negative"),
        CheckConstraint("total_price >= 0", name="chk_order_item_total_price_non_negative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    total_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    # Relationships
    order: Mapped["Order"] = relationship(
        "Order",
        back_populates="items",
    )
    product: Mapped["Product"] = relationship(
        "Product",
        back_populates="order_items",
    )

    def calculate_total(self) -> Decimal:
        self.total_price = Decimal(self.quantity) * self.unit_price
        return self.total_price

    def __repr__(self) -> str:
        return (
            f"<OrderItem id={self.id} order_id={self.order_id} "
            f"product_id={self.product_id} qty={self.quantity} total={self.total_price}>"
        )
