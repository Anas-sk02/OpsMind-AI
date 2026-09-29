import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, EmailStr, ConfigDict


class InboundEmailWebhookRequest(BaseModel):
    """
    Standardized inbound email webhook payload.
    Compatible with SendGrid Inbound Parse, Mailgun, Postmark, AWS SES, or direct JSON simulation.
    """
    model_config = ConfigDict(extra="ignore")

    message_id: str = Field(..., min_length=3, max_length=255, description="Unique Message-ID header of the email")
    sender_email: EmailStr = Field(..., description="Customer sender email address")
    sender_name: Optional[str] = Field(None, max_length=255, description="Sender display name if present")
    recipient_email: Optional[str] = Field("orders@opsmind.io", max_length=255, description="Inbound recipient mailbox")
    subject: str = Field(..., min_length=1, max_length=500, description="Email subject line")
    body_plain: str = Field(..., min_length=1, description="Raw plain text body of the email")
    body_html: Optional[str] = Field(None, description="HTML formatted body if present")
    timestamp: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when email was sent or received"
    )
    raw_payload: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Raw webhook provider JSON or headers for audit retention"
    )


class InboundEmailWebhookResponse(BaseModel):
    """
    Response returned to webhook caller or client after email ingestion and processing.
    """
    model_config = ConfigDict(from_attributes=True)

    email_id: uuid.UUID
    message_id: str
    status: str = Field(..., description="PROCESSED | QUEUED | DUPLICATE | NEEDS_REVIEW | FAILED")
    order_id: Optional[uuid.UUID] = None
    order_number: Optional[str] = None
    order_status: Optional[str] = None
    customer_id: Optional[uuid.UUID] = None
    customer_email: Optional[str] = None
    detected_language: Optional[str] = None
    is_order_intent: Optional[bool] = None
    needs_human_review: Optional[bool] = None
    review_reasons: List[str] = Field(default_factory=list)
    outbound_email_id: Optional[uuid.UUID] = None
    message: str


class EmailMessageResponse(BaseModel):
    """
    Complete audit log representation of an inbound or outbound email interaction.
    """
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    message_id: str
    customer_id: Optional[uuid.UUID] = None
    customer_name: Optional[str] = None
    order_id: Optional[uuid.UUID] = None
    order_number: Optional[str] = None
    direction: str  # "INBOUND" | "OUTBOUND"
    sender_email: str
    recipient_email: str
    subject: str
    body_plain: str
    body_html: Optional[str] = None
    detected_language: Optional[str] = None
    ai_extraction_payload: Optional[Dict[str, Any]] = None
    created_at: datetime
