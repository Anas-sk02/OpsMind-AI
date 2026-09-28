import uuid
from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.order import OrderItemResponse

TaskType = Literal["PACKAGING", "DELIVERY"]
TaskStatus = Literal["PENDING", "IN_PROGRESS", "COMPLETED", "EXCEPTION"]


class UpdateTaskStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    new_status: TaskStatus = Field(..., description="Target status: IN_PROGRESS, COMPLETED, EXCEPTION")
    exception_notes: Optional[str] = Field(None, max_length=1000, description="Required if new_status is EXCEPTION")


class ReassignTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assigned_employee_id: uuid.UUID = Field(..., description="Target employee UUID")


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_id: uuid.UUID
    order_number: Optional[str] = None
    assigned_employee_id: Optional[uuid.UUID] = None
    assigned_employee_name: Optional[str] = None
    task_type: str
    status: str
    exception_notes: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class TaskWithOrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_id: uuid.UUID
    order_number: str
    order_status: str
    task_type: str
    status: str
    assigned_employee_id: Optional[uuid.UUID] = None
    assigned_employee_name: Optional[str] = None
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    delivery_address: str
    items: List[OrderItemResponse] = []
    exception_notes: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class EmployeeWorkloadMetric(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    employee_id: uuid.UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    active_tasks: int = 0
    completed_tasks: int = 0
