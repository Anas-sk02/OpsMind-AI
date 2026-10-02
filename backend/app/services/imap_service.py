import re
import uuid
import email
import imaplib
import logging
import asyncio
from email.header import decode_header
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.schemas.email_webhook import InboundEmailWebhookRequest
from app.services.email_service import EmailService

logger = logging.getLogger("opsmind.imap_service")


def _decode_mime_header(header_val: Optional[str]) -> str:
    """
    Safely decodes encoded MIME headers (e.g. UTF-8, ISO-8859-1 encoded subjects).
    """
    if not header_val:
        return ""
    decoded_parts = []
    for text, enc in decode_header(header_val):
        if isinstance(text, bytes):
            try:
                decoded_parts.append(text.decode(enc or "utf-8", errors="replace"))
            except Exception:
                decoded_parts.append(text.decode("latin1", errors="replace"))
        else:
            decoded_parts.append(str(text))
    return "".join(decoded_parts).strip()


class ImapService:
    """
    Direct Mailbox IMAP Poller Service.
    Connects securely to Gmail or any standard IMAP inbox to fetch UNSEEN order emails,
    feeds them into the AI extraction pipeline, and marks them as READ.
    """

    @staticmethod
    def _fetch_unseen_emails_sync() -> List[Dict[str, Any]]:
        """
        Synchronous IMAP worker that connects to mailbox over SSL and extracts unread messages.
        Executed in an asynchronous worker thread to prevent event loop blocking.
        """
        imap_user = settings.IMAP_USER or settings.SMTP_USER
        imap_password = settings.IMAP_PASSWORD or settings.SMTP_PASSWORD

        if not settings.IMAP_HOST or not imap_user or not imap_password:
            logger.debug("[IMAP Poller] Skipped: IMAP credentials not configured in environment.")
            return []

        from datetime import datetime, timezone, timedelta
        pwd = imap_password.replace(" ", "").strip()
        port = settings.IMAP_PORT or 993
        extracted_emails: List[Dict[str, Any]] = []

        # Known automated notification / marketing sender patterns to bypass
        AUTOMATED_SENDER_PATTERNS = [
            "noreply", "no-reply", "marketing", "newsletter", "linkedin.com", "engage.canva.com",
            "notifications@", "promotions@", "accounts.google.com", "accountprotection.microsoft.com",
            "mailer-daemon", "updates.", "mail.cursor.com", "security@", "digest@", "invite@",
            "news@", "billing@", "donotreply", "no_reply"
        ]

        try:
            with imaplib.IMAP4_SSL(settings.IMAP_HOST, port) as client:
                client.login(imap_user, pwd)
                client.select("INBOX")

                # 1. Search with 24h SINCE filter to prevent scanning hundreds of historical unread emails
                since_date = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%d-%b-%Y")
                status, data = client.search(None, "UNSEEN", "SINCE", since_date)
                
                # Fallback to standard UNSEEN if SINCE returns nothing
                if status != "OK" or not data or not data[0]:
                    status, data = client.search(None, "UNSEEN")

                if status != "OK" or not data or not data[0]:
                    return []

                raw_nums = data[0].split()
                # Take only the latest 10 unread emails per polling cycle to avoid batch overloading
                msg_nums = raw_nums[-10:] if len(raw_nums) > 10 else raw_nums
                logger.info(f"[IMAP Poller] Found {len(raw_nums)} UNSEEN email(s) (Processing latest {len(msg_nums)}).")

                for num in msg_nums:
                    try:
                        res, msg_data = client.fetch(num, "(RFC822)")
                        if res != "OK" or not msg_data:
                            continue

                        raw_email_bytes = msg_data[0][1]
                        msg = email.message_from_bytes(raw_email_bytes)

                        # Extract Message-ID
                        raw_msg_id = msg.get("Message-ID") or msg.get("Message-Id")
                        if raw_msg_id:
                            clean_msg_id = raw_msg_id.strip("<> \t\n\r")
                        else:
                            clean_msg_id = f"imap_{uuid.uuid4().hex[:12]}@opsmind.io"

                        # Extract Subject
                        subject = _decode_mime_header(msg.get("Subject", "Order Request"))

                        # Extract From
                        raw_from = _decode_mime_header(msg.get("From", ""))
                        sender_email = imap_user
                        sender_name: Optional[str] = None

                        match = re.search(r"^(.*?)\s*<([^>]+)>$", raw_from)
                        if match:
                            sender_name = match.group(1).strip().strip('"').strip("'") or None
                            sender_email = match.group(2).strip()
                        else:
                            em_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", raw_from)
                            if em_match:
                                sender_email = em_match.group(0)

                        # Mark as read/seen on server immediately so it is not re-processed
                        client.store(num, "+FLAGS", "\\Seen")

                        # Skip known automated bots & marketing senders
                        sender_lower = sender_email.lower()
                        if any(pattern in sender_lower for pattern in AUTOMATED_SENDER_PATTERNS):
                            logger.info(f"[IMAP Poller] Skipped automated marketing/notification sender: {sender_email}")
                            continue

                        # Extract Body
                        body_plain = ""
                        body_html: Optional[str] = None

                        if msg.is_multipart():
                            for part in msg.walk():
                                content_type = part.get_content_type()
                                content_disp = str(part.get("Content-Disposition", ""))

                                if "attachment" in content_disp.lower():
                                    continue

                                charset = part.get_content_charset() or "utf-8"
                                payload = part.get_payload(decode=True)
                                if payload:
                                    try:
                                        decoded_text = payload.decode(charset, errors="replace")
                                    except Exception:
                                        decoded_text = payload.decode("latin1", errors="replace")

                                    if content_type == "text/plain" and not body_plain:
                                        body_plain = decoded_text
                                    elif content_type == "text/html" and not body_html:
                                        body_html = decoded_text
                        else:
                            charset = msg.get_content_charset() or "utf-8"
                            payload = msg.get_payload(decode=True)
                            if payload:
                                try:
                                    body_plain = payload.decode(charset, errors="replace")
                                except Exception:
                                    body_plain = payload.decode("latin1", errors="replace")

                        if not body_plain and body_html:
                            # Fallback: strip tags
                            body_plain = re.sub(r"<[^>]+>", " ", body_html).strip()

                        if not body_plain:
                            body_plain = subject or "Inbound customer inquiry"

                        extracted_emails.append({
                            "message_id": clean_msg_id,
                            "sender_email": sender_email,
                            "sender_name": sender_name,
                            "recipient_email": imap_user,
                            "subject": subject,
                            "body_plain": body_plain,
                            "body_html": body_html,
                            "imap_num": num,
                        })

                    except Exception as msg_ex:
                        logger.error(f"[IMAP Poller] Failed to parse message {num}: {msg_ex}")

        except Exception as ex:
            logger.error(f"[IMAP Poller] Connection error to {settings.IMAP_HOST}:{port}: {ex}")

        return extracted_emails

    @staticmethod
    async def poll_and_process_mailbox(db: AsyncSession) -> Dict[str, Any]:
        """
        Polls mailbox once and synchronously processes all newly extracted unread emails.
        """
        raw_emails = await asyncio.to_thread(ImapService._fetch_unseen_emails_sync)
        if not raw_emails:
            return {
                "polled": True,
                "count": 0,
                "message": "No new unread emails found in mailbox.",
                "processed_orders": [],
            }

        processed_orders = []
        for em in raw_emails:
            try:
                req = InboundEmailWebhookRequest(
                    message_id=em["message_id"],
                    sender_email=em["sender_email"],
                    sender_name=em["sender_name"],
                    recipient_email=em["recipient_email"],
                    subject=em["subject"],
                    body_plain=em["body_plain"],
                    body_html=em["body_html"],
                )
                res = await EmailService.ingest_inbound_email(db, req, synchronous=True)
                processed_orders.append({
                    "message_id": res.message_id,
                    "order_number": res.order_number,
                    "status": res.status,
                    "customer_email": res.customer_email,
                })
                logger.info(f"[IMAP Poller] Successfully ingested email {res.message_id} -> Order {res.order_number} ({res.status})")
            except Exception as in_ex:
                logger.error(f"[IMAP Poller] Ingestion error for message {em.get('message_id')}: {in_ex}")

        return {
            "polled": True,
            "count": len(processed_orders),
            "message": f"Successfully ingested {len(processed_orders)} new email(s).",
            "processed_orders": processed_orders,
        }

    @staticmethod
    async def run_poller_background_loop(get_db_session):
        """
        Asynchronous continuous background worker running during FastAPI lifespan.
        Polls mailbox every IMAP_POLL_INTERVAL_SECONDS.
        """
        interval = max(10, settings.IMAP_POLL_INTERVAL_SECONDS)
        logger.info(f"[IMAP Poller] Background mailbox poller started (Interval: {interval}s).")

        while True:
            try:
                await asyncio.sleep(interval)
                async with get_db_session() as db:
                    await ImapService.poll_and_process_mailbox(db)
            except asyncio.CancelledError:
                logger.info("[IMAP Poller] Background poller gracefully cancelled.")
                break
            except Exception as ex:
                logger.warning(f"[IMAP Poller] Loop error (will retry in {interval}s): {ex}")
