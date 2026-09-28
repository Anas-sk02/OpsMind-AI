import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, TYPE_CHECKING
from sqlalchemy import String, DateTime, Text, ForeignKey, Index, JSON, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.user import User


class OrderEvent(Base):
    """
    SQLAlchemy 2.0 model recording every status transition and event in an order's lifecycle.
    """
    __tablename__ = "order_events"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    from_status: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    to_status: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )

    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="STATUS_CHANGE",
        # Values: "STATUS_CHANGE", "TASK_SPAWNED", "EMAIL_TRIGGERED", "EXCEPTION_RAISED", "STOCK_RESERVED"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    event_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        "metadata",  # column name in DB
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    order: Mapped["Order"] = relationship(
        "Order",
        back_populates="order_events",
    )
    actor: Mapped[Optional["User"]] = relationship(
        "User",
    )

    def __repr__(self) -> str:
        return (
            f"<OrderEvent id={self.id} order_id={self.order_id} "
            f"transition={self.from_status}->{self.to_status} type={self.event_type}>"
        )


class AuditLog(Base):
    """
    SQLAlchemy 2.0 system-wide audit trail for administrative mutations and entity changes.
    """
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("idx_audit_logs_entity", "entity_name", "entity_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,  # "CREATE" | "UPDATE" | "SOFT_DELETE" | "HARD_DELETE" | "STOCK_ADJUST"
    )
    entity_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,  # "products", "users", "customers", "inventory", "orders", "tasks"
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
        index=True,
    )
    change_diff: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
    )
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationship
    actor: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="audit_logs",
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog id={self.id} action={self.action} entity={self.entity_name} "
            f"entity_id={self.entity_id} actor_id={self.actor_id}>"
        )
