import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_admin, require_operator
from app.core.exceptions import NotFoundException
from app.models.user import User
from app.schemas.common import ApiResponse, PaginatedResponse
from app.schemas.order import (
    CreateOrderRequest,
    UpdateOrderStatusRequest,
    OrderResponse,
    OrderEventResponse,
)
from app.services.order_service import OrderService

router = APIRouter(prefix="/admin/orders", tags=["Admin Orders"])


@router.get(
    "",
    response_model=PaginatedResponse[OrderResponse],
    summary="List orders with state, customer, and line items",
)
async def list_orders(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (e.g. RECEIVED, CONFIRMED)"),
    customer_id: Optional[uuid.UUID] = Query(None, description="Filter by customer ID"),
    search: Optional[str] = Query(None, description="Search by order number prefix"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    skip = (page - 1) * page_size
    orders, total = await OrderService.list_orders(
        db, status=status_filter, customer_id=customer_id, search=search, skip=skip, limit=page_size
    )
    return PaginatedResponse.create(
        items=orders,
        total=total,
        page=page,
        page_size=page_size,
    )



@router.post(
    "",
    response_model=ApiResponse[OrderResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new customer order manually or via ingested channel",
)
async def create_order(
    payload: CreateOrderRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    order = await OrderService.create_order(db, data=payload, actor_id=admin.id)
    return ApiResponse(data=order, message=f"Order '{order.order_number}' created successfully")


@router.get(
    "/{order_id}",
    response_model=ApiResponse[OrderResponse],
    summary="Get full order details, customer info, and line items",
)
async def get_order(
    order_id: uuid.UUID = Path(..., description="Target order UUID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    order = await OrderService.get_order_by_id(db, order_id)
    if not order:
        raise NotFoundException(f"Order with ID '{order_id}' not found")
    return ApiResponse(data=OrderService._to_order_response(order))


@router.patch(
    "/{order_id}/status",
    response_model=ApiResponse[OrderResponse],
    summary="Transition order status with state machine verification and stock automation",
)
async def update_order_status(
    order_id: uuid.UUID = Path(..., description="Target order UUID"),
    payload: UpdateOrderStatusRequest = ...,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    updated = await OrderService.update_order_status(
        db, order_id=order_id, data=payload, actor_id=current_user.id
    )
    return ApiResponse(
        data=updated,
        message=f"Order '{updated.order_number}' successfully transitioned to '{updated.status}'",
    )


@router.get(
    "/{order_id}/events",
    response_model=ApiResponse[List[OrderEventResponse]],
    summary="Get audit event log history for an order",
)
async def get_order_events(
    order_id: uuid.UUID = Path(..., description="Target order UUID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    events = await OrderService.get_order_events(db, order_id)
    return ApiResponse(data=events)
