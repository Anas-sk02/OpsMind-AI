import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_operator, require_admin
from app.core.exceptions import NotFoundException, ForbiddenException
from app.models.user import User
from app.schemas.common import ApiResponse, PaginatedResponse
from app.schemas.task import (
    TaskResponse,
    TaskWithOrderResponse,
    UpdateTaskStatusRequest,
    ReassignTaskRequest,
    EmployeeWorkloadMetric,
)
from app.services.task_service import TaskService

router = APIRouter(tags=["Employee & Warehouse Tasks"])


@router.get(
    "/employee/tasks/my",
    response_model=PaginatedResponse[TaskWithOrderResponse],
    summary="List tasks assigned to the currently authenticated operator",
)
async def list_my_tasks(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status: PENDING, IN_PROGRESS, COMPLETED, EXCEPTION"),
    task_type: Optional[str] = Query(None, description="Filter by PACKAGING or DELIVERY"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    skip = (page - 1) * page_size
    tasks, total = await TaskService.list_operator_tasks(
        db,
        employee_id=current_user.id,
        status_filter=status_filter,
        task_type=task_type,
        skip=skip,
        limit=page_size,
    )
    return PaginatedResponse.create(
        items=tasks,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/employee/tasks/{task_id}",
    response_model=ApiResponse[TaskWithOrderResponse],
    summary="Get single task details with line items and customer delivery address",
)
async def get_task_details(
    task_id: uuid.UUID = Path(..., description="Target task UUID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    task = await TaskService.get_task_with_order(db, task_id)
    if not task:
        raise NotFoundException(f"Task with ID '{task_id}' not found")

    # Access control: Operators can only inspect their own tasks; Admins can inspect any
    if current_user.role != "ADMIN" and task.assigned_employee_id != current_user.id:
        raise ForbiddenException("Access denied: You cannot view tasks assigned to another employee.")

    return ApiResponse(data=task)


@router.patch(
    "/employee/tasks/{task_id}/status",
    response_model=ApiResponse[TaskWithOrderResponse],
    summary="Transition task status (IN_PROGRESS, COMPLETED, EXCEPTION) with downstream order stage automation",
)
async def update_task_status(
    task_id: uuid.UUID = Path(..., description="Target task UUID"),
    payload: UpdateTaskStatusRequest = ...,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    updated = await TaskService.update_task_status(
        db, task_id=task_id, data=payload, actor=current_user
    )
    return ApiResponse(
        data=updated,
        message=f"Task {task_id} successfully transitioned to '{updated.status}'",
    )


@router.post(
    "/employee/tasks/{task_id}/complete",
    response_model=ApiResponse[TaskWithOrderResponse],
    summary="Convenience endpoint to complete task with optional notes",
)
async def complete_task_endpoint(
    task_id: uuid.UUID = Path(..., description="Target task UUID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    payload = UpdateTaskStatusRequest(new_status="COMPLETED")
    updated = await TaskService.update_task_status(
        db, task_id=task_id, data=payload, actor=current_user
    )
    return ApiResponse(
        data=updated,
        message=f"Task {task_id} marked COMPLETED",
    )


@router.post(
    "/employee/tasks/{task_id}/exception",
    response_model=ApiResponse[TaskWithOrderResponse],
    summary="Convenience endpoint to mark task as EXCEPTION with notes",
)
async def report_task_exception_endpoint(
    task_id: uuid.UUID = Path(..., description="Target task UUID"),
    reason: Optional[dict] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    notes = reason.get("reason") if isinstance(reason, dict) else "Task exception reported"
    payload = UpdateTaskStatusRequest(new_status="EXCEPTION", exception_notes=notes)
    updated = await TaskService.update_task_status(
        db, task_id=task_id, data=payload, actor=current_user
    )
    return ApiResponse(
        data=updated,
        message=f"Task {task_id} marked EXCEPTION",
    )


@router.get(
    "/admin/tasks",
    response_model=PaginatedResponse[TaskResponse],
    summary="Admin overview: List all warehouse packaging and delivery tasks",
)
async def list_all_tasks(
    task_type: Optional[str] = Query(None, description="Filter by PACKAGING or DELIVERY"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    employee_id: Optional[uuid.UUID] = Query(None, description="Filter by assigned employee"),
    order_id: Optional[uuid.UUID] = Query(None, description="Filter by order"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    skip = (page - 1) * page_size
    tasks, total = await TaskService.list_all_tasks(
        db,
        task_type=task_type,
        status_filter=status_filter,
        employee_id=employee_id,
        order_id=order_id,
        skip=skip,
        limit=page_size,
    )
    return PaginatedResponse.create(
        items=tasks,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/admin/tasks/{task_id}/reassign",
    response_model=ApiResponse[TaskWithOrderResponse],
    summary="Admin manual reassignment of task to another warehouse staff member",
)
async def reassign_task(
    task_id: uuid.UUID = Path(..., description="Target task UUID"),
    payload: ReassignTaskRequest = ...,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    updated = await TaskService.reassign_task(
        db, task_id=task_id, data=payload, actor_id=admin.id
    )
    return ApiResponse(
        data=updated,
        message=f"Task {task_id} successfully reassigned to employee {payload.assigned_employee_id}",
    )


@router.get(
    "/admin/tasks/workload-metrics",
    response_model=ApiResponse[List[EmployeeWorkloadMetric]],
    summary="Admin live workload analytics: Active vs. completed tasks per employee",
)
async def get_workload_metrics(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    metrics = await TaskService.get_employee_workload_metrics(db)
    return ApiResponse(data=metrics)
