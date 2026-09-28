import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class CreateProductRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku: str = Field(..., min_length=2, max_length=100, description="Unique product SKU")
    name: str = Field(..., min_length=1, max_length=255, description="Product title/name")
    description: Optional[str] = Field(None, description="Detailed product description")
    price: Decimal = Field(..., ge=0, description="Unit selling price")
    category: Optional[str] = Field(None, max_length=100, description="Product category")
    initial_stock: int = Field(0, ge=0, description="Initial available inventory quantity")
    reorder_level: int = Field(10, ge=0, description="Low stock warning threshold")


class UpdateProductRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    price: Optional[Decimal] = Field(None, ge=0)
    category: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sku: str
    name: str
    description: Optional[str]
    price: Decimal
    category: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProductWithInventoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sku: str
    name: str
    description: Optional[str]
    price: Decimal
    category: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    available_qty: int = 0
    reserved_qty: int = 0
    total_qty: int = 0
    reorder_level: int = 10
    is_low_stock: bool = False
