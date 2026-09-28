import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, TYPE_CHECKING
from sqlalchemy import String, DateTime, Text, ForeignKey, JSON, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.order import Order


class EmailMessage(Base):
    """
    SQLAlchemy 2.0 model logging all inbound and outbound emails.
    Stores raw email content and structured AI extraction payloads.
    """
    __tablename__ = "email_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    message_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("customers.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    order_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("orders.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    direction: Mapped[str] = mapped_column(
        String(20),
        default="INBOUND",  # "INBOUND" | "OUTBOUND"
        index=True,
        nullable=False,
    )
    sender_email: Mapped[str] = mapped_column(
        String(255),
        index=True,
        nullable=False,
    )
    recipient_email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    subject: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    body_plain: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    body_html: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    detected_language: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
    )
    ai_extraction_payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    customer: Mapped[Optional["Customer"]] = relationship(
        "Customer",
        back_populates="email_messages",
    )
    order: Mapped[Optional["Order"]] = relationship(
        "Order",
        back_populates="email_messages",
    )

    def __repr__(self) -> str:
        return (
            f"<EmailMessage id={self.id} msg_id={self.message_id} "
            f"direction={self.direction} sender={self.sender_email}>"
        )
