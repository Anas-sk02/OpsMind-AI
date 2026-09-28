import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Integer, DateTime, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.order import Order
    from app.models.user import User


class InventoryMovement(Base):
    """
    SQLAlchemy 2.0 immutable audit ledger tracking every stock mutation event.
    Guarantees full financial and inventory traceability.
    """
    __tablename__ = "inventory_movements"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    delta_qty: Mapped[int] = mapped_column(
        Integer,
        nullable=False,  # Positive for addition, negative for deduction
    )
    movement_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        # Values: "PURCHASE_RECEIPT", "ORDER_RESERVATION", "DELIVERY_DEDUCTION",
        # "MANUAL_CORRECTION", "ORDER_CANCEL_RESTORE", "RETURN"
    )
    reason: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    order_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("orders.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    actor_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    product: Mapped["Product"] = relationship(
        "Product",
        back_populates="inventory_movements",
    )
    order: Mapped[Optional["Order"]] = relationship(
        "Order",
        back_populates="inventory_movements",
    )
    actor_user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="inventory_movements",
    )

    def __repr__(self) -> str:
        return (
            f"<InventoryMovement id={self.id} product_id={self.product_id} "
            f"delta_qty={self.delta_qty} type={self.movement_type}>"
        )
