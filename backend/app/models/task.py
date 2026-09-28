import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, DateTime, Text, ForeignKey, Index, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.user import User


class Task(Base):
    """
    SQLAlchemy 2.0 model representing packaging and delivery tasks assigned to warehouse staff.
    Supports least-loaded employee auto-assignment workflows.
    """
    __tablename__ = "tasks"
    __table_args__ = (
        # Fast indexing for employee task queries and active workload lookups
        Index("idx_tasks_assigned_status", "assigned_employee_id", "status"),
        Index("idx_tasks_type_status", "task_type", "status"),
    )

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
    assigned_employee_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    task_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,  # "PACKAGING" | "DELIVERY"
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="PENDING",
        index=True,
        nullable=False,  # "PENDING" | "IN_PROGRESS" | "COMPLETED" | "EXCEPTION"
    )
    exception_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    order: Mapped["Order"] = relationship(
        "Order",
        back_populates="tasks",
        lazy="selectin",
    )
    assigned_employee: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="assigned_tasks",
        lazy="selectin",
    )


    def mark_completed(self) -> None:
        self.status = "COMPLETED"
        self.completed_at = datetime.now(timezone.utc)

    def mark_exception(self, notes: str) -> None:
        self.status = "EXCEPTION"
        self.exception_notes = notes

    def __repr__(self) -> str:
        return (
            f"<Task id={self.id} type={self.task_type} status={self.status} "
            f"order_id={self.order_id} employee_id={self.assigned_employee_id}>"
        )
