import logging
from typing import Optional
from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import AuthenticationException
from app.schemas.common import ApiResponse
from app.schemas.email_webhook import (
    InboundEmailWebhookRequest,
    InboundEmailWebhookResponse,
)
from app.services.email_service import EmailService

logger = logging.getLogger("opsmind.api.webhooks")
router = APIRouter(prefix="/webhooks", tags=["Inbound Email Webhooks"])


@router.post(
    "/email/inbound",
    response_model=ApiResponse[InboundEmailWebhookResponse],
    status_code=status.HTTP_200_OK,
    summary="Ingest inbound customer email via webhook",
)
async def ingest_inbound_email(
    payload: InboundEmailWebhookRequest,
    sync: bool = Query(True, description="Process synchronously and return order details"),
    x_webhook_secret: Optional[str] = Header(None, description="Optional webhook HMAC / secret header"),
    db: AsyncSession = Depends(get_db),
):
    """
    Inbound email ingestion endpoint compatible with SendGrid, Mailgun, Postmark, AWS SES, or direct HTTP.
    - Idempotently verifies message_id against duplicate ingestion.
    - Runs AI multilingual extraction & entity resolution.
    - Auto-creates or resolves customer profile.
    - Progresses order through state machine, automatically reserving stock and dispatching packaging task.
    - Synthesizes localized fact-grounded confirmation/review notification.
    """
    # Verify webhook secret in production if configured
    if (
        settings.ENVIRONMENT == "production"
        and settings.WEBHOOK_SECRET
        and settings.WEBHOOK_SECRET != "opsmind_webhook_secret_key"
    ):
        if x_webhook_secret != settings.WEBHOOK_SECRET:
            raise AuthenticationException("Invalid or missing X-Webhook-Secret header")

    result = await EmailService.ingest_inbound_email(
        db=db,
        data=payload,
        synchronous=sync,
    )

    return ApiResponse.ok(
        data=result,
        message=result.message,
    )
