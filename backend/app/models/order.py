import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, DateTime, Text, Numeric, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.order_item import OrderItem
    from app.models.task import Task
    from app.models.email_message import EmailMessage
    from app.models.audit_log import OrderEvent
    from app.models.inventory_movement import InventoryMovement


class Order(Base):
    """
    SQLAlchemy 2.0 model representing a customer order lifecycle.
    Tracks state transitions from ingestion to final delivery.
    """
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    order_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="RECEIVED",
        index=True,
        nullable=False,
        # States: "RECEIVED", "PROCESSING", "CONFIRMED", "PACKAGING", "PACKED",
        # "OUT_FOR_DELIVERY", "DELIVERED", "NEEDS_REVIEW", "OUT_OF_STOCK", "CANCELLED", "FAILED"
    )
    source_email_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    delivery_address: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    expected_delivery_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    @property
    def shipping_address(self) -> str:
        return self.delivery_address

    @shipping_address.setter
    def shipping_address(self, value: str):
        self.delivery_address = value

    @property
    def currency(self) -> str:
        return "USD"

    @property
    def raw_source(self) -> str:
        return self.source_email_id or "EMAIL"

    @raw_source.setter
    def raw_source(self, value: Optional[str]):
        self.source_email_id = value

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    customer: Mapped["Customer"] = relationship(
        "Customer",
        back_populates="orders",
        lazy="selectin",
    )
    items: Mapped[List["OrderItem"]] = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    tasks: Mapped[List["Task"]] = relationship(
        "Task",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    email_messages: Mapped[List["EmailMessage"]] = relationship(
        "EmailMessage",
        back_populates="order",
        lazy="selectin",
    )
    order_events: Mapped[List["OrderEvent"]] = relationship(
        "OrderEvent",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    inventory_movements: Mapped[List["InventoryMovement"]] = relationship(
        "InventoryMovement",
        back_populates="order",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Order id={self.id} number={self.order_number} status={self.status} total={self.total_amount}>"
