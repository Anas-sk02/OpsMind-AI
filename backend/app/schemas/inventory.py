import uuid
from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, ConfigDict, Field

MovementType = Literal[
    "PURCHASE_RECEIPT",
    "ORDER_RESERVATION",
    "DELIVERY_DEDUCTION",
    "MANUAL_CORRECTION",
    "ORDER_CANCEL_RESTORE",
    "RETURN",
]


class StockAdjustmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: uuid.UUID = Field(..., description="Target product UUID")
    delta_qty: int = Field(..., description="Positive to add stock, negative to deduct")
    movement_type: MovementType = Field("MANUAL_CORRECTION", description="Category of stock mutation")
    reason: Optional[str] = Field(None, max_length=255, description="Auditing justification for adjustment")



class InventoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    available_qty: int
    reserved_qty: int
    reorder_level: int
    last_restocked_at: Optional[datetime]
    updated_at: datetime


class InventoryMovementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    delta_qty: int
    movement_type: str
    reason: Optional[str]
    order_id: Optional[uuid.UUID]
    actor_user_id: Optional[uuid.UUID]
    created_at: datetime


class LowStockItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: uuid.UUID
    sku: str
    name: str
    category: Optional[str]
    available_qty: int
    reserved_qty: int
    reorder_level: int
    deficit: int
