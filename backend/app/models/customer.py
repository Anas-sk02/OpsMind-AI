import uuid
from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Boolean, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.email_message import EmailMessage


class Customer(Base):
    """
    SQLAlchemy 2.0 model representing a customer entity.
    Customers interact exclusively via Email (No password/login credentials).
    """
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )
    phone: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    address: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    preferred_language: Mapped[str] = mapped_column(
        String(10),
        default="en",
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )
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
    orders: Mapped[List["Order"]] = relationship(
        "Order",
        back_populates="customer",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    email_messages: Mapped[List["EmailMessage"]] = relationship(
        "EmailMessage",
        back_populates="customer",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Customer id={self.id} email={self.email} name={self.name}>"
