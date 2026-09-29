import uuid
import logging
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import require_admin
from app.models.user import User
from app.models.email_message import EmailMessage
from app.core.exceptions import NotFoundException
from app.schemas.common import ApiResponse, PaginatedResponse
from app.schemas.email_webhook import EmailMessageResponse
from app.services.email_service import EmailService

logger = logging.getLogger("opsmind.api.admin_emails")
router = APIRouter(prefix="/admin/emails", tags=["Admin Email Audit"])


@router.get(
    "",
    response_model=PaginatedResponse[EmailMessageResponse],
    status_code=status.HTTP_200_OK,
    summary="List all inbound and outbound email interactions with pagination and filters",
)
async def list_email_logs(
    direction: Optional[str] = Query(None, description="Filter by direction: INBOUND | OUTBOUND"),
    customer_id: Optional[uuid.UUID] = Query(None, description="Filter by customer UUID"),
    order_id: Optional[uuid.UUID] = Query(None, description="Filter by linked order UUID"),
    search: Optional[str] = Query(None, description="Search by email, subject, or message ID"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    skip = (page - 1) * page_size
    items, total = await EmailService.list_email_logs(
        db=db,
        direction=direction,
        customer_id=customer_id,
        order_id=order_id,
        search=search,
        skip=skip,
        limit=page_size,
    )

    return PaginatedResponse.create(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{id}",
    response_model=ApiResponse[EmailMessageResponse],
    status_code=status.HTTP_200_OK,
    summary="Get single email interaction by ID including AI extraction metadata",
)
async def get_email_log(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    stmt = (
        select(EmailMessage)
        .options(
            selectinload(EmailMessage.customer),
            selectinload(EmailMessage.order),
        )
        .where(EmailMessage.id == id)
    )
    email_msg = (await db.execute(stmt)).scalar_one_or_none()
    if not email_msg:
        raise NotFoundException(f"Email interaction with ID '{id}' not found")

    dto = EmailMessageResponse(
        id=email_msg.id,
        message_id=email_msg.message_id,
        customer_id=email_msg.customer_id,
        customer_name=email_msg.customer.name if email_msg.customer else None,
        order_id=email_msg.order_id,
        order_number=email_msg.order.order_number if email_msg.order else None,
        direction=email_msg.direction,
        sender_email=email_msg.sender_email,
        recipient_email=email_msg.recipient_email,
        subject=email_msg.subject,
        body_plain=email_msg.body_plain,
        body_html=email_msg.body_html,
        detected_language=email_msg.detected_language,
        ai_extraction_payload=email_msg.ai_extraction_payload,
        created_at=email_msg.created_at,
    )
    return ApiResponse.ok(data=dto)
