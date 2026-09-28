import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, ConfigDict, Field

OrderStatus = Literal[
    "RECEIVED",
    "PROCESSING",
    "CONFIRMED",
    "PACKAGING",
    "PACKED",
    "OUT_FOR_DELIVERY",
    "DELIVERED",
    "CANCELLED",
    "OUT_OF_STOCK",
    "NEEDS_REVIEW",
]


class CreateOrderItemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: uuid.UUID = Field(..., description="Target product UUID")
    quantity: int = Field(..., gt=0, description="Quantity to order")
    unit_price: Optional[Decimal] = Field(None, ge=0, description="Optional override; defaults to product price")


class CreateOrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_email: str = Field(..., min_length=5, max_length=255, description="Customer contact email")
    customer_name: Optional[str] = Field(None, max_length=150, description="Customer full name")
    shipping_address: str = Field(..., min_length=5, description="Physical delivery destination")
    items: List[CreateOrderItemRequest] = Field(..., min_length=1, description="Order line items")
    source: str = Field("EMAIL", description="Ingestion channel: EMAIL, MANUAL, WEBHOOK")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class UpdateOrderStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    new_status: OrderStatus = Field(..., description="Target lifecycle status")
    reason: Optional[str] = Field(None, max_length=255, description="Optional note for status transition")


class OrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_id: uuid.UUID
    product_id: uuid.UUID
    quantity: int
    unit_price: Decimal
    total_price: Decimal
    product_sku: Optional[str] = None
    product_name: Optional[str] = None


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_number: str
    customer_id: uuid.UUID
    customer_email: Optional[str] = None
    customer_name: Optional[str] = None
    status: str
    total_amount: Decimal
    currency: str
    shipping_address: str
    raw_source: str
    created_at: datetime
    updated_at: datetime
    items: List[OrderItemResponse] = []


class OrderEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_id: uuid.UUID
    from_status: Optional[str]
    to_status: str
    event_type: str
    description: Optional[str]
    actor_id: Optional[uuid.UUID]
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
