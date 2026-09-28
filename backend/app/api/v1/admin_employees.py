import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_admin
from app.models.user import User
from app.schemas.auth import (
    CreateStaffRequest,
    UpdateStaffRequest,
    UserResponse,
)
from app.schemas.common import ApiResponse, PaginatedResponse, PaginationMeta
from app.services.auth_service import AuthService

router = APIRouter(prefix="/admin/employees", tags=["Admin Employees"])



@router.get(
    "",
    response_model=PaginatedResponse[UserResponse],
    summary="List Staff Employees",
    description="Retrieves a paginated list of staff members with optional role and status filters. Requires ADMIN role.",
)
async def list_employees(
    role: Optional[str] = Query(None, description="Filter by staff role (ADMIN, PACKAGING, DELIVERY)"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> PaginatedResponse[UserResponse]:
    skip = (page - 1) * page_size
    users, total = await AuthService.list_staff(
        db=db,
        role=role,
        is_active=is_active,
        skip=skip,
        limit=page_size,
    )

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    return PaginatedResponse(
        data=[UserResponse.model_validate(u) for u in users],
        meta=PaginationMeta(
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        ),
    )


@router.post(
    "",
    response_model=ApiResponse[UserResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create Staff Employee",
    description="Provisions a new staff user account with assigned role. Requires ADMIN role.",
)
async def create_employee(
    payload: CreateStaffRequest,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> ApiResponse[UserResponse]:
    new_user = await AuthService.register_staff(
        db=db,
        data=payload,
        actor_id=current_admin.id,
    )
    return ApiResponse(
        data=UserResponse.model_validate(new_user),
        message=f"Employee '{new_user.email}' created successfully",
    )


@router.get(
    "/{employee_id}",
    response_model=ApiResponse[UserResponse],
    summary="Get Staff Employee Details",
    description="Retrieves profile information for a specific staff member. Requires ADMIN role.",
)
async def get_employee(
    employee_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> ApiResponse[UserResponse]:
    user = await AuthService.get_user_by_id(db, employee_id)
    if not user:
        from app.core.exceptions import NotFoundException
        raise NotFoundException(f"Employee with ID '{employee_id}' was not found")

    return ApiResponse(
        data=UserResponse.model_validate(user),
        message="Employee details retrieved successfully",
    )


@router.patch(
    "/{employee_id}",
    response_model=ApiResponse[UserResponse],
    summary="Update Staff Employee",
    description="Updates role, full name, password, or active status. Requires ADMIN role.",
)
async def update_employee(
    employee_id: uuid.UUID,
    payload: UpdateStaffRequest,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> ApiResponse[UserResponse]:
    updated_user = await AuthService.update_staff(
        db=db,
        user_id=employee_id,
        data=payload,
        actor_id=current_admin.id,
    )
    return ApiResponse(
        data=UserResponse.model_validate(updated_user),
        message="Employee profile updated successfully",
    )


@router.delete(
    "/{employee_id}",
    response_model=ApiResponse[UserResponse],
    summary="Soft Delete Employee",
    description="Soft-deactivates a staff account (sets is_active = false) to preserve audit integrity. Requires ADMIN role.",
)
async def delete_employee(
    employee_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> ApiResponse[UserResponse]:
    deactivated_user = await AuthService.update_staff(
        db=db,
        user_id=employee_id,
        data=UpdateStaffRequest(is_active=False),
        actor_id=current_admin.id,
    )
    return ApiResponse(
        data=UserResponse.model_validate(deactivated_user),
        message=f"Employee '{deactivated_user.email}' has been deactivated",
    )
