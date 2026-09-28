import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_admin, require_operator
from app.core.exceptions import NotFoundException
from app.models.user import User
from app.schemas.common import ApiResponse, PaginatedResponse
from app.schemas.product import (
    CreateProductRequest,
    UpdateProductRequest,
    ProductWithInventoryResponse,
)
from app.services.inventory_service import InventoryService

router = APIRouter(prefix="/admin/products", tags=["Admin Products"])


@router.get(
    "",
    response_model=PaginatedResponse[ProductWithInventoryResponse],
    summary="List product catalog with live inventory balances",
)
async def list_products(
    category: Optional[str] = Query(None, description="Filter by category"),
    is_active: Optional[bool] = Query(None, description="Filter active/inactive products"),
    search: Optional[str] = Query(None, description="Search SKU, name, or description"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    skip = (page - 1) * page_size
    items, total = await InventoryService.list_products(
        db, category=category, is_active=is_active, search=search, skip=skip, limit=page_size
    )
    return PaginatedResponse.create(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )



@router.post(
    "",
    response_model=ApiResponse[ProductWithInventoryResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Provision a new product item with initial inventory",
)
async def create_product(
    payload: CreateProductRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    product = await InventoryService.create_product_with_inventory(
        db, data=payload, actor_id=admin.id
    )
    return ApiResponse(data=product, message=f"Product '{product.sku}' created successfully")


@router.get(
    "/{product_id}",
    response_model=ApiResponse[ProductWithInventoryResponse],
    summary="Get single product details with inventory metrics",
)
async def get_product(
    product_id: uuid.UUID = Path(..., description="Target product UUID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    product = await InventoryService.get_product_with_inventory(db, product_id)
    if not product:
        raise NotFoundException(f"Product with ID '{product_id}' not found")
    return ApiResponse(data=product)


@router.patch(
    "/{product_id}",
    response_model=ApiResponse[ProductWithInventoryResponse],
    summary="Update product attributes, pricing, or status",
)
async def update_product(
    product_id: uuid.UUID = Path(..., description="Target product UUID"),
    payload: UpdateProductRequest = ...,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    updated = await InventoryService.update_product(
        db, product_id=product_id, data=payload, actor_id=admin.id
    )
    return ApiResponse(data=updated, message="Product updated successfully")


@router.delete(
    "/{product_id}",
    response_model=ApiResponse[ProductWithInventoryResponse],
    summary="Soft-delete product item",
)
async def delete_product(
    product_id: uuid.UUID = Path(..., description="Target product UUID"),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    deleted = await InventoryService.soft_delete_product(
        db, product_id=product_id, actor_id=admin.id
    )
    return ApiResponse(data=deleted, message=f"Product '{deleted.sku}' deactivated successfully")
