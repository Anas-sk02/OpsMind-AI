import re
import uuid
import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, Header, Query, Form, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import AuthenticationException, ValidationException
from app.schemas.common import ApiResponse
from app.schemas.email_webhook import (
    InboundEmailWebhookRequest,
    InboundEmailWebhookResponse,
)
from app.services.email_service import EmailService

logger = logging.getLogger("opsmind.api.webhooks")
router = APIRouter(prefix="/webhooks", tags=["Inbound Email Webhooks"])


class TestSmtpRequest(BaseModel):
    recipient_email: EmailStr


@router.post(
    "/email/inbound",
    response_model=ApiResponse[InboundEmailWebhookResponse],
    status_code=status.HTTP_200_OK,
    summary="Ingest inbound customer email via JSON webhook",
)
async def ingest_inbound_email(
    payload: InboundEmailWebhookRequest,
    sync: bool = Query(True, description="Process synchronously and return order details"),
    x_webhook_secret: Optional[str] = Header(None, description="Optional webhook HMAC / secret header"),
    db: AsyncSession = Depends(get_db),
):
    """
    Inbound email ingestion endpoint compatible with JSON webhooks (Resend, Mailgun, Postmark, AWS SES, or direct HTTP).
    - Idempotently verifies message_id against duplicate ingestion.
    - Runs AI multilingual extraction & catalog entity resolution.
    - Auto-creates or resolves customer profile.
    - Progresses order through state machine, automatically reserving stock and dispatching packaging task.
    - Dispatches fact-grounded confirmation/review notification.
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


@router.post(
    "/email/sendgrid",
    response_model=ApiResponse[InboundEmailWebhookResponse],
    status_code=status.HTTP_200_OK,
    summary="Ingest inbound customer email via SendGrid Inbound Parse (multipart/form-data)",
)
async def ingest_sendgrid_email(
    request: Request,
    headers: Optional[str] = Form(None),
    envelope: Optional[str] = Form(None),
    subject: Optional[str] = Form(None),
    text: Optional[str] = Form(None),
    html: Optional[str] = Form(None),
    from_field: Optional[str] = Form(None, alias="from"),
    to_field: Optional[str] = Form(None, alias="to"),
    db: AsyncSession = Depends(get_db),
):
    """
    Direct SendGrid Inbound Parse webhook handler that parses multipart form-data.
    Automatically extracts sender name, sender email, subject, text, HTML, and Message-ID.
    """
    raw_from = from_field or "customer@example.com"
    raw_subject = (subject or "Order Request").strip()
    raw_body = (text or html or "Order inquiry").strip()

    # Extract email and display name from "First Last <email@example.com>"
    sender_email = raw_from
    sender_name: Optional[str] = None

    match = re.search(r"^(.*?)\s*<([^>]+)>$", raw_from)
    if match:
        sender_name = match.group(1).strip().strip('"').strip("'") or None
        sender_email = match.group(2).strip()
    else:
        email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", raw_from)
        if email_match:
            sender_email = email_match.group(0)

    # Extract Message-ID from headers if available
    msg_id = f"sendgrid_{uuid.uuid4().hex[:12]}@opsmind.io"
    if headers:
        id_match = re.search(r"(?:Message-ID|Message-Id):\s*<([^>]+)>", headers, re.IGNORECASE)
        if id_match:
            msg_id = id_match.group(1).strip()

    payload = InboundEmailWebhookRequest(
        message_id=msg_id,
        sender_email=sender_email,
        sender_name=sender_name,
        recipient_email=to_field or "orders@opsmind.io",
        subject=raw_subject,
        body_plain=raw_body,
        body_html=html,
    )

    result = await EmailService.ingest_inbound_email(
        db=db,
        data=payload,
        synchronous=True,
    )

    return ApiResponse.ok(
        data=result,
        message="SendGrid inbound email processed successfully",
    )


@router.post(
    "/email/test-smtp",
    response_model=ApiResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Send a test verification email via configured SMTP",
)
async def test_smtp_endpoint(
    req: TestSmtpRequest,
):
    """
    Diagnostics endpoint to test real outbound SMTP configuration (e.g. Gmail App Password, SendGrid, Amazon SES).
    """
    result = await EmailService.test_smtp_connection(req.recipient_email)
    if not result.get("success") and result.get("configured"):
        return ApiResponse.error(
            message=result.get("message", "SMTP test failed"),
            data=result,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return ApiResponse.ok(
        data=result,
        message=result.get("message", "SMTP check completed"),
    )

