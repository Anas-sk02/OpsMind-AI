"""
Celery tasks for OpsMind AI background processing.
"""
import logging
import asyncio
from typing import Dict, Any, Optional
from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_factory
from app.services.imap_service import ImapService
from app.services.email_service import EmailService
from app.services.ai_service import AIService
from app.schemas.email_webhook import InboundEmailWebhookRequest

logger = logging.getLogger("opsmind.workers.tasks")


def _get_db_session() -> AsyncSession:
    """Create a new database session for the task."""
    return async_session_factory()


# ============================================================
# IMAP Mailbox Polling Task
# ============================================================

@shared_task(
    bind=True,
    name="app.workers.tasks.poll_mailbox_task",
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def poll_mailbox_task(self) -> Dict[str, Any]:
    """
    Periodic task to poll IMAP mailbox for new emails.
    Runs every 30 seconds via Celery Beat.
    """
    logger.info("[Celery] Starting mailbox poll task")

    async def _poll():
        async with _get_db_session() as db:
            return await ImapService.poll_and_process_mailbox(db)

    try:
        result = asyncio.run(_poll())
        logger.info(f"[Celery] Mailbox poll completed: {result}")
        return result
    except Exception as exc:
        logger.error(f"[Celery] Mailbox poll failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    name="app.workers.tasks.process_single_email_task",
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
)
def process_single_email_task(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a single inbound email through the full pipeline.
    Can be called directly (e.g., from webhook) or by poll_mailbox_task.
    """
    logger.info(f"[Celery] Processing email: {email_data.get('message_id')}")

    async def _process():
        async with _get_db_session() as db:
            req = InboundEmailWebhookRequest(**email_data)
            return await EmailService.ingest_inbound_email(db, req, synchronous=True)

    try:
        result = asyncio.run(_process())
        return {
            "status": result.status,
            "order_id": str(result.order_id) if result.order_id else None,
            "order_number": result.order_number,
            "message": result.message,
        }
    except Exception as exc:
        logger.error(f"[Celery] Email processing failed: {exc}")
        raise self.retry(exc=exc)


# ============================================================
# SMTP Dispatch Task
# ============================================================

@shared_task(
    bind=True,
    name="app.workers.tasks.dispatch_smtp_email_task",
    max_retries=5,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def dispatch_smtp_email_task(
    self,
    to_email: str,
    subject: str,
    body_plain: str,
    body_html: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Send transactional email via SMTP with automatic retry.
    Fire-and-forget from API perspective.
    """
    logger.info(f"[Celery] Dispatching SMTP email to {to_email}")

    async def _send():
        return await EmailService._dispatch_real_smtp_email(
            to_email=to_email,
            subject=subject,
            body_plain=body_plain,
            body_html=body_html,
        )

    try:
        delivered = asyncio.run(_send())
        return {"delivered": delivered, "recipient": to_email}
    except Exception as exc:
        logger.error(f"[Celery] SMTP dispatch failed for {to_email}: {exc}")
        raise self.retry(exc=exc)


# ============================================================
# AI Extraction Task (for high-volume async processing)
# ============================================================

@shared_task(
    bind=True,
    name="app.workers.tasks.extract_order_task",
    max_retries=2,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
)
def extract_order_task(
    self,
    subject: str,
    body: str,
    sender_email: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run AI extraction as a background task.
    Useful for batch processing or when webhook needs fast response.
    """
    logger.info(f"[Celery] Running AI extraction for email from {sender_email}")

    async def _extract():
        async with _get_db_session() as db:
            extraction, exec_ms, model_name = await AIService.extract_order_from_email(
                subject=subject,
                body=body,
                sender_email=sender_email,
                db=db,
            )
            return {
                "extraction": extraction.model_dump(mode="json"),
                "execution_time_ms": exec_ms,
                "model_name": model_name,
            }

    try:
        return asyncio.run(_extract())
    except Exception as exc:
        logger.error(f"[Celery] AI extraction failed: {exc}")
        raise self.retry(exc=exc)


# ============================================================
# Order Notification Task
# ============================================================

@shared_task(
    bind=True,
    name="app.workers.tasks.notify_customer_task",
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
)
def notify_customer_task(self, order_id: str, new_status: str) -> Dict[str, Any]:
    """
    Send customer notification email for order status change.
    Decoupled from order state transition.
    """
    import uuid
    logger.info(f"[Celery] Sending {new_status} notification for order {order_id}")

    async def _notify():
        async with _get_db_session() as db:
            outbound = await EmailService.notify_customer_order_status(
                db=db,
                order_id=uuid.UUID(order_id),
                new_status=new_status,
            )
            return {"sent": outbound is not None, "email_id": str(outbound.id) if outbound else None}

    try:
        return asyncio.run(_notify())
    except Exception as exc:
        logger.error(f"[Celery] Customer notification failed: {exc}")
        raise self.retry(exc=exc)