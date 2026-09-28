import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_admin, require_operator
from app.models.user import User
from app.schemas.common import ApiResponse, PaginatedResponse
from app.schemas.inventory import (
    StockAdjustmentRequest,
    InventoryResponse,
    InventoryMovementResponse,
    LowStockItemResponse,
)
from app.services.inventory_service import InventoryService

router = APIRouter(prefix="/admin/inventory", tags=["Admin Inventory"])


@router.post(
    "/adjust",
    response_model=ApiResponse[InventoryResponse],
    summary="Record manual stock adjustment with immutable ledger audit",
)
async def adjust_stock(
    payload: StockAdjustmentRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    inv = await InventoryService.adjust_stock(
        db,
        product_id=payload.product_id,
        delta_qty=payload.delta_qty,
        movement_type=payload.movement_type,
        reason=payload.reason,
        actor_id=admin.id,
    )
    return ApiResponse(
        data=inv,
        message=f"Successfully adjusted stock by {payload.delta_qty}. New available qty: {inv.available_qty}",
    )


@router.get(
    "/low-stock",
    response_model=ApiResponse[List[LowStockItemResponse]],
    summary="Get active products at or below reorder threshold",
)
async def get_low_stock_items(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    items = await InventoryService.get_low_stock_items(db)
    return ApiResponse(data=items)


@router.get(
    "/movements",
    response_model=PaginatedResponse[InventoryMovementResponse],
    summary="List immutable stock movement audit ledger",
)
async def list_movements(
    product_id: Optional[uuid.UUID] = Query(None, description="Filter movements by product"),
    order_id: Optional[uuid.UUID] = Query(None, description="Filter movements by order"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    skip = (page - 1) * page_size
    movements, total = await InventoryService.list_movements(
        db, product_id=product_id, order_id=order_id, skip=skip, limit=page_size
    )
    movement_dtos = [InventoryMovementResponse.model_validate(m) for m in movements]
    return PaginatedResponse.create(
        items=movement_dtos,
        total=total,
        page=page,
        page_size=page_size,
    )

