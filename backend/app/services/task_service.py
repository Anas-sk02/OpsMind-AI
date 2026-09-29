import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List, Tuple, Dict, Any, Set
from sqlalchemy import select, func, or_, and_, case
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    NotFoundException,
    ForbiddenException,
    ValidationException,
    StateTransitionException,
)
from app.models.user import User
from app.models.task import Task
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.audit_log import OrderEvent, AuditLog
from app.schemas.task import (
    TaskResponse,
    TaskWithOrderResponse,
    UpdateTaskStatusRequest,
    ReassignTaskRequest,
    EmployeeWorkloadMetric,
)
from app.schemas.order import OrderItemResponse, UpdateOrderStatusRequest

logger = logging.getLogger("opsmind.task_service")

ALLOWED_TASK_TRANSITIONS: Dict[str, Set[str]] = {
    "PENDING": {"IN_PROGRESS", "COMPLETED", "EXCEPTION"},
    "IN_PROGRESS": {"COMPLETED", "EXCEPTION"},
    "EXCEPTION": {"IN_PROGRESS", "COMPLETED"},
    "COMPLETED": set(),  # Terminal
}


class TaskService:
    """
    Business logic layer for warehouse task allocation, least-loaded auto-assignment,
    and automatic stage-driven workflow progression.
    """

    @staticmethod
    async def find_least_loaded_employee(
        db: AsyncSession, role: str
    ) -> Optional[User]:
        """
        Implements the least-loaded auto-assignment algorithm:
        Finds all active employees of the given role and returns the one with the fewest active tasks.
        """
        # Subquery for active task counts per employee
        active_task_stmt = (
            select(
                User.id.label("user_id"),
                func.count(Task.id).label("active_task_count"),
            )
            .outerjoin(
                Task,
                and_(
                    Task.assigned_employee_id == User.id,
                    Task.status.in_(["PENDING", "IN_PROGRESS"]),
                ),
            )
            .where(User.role == role.upper())
            .where(User.is_active == True)
            .group_by(User.id)
            .order_by(func.count(Task.id).asc(), User.created_at.asc())
        )

        res = await db.execute(active_task_stmt)
        first_row = res.first()
        if not first_row:
            logger.warning(f"No active employees found for role '{role}'")
            return None

        best_user_id = first_row.user_id
        user_stmt = select(User).where(User.id == best_user_id)
        user_res = await db.execute(user_stmt)
        return user_res.scalar_one_or_none()

    @staticmethod
    async def spawn_packaging_task(
        db: AsyncSession, order_id: uuid.UUID, actor_id: Optional[uuid.UUID] = None
    ) -> Task:
        """
        Idempotently spawns and allocates a PACKAGING task for an order.
        """
        # Check if active packaging task already exists
        existing_stmt = (
            select(Task)
            .where(Task.order_id == order_id)
            .where(Task.task_type == "PACKAGING")
            .where(Task.status.in_(["PENDING", "IN_PROGRESS"]))
        )
        existing = (await db.execute(existing_stmt)).scalar_one_or_none()
        if existing:
            return existing

        assignee = await TaskService.find_least_loaded_employee(db, role="PACKAGING")
        new_task = Task(
            order_id=order_id,
            assigned_employee_id=assignee.id if assignee else None,
            task_type="PACKAGING",
            status="PENDING",
        )
        db.add(new_task)
        await db.flush()

        # Record audit and timeline
        assignee_name = assignee.full_name if assignee else "Unassigned (Queue)"
        ev = OrderEvent(
            order_id=order_id,
            from_status="PACKAGING",
            to_status="PACKAGING",
            event_type="TASK_SPAWNED",
            description=f"Packaging task spawned and assigned to {assignee_name}",
            actor_id=actor_id,
        )
        db.add(ev)

        audit = AuditLog(
            actor_id=actor_id,
            action="CREATE",
            entity_name="tasks",
            entity_id=new_task.id,
            change_diff={
                "task_type": "PACKAGING",
                "assigned_to": str(assignee.id) if assignee else None,
            },
        )
        db.add(audit)

        await db.commit()
        await db.refresh(new_task)
        logger.info(f"Spawned PACKAGING task {new_task.id} for order {order_id} -> {assignee_name}")
        return new_task

    @staticmethod
    async def spawn_delivery_task(
        db: AsyncSession, order_id: uuid.UUID, actor_id: Optional[uuid.UUID] = None
    ) -> Task:
        """
        Idempotently spawns and allocates a DELIVERY task for a packed order.
        """
        existing_stmt = (
            select(Task)
            .where(Task.order_id == order_id)
            .where(Task.task_type == "DELIVERY")
            .where(Task.status.in_(["PENDING", "IN_PROGRESS"]))
        )
        existing = (await db.execute(existing_stmt)).scalar_one_or_none()
        if existing:
            return existing

        assignee = await TaskService.find_least_loaded_employee(db, role="DELIVERY")
        new_task = Task(
            order_id=order_id,
            assigned_employee_id=assignee.id if assignee else None,
            task_type="DELIVERY",
            status="PENDING",
        )
        db.add(new_task)
        await db.flush()

        assignee_name = assignee.full_name if assignee else "Unassigned (Queue)"
        ev = OrderEvent(
            order_id=order_id,
            from_status="PACKED",
            to_status="PACKED",
            event_type="TASK_SPAWNED",
            description=f"Delivery task spawned and assigned to {assignee_name}",
            actor_id=actor_id,
        )

        db.add(ev)

        audit = AuditLog(
            actor_id=actor_id,
            action="CREATE",
            entity_name="tasks",
            entity_id=new_task.id,
            change_diff={
                "task_type": "DELIVERY",
                "assigned_to": str(assignee.id) if assignee else None,
            },
        )
        db.add(audit)

        await db.commit()
        await db.refresh(new_task)
        logger.info(f"Spawned DELIVERY task {new_task.id} for order {order_id} -> {assignee_name}")
        return new_task

    @staticmethod
    async def get_task_by_id(db: AsyncSession, task_id: uuid.UUID) -> Optional[Task]:
        stmt = (
            select(Task)
            .options(
                selectinload(Task.order).selectinload(Order.customer),
                selectinload(Task.order).selectinload(Order.items).selectinload(OrderItem.product),
                selectinload(Task.assigned_employee),
            )
            .where(Task.id == task_id)
        )
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def get_task_with_order(
        db: AsyncSession, task_id: uuid.UUID
    ) -> Optional[TaskWithOrderResponse]:
        task = await TaskService.get_task_by_id(db, task_id)
        if not task:
            return None
        return TaskService._to_task_with_order_response(task)

    @staticmethod
    async def update_task_status(
        db: AsyncSession,
        task_id: uuid.UUID,
        data: UpdateTaskStatusRequest,
        actor: User,
    ) -> TaskWithOrderResponse:
        """
        Updates task status with validation and triggers automatic downstream stage progression.
        """
        task = await TaskService.get_task_by_id(db, task_id)
        if not task:
            raise NotFoundException(f"Task with ID '{task_id}' not found")

        # Authorization check: Operators can only update tasks assigned to themselves; Admins can update any
        if actor.role != "ADMIN" and task.assigned_employee_id != actor.id:
            raise ForbiddenException("You are not authorized to update tasks assigned to another employee.")

        current_status = task.status
        target_status = data.new_status

        # Idempotency check
        if current_status == target_status:
            return TaskService._to_task_with_order_response(task)

        allowed = ALLOWED_TASK_TRANSITIONS.get(current_status, set())
        if target_status not in allowed:
            raise StateTransitionException(
                f"Illegal task transition from '{current_status}' to '{target_status}'. Allowed: {sorted(list(allowed))}"
            )

        if target_status == "EXCEPTION":
            if not data.exception_notes or not data.exception_notes.strip():
                raise ValidationException("Exception notes are required when reporting a task exception.")
            task.mark_exception(data.exception_notes.strip())
            ev = OrderEvent(
                order_id=task.order_id,
                event_type="EXCEPTION_RAISED",
                description=f"{task.task_type} task exception: {data.exception_notes.strip()}",
                actor_id=actor.id,
            )
            db.add(ev)
        elif target_status == "COMPLETED":
            task.mark_completed()
        else:
            task.status = target_status

        audit = AuditLog(
            actor_id=actor.id,
            action="UPDATE",
            entity_name="tasks",
            entity_id=task.id,
            change_diff={
                "status": {"old": current_status, "new": target_status},
                "notes": data.exception_notes,
            },
        )
        db.add(audit)

        await db.commit()
        await db.refresh(task)

        # ==========================================
        # AUTOMATIC DOWNSTREAM ORDER STAGE ADVANCEMENT
        # ==========================================
        from app.services.order_service import OrderService

        if task.task_type == "DELIVERY" and target_status == "IN_PROGRESS":
            try:
                # If order is PACKED, move it to OUT_FOR_DELIVERY
                order_check_stmt = select(Order).where(Order.id == task.order_id)
                order_res = (await db.execute(order_check_stmt)).scalar_one_or_none()
                if order_res and order_res.status == "PACKED":
                    await OrderService.update_order_status(
                        db,
                        order_id=task.order_id,
                        data=UpdateOrderStatusRequest(
                            new_status="OUT_FOR_DELIVERY",
                            reason=f"Delivery task {task.id} started by {actor.full_name}",
                        ),
                        actor_id=actor.id,
                    )
            except Exception as e:
                logger.error(f"Failed to auto-advance order {task.order_id} to OUT_FOR_DELIVERY: {e}")

        elif target_status == "COMPLETED":
            if task.task_type == "PACKAGING":
                # Advance order: PACKAGING -> PACKED (which triggers DELIVERY task auto-spawning!)
                try:
                    await OrderService.update_order_status(
                        db,
                        order_id=task.order_id,
                        data=UpdateOrderStatusRequest(
                            new_status="PACKED",
                            reason=f"Packaging task {task.id} completed by {actor.full_name}",
                        ),
                        actor_id=actor.id,
                    )
                    # Automatically spawn the downstream delivery task
                    await TaskService.spawn_delivery_task(db, order_id=task.order_id, actor_id=actor.id)
                except Exception as e:
                    logger.error(f"Failed to auto-advance order {task.order_id} to PACKED: {e}")

            elif task.task_type == "DELIVERY":
                # Advance order: OUT_FOR_DELIVERY -> DELIVERED (triggers idempotent stock deduction!)
                try:
                    order_check_stmt = select(Order).where(Order.id == task.order_id)
                    order_res = (await db.execute(order_check_stmt)).scalar_one_or_none()
                    if order_res and order_res.status == "PACKED":
                        await OrderService.update_order_status(
                            db,
                            order_id=task.order_id,
                            data=UpdateOrderStatusRequest(
                                new_status="OUT_FOR_DELIVERY",
                                reason=f"Delivery task {task.id} in transit",
                            ),
                            actor_id=actor.id,
                        )
                    await OrderService.update_order_status(
                        db,
                        order_id=task.order_id,
                        data=UpdateOrderStatusRequest(
                            new_status="DELIVERED",
                            reason=f"Delivery completed by {actor.full_name}",
                        ),
                        actor_id=actor.id,
                    )
                except Exception as e:
                    logger.error(f"Failed to auto-advance order {task.order_id} to DELIVERED: {e}")

        refreshed_task = await TaskService.get_task_by_id(db, task.id)
        return TaskService._to_task_with_order_response(refreshed_task)  # type: ignore

    @staticmethod
    async def reassign_task(
        db: AsyncSession,
        task_id: uuid.UUID,
        data: ReassignTaskRequest,
        actor_id: Optional[uuid.UUID] = None,
    ) -> TaskWithOrderResponse:
        """
        Manually reassigns a task to another active employee of matching role. Requires ADMIN role.
        """
        task = await TaskService.get_task_by_id(db, task_id)
        if not task:
            raise NotFoundException(f"Task with ID '{task_id}' not found")

        target_user_stmt = select(User).where(User.id == data.assigned_employee_id)
        target_user = (await db.execute(target_user_stmt)).scalar_one_or_none()
        if not target_user:
            raise NotFoundException(f"Target employee with ID '{data.assigned_employee_id}' not found")

        if not target_user.is_active:
            raise ValidationException("Cannot assign task to a deactivated employee.")

        if target_user.role != task.task_type:
            raise ValidationException(
                f"Role mismatch: Cannot assign '{task.task_type}' task to employee with role '{target_user.role}'"
            )

        old_assignee_id = task.assigned_employee_id
        task.assigned_employee_id = target_user.id

        ev = OrderEvent(
            order_id=task.order_id,
            event_type="TASK_REASSIGNED",
            description=f"{task.task_type} task reassigned to {target_user.full_name}",
            actor_id=actor_id,
        )
        db.add(ev)

        audit = AuditLog(
            actor_id=actor_id,
            action="UPDATE",
            entity_name="tasks",
            entity_id=task.id,
            change_diff={
                "assigned_employee_id": {
                    "old": str(old_assignee_id) if old_assignee_id else None,
                    "new": str(target_user.id),
                }
            },
        )
        db.add(audit)

        await db.commit()
        refreshed = await TaskService.get_task_by_id(db, task.id)
        return TaskService._to_task_with_order_response(refreshed)  # type: ignore

    @staticmethod
    async def list_operator_tasks(
        db: AsyncSession,
        employee_id: uuid.UUID,
        status_filter: Optional[str] = None,
        task_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[TaskWithOrderResponse], int]:
        query = (
            select(Task)
            .options(
                selectinload(Task.order).selectinload(Order.customer),
                selectinload(Task.order).selectinload(Order.items).selectinload(OrderItem.product),
                selectinload(Task.assigned_employee),
            )
            .where(Task.assigned_employee_id == employee_id)
        )
        count_query = select(func.count(Task.id)).where(Task.assigned_employee_id == employee_id)

        if status_filter:
            query = query.where(Task.status == status_filter.upper().strip())
            count_query = count_query.where(Task.status == status_filter.upper().strip())

        if task_type:
            query = query.where(Task.task_type == task_type.upper().strip())
            count_query = count_query.where(Task.task_type == task_type.upper().strip())

        total_res = await db.execute(count_query)
        total = total_res.scalar() or 0

        query = query.order_by(Task.created_at.desc()).offset(skip).limit(limit)
        res = await db.execute(query)
        tasks = res.scalars().all()

        return [TaskService._to_task_with_order_response(t) for t in tasks], total

    @staticmethod
    async def list_all_tasks(
        db: AsyncSession,
        task_type: Optional[str] = None,
        status_filter: Optional[str] = None,
        employee_id: Optional[uuid.UUID] = None,
        order_id: Optional[uuid.UUID] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[TaskResponse], int]:
        query = (
            select(Task)
            .options(
                selectinload(Task.order),
                selectinload(Task.assigned_employee),
            )
        )
        count_query = select(func.count(Task.id))

        if task_type:
            query = query.where(Task.task_type == task_type.upper().strip())
            count_query = count_query.where(Task.task_type == task_type.upper().strip())

        if status_filter:
            query = query.where(Task.status == status_filter.upper().strip())
            count_query = count_query.where(Task.status == status_filter.upper().strip())

        if employee_id:
            query = query.where(Task.assigned_employee_id == employee_id)
            count_query = count_query.where(Task.assigned_employee_id == employee_id)

        if order_id:
            query = query.where(Task.order_id == order_id)
            count_query = count_query.where(Task.order_id == order_id)

        total_res = await db.execute(count_query)
        total = total_res.scalar() or 0

        query = query.order_by(Task.created_at.desc()).offset(skip).limit(limit)
        res = await db.execute(query)
        tasks = res.scalars().all()

        return [TaskService._to_task_response(t) for t in tasks], total

    @staticmethod
    async def get_employee_workload_metrics(
        db: AsyncSession,
    ) -> List[EmployeeWorkloadMetric]:
        """
        Calculates live active vs. completed task workload counts across all warehouse staff.
        """
        users_stmt = (
            select(User)
            .where(User.role.in_(["PACKAGING", "DELIVERY"]))
            .order_by(User.role.asc(), User.full_name.asc())
        )
        users_res = await db.execute(users_stmt)
        users = users_res.scalars().all()

        metrics: List[EmployeeWorkloadMetric] = []
        for u in users:
            active_stmt = select(func.count(Task.id)).where(
                Task.assigned_employee_id == u.id,
                Task.status.in_(["PENDING", "IN_PROGRESS"]),
            )
            completed_stmt = select(func.count(Task.id)).where(
                Task.assigned_employee_id == u.id,
                Task.status == "COMPLETED",
            )

            active_cnt = (await db.execute(active_stmt)).scalar() or 0
            completed_cnt = (await db.execute(completed_stmt)).scalar() or 0

            metrics.append(
                EmployeeWorkloadMetric(
                    employee_id=u.id,
                    email=u.email,
                    full_name=u.full_name,
                    role=u.role,
                    is_active=u.is_active,
                    active_tasks=active_cnt,
                    completed_tasks=completed_cnt,
                )
            )

        return metrics

    @staticmethod
    def _to_task_response(task: Task) -> TaskResponse:
        return TaskResponse(
            id=task.id,
            order_id=task.order_id,
            order_number=task.order.order_number if task.order else None,
            assigned_employee_id=task.assigned_employee_id,
            assigned_employee_name=task.assigned_employee.full_name if task.assigned_employee else None,
            task_type=task.task_type,
            status=task.status,
            exception_notes=task.exception_notes,
            created_at=task.created_at,
            completed_at=task.completed_at,
        )

    @staticmethod
    def _to_task_with_order_response(task: Task) -> TaskWithOrderResponse:
        items_dtos = []
        if task.order and task.order.items:
            for item in task.order.items:
                items_dtos.append(
                    OrderItemResponse(
                        id=item.id,
                        order_id=item.order_id,
                        product_id=item.product_id,
                        quantity=item.quantity,
                        unit_price=item.unit_price,
                        total_price=item.total_price,
                        product_sku=item.product.sku if item.product else None,
                        product_name=item.product.name if item.product else None,
                    )
                )

        return TaskWithOrderResponse(
            id=task.id,
            order_id=task.order_id,
            order_number=task.order.order_number if task.order else "",
            order_status=task.order.status if task.order else "",
            task_type=task.task_type,
            status=task.status,
            assigned_employee_id=task.assigned_employee_id,
            assigned_employee_name=task.assigned_employee.full_name if task.assigned_employee else None,
            customer_name=task.order.customer.full_name if task.order and task.order.customer else None,
            customer_email=task.order.customer.email if task.order and task.order.customer else None,
            delivery_address=task.order.delivery_address if task.order else "",
            items=items_dtos,
            exception_notes=task.exception_notes,
            created_at=task.created_at,
            completed_at=task.completed_at,
        )
