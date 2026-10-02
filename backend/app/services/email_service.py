import uuid
import logging
import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Tuple, Dict, Any
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    NotFoundException,
    InsufficientStockException,
    StateTransitionException,
    ValidationException,
)
from app.models.customer import Customer
from app.models.product import Product
from app.models.inventory import Inventory
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.email_message import EmailMessage
from app.models.audit_log import OrderEvent, AuditLog
from app.schemas.email_webhook import (
    InboundEmailWebhookRequest,
    InboundEmailWebhookResponse,
    EmailMessageResponse,
)
from app.schemas.order import CreateOrderRequest, CreateOrderItemRequest, UpdateOrderStatusRequest
from app.schemas.ai_extraction import (
    OrderExtractionResult,
    OutboundSynthesisRequest,
)
from app.services.ai_service import AIService
from app.services.order_service import OrderService
from app.services.task_service import TaskService

logger = logging.getLogger("opsmind.email_service")


class EmailService:
    """
    Core Email Ingestion & Outbound Notification Engine.
    Handles webhook parsing, AI extraction orchestration, customer auto-resolution,
    order state initiation, stock checking, task triggering, and fact-grounded customer updates.
    """

    @staticmethod
    async def ingest_inbound_email(
        db: AsyncSession,
        data: InboundEmailWebhookRequest,
        synchronous: bool = True,
    ) -> InboundEmailWebhookResponse:
        """
        Ingests an inbound customer email with strict deduplication idempotency.
        Saves raw message immediately, then processes extraction and order fulfillment.
        """
        # 1. Idempotency Check: Verify if message_id was already ingested
        existing_stmt = select(EmailMessage).options(
            selectinload(EmailMessage.customer),
            selectinload(EmailMessage.order),
        ).where(EmailMessage.message_id == data.message_id)
        existing_msg = (await db.execute(existing_stmt)).scalar_one_or_none()

        if existing_msg:
            logger.info(f"Duplicate email webhook received with message_id '{data.message_id}'. Returning existing.")
            return InboundEmailWebhookResponse(
                email_id=existing_msg.id,
                message_id=existing_msg.message_id,
                status="DUPLICATE",
                order_id=existing_msg.order_id,
                order_number=existing_msg.order.order_number if existing_msg.order else None,
                order_status=existing_msg.order.status if existing_msg.order else None,
                customer_id=existing_msg.customer_id,
                customer_email=existing_msg.sender_email,
                detected_language=existing_msg.detected_language,
                is_order_intent=existing_msg.ai_extraction_payload.get("is_order_intent") if existing_msg.ai_extraction_payload else None,
                needs_human_review=existing_msg.ai_extraction_payload.get("needs_human_review") if existing_msg.ai_extraction_payload else None,
                review_reasons=existing_msg.ai_extraction_payload.get("review_reasons", []) if existing_msg.ai_extraction_payload else [],
                message="Duplicate email ignored; existing record returned.",
            )

        # 2. Persist Raw Inbound Email (Guarantees zero data loss)
        inbound_msg = EmailMessage(
            message_id=data.message_id,
            direction="INBOUND",
            sender_email=data.sender_email.lower().strip(),
            recipient_email=data.recipient_email.lower().strip() if data.recipient_email else "orders@opsmind.io",
            subject=data.subject.strip(),
            body_plain=data.body_plain.strip(),
            body_html=data.body_html,
        )
        db.add(inbound_msg)
        await db.commit()
        await db.refresh(inbound_msg)
        logger.info(f"Persisted inbound email {inbound_msg.id} (message_id: {data.message_id}) from {data.sender_email}")

        if not synchronous:
            return InboundEmailWebhookResponse(
                email_id=inbound_msg.id,
                message_id=inbound_msg.message_id,
                status="QUEUED",
                customer_email=inbound_msg.sender_email,
                message="Email ingested and queued for asynchronous AI processing.",
            )

        # 3. Synchronous Processing
        return await EmailService.process_inbound_email(db, inbound_msg.id, sender_display_name=data.sender_name)

    @staticmethod
    async def process_inbound_email(
        db: AsyncSession,
        email_id: uuid.UUID,
        sender_display_name: Optional[str] = None,
    ) -> InboundEmailWebhookResponse:
        """
        Executes AI extraction, customer auto-resolution, order creation & state progression,
        and fact-grounded outbound notification synthesis.
        """
        email_stmt = select(EmailMessage).where(EmailMessage.id == email_id)
        email_msg = (await db.execute(email_stmt)).scalar_one_or_none()
        if not email_msg:
            raise NotFoundException(f"EmailMessage with ID '{email_id}' not found")

        # 1. AI Extraction & Catalog Fuzzy Matching
        extraction, exec_ms, model_name = await AIService.extract_order_from_email(
            subject=email_msg.subject,
            body=email_msg.body_plain,
            sender_email=email_msg.sender_email,
            db=db,
        )

        email_msg.detected_language = extraction.detected_language
        email_msg.ai_extraction_payload = extraction.model_dump(mode="json")

        # 2. Customer Auto-Resolution & Profile Update
        customer = await EmailService._resolve_or_create_customer(
            db=db,
            sender_email=email_msg.sender_email,
            sender_name=extraction.sender_name or sender_display_name,
            shipping_address=extraction.shipping_address,
            phone=extraction.sender_phone,
            language=extraction.detected_language,
        )
        email_msg.customer_id = customer.id

        created_order: Optional[Order] = None
        outbound_msg: Optional[EmailMessage] = None
        final_status = "PROCESSED"

        # 3. Order Fulfillment Workflow
        if extraction.is_order_intent:
            resolved_line_items = [
                it for it in extraction.items
                if it.matched_product_id and it.quantity > 0
            ]

            if extraction.needs_human_review or not resolved_line_items:
                # Flagged for Admin Review -> Create order in NEEDS_REVIEW
                final_status = "NEEDS_REVIEW"
                created_order = await EmailService._create_review_order(
                    db=db,
                    customer=customer,
                    email_msg=email_msg,
                    extraction=extraction,
                    resolved_items=resolved_line_items,
                )
                email_msg.order_id = created_order.id

                # Outbound review notice to customer
                outbound_msg = await EmailService._send_outbound_notification(
                    db=db,
                    customer=customer,
                    order=created_order,
                    template_type="REVIEW_NOTICE",
                    target_language=customer.preferred_language,
                )

            else:
                # Clear order -> Attempt automatic reservation and progression
                created_order, order_outcome = await EmailService._process_valid_order(
                    db=db,
                    customer=customer,
                    email_msg=email_msg,
                    extraction=extraction,
                    resolved_items=resolved_line_items,
                )
                email_msg.order_id = created_order.id

                if order_outcome == "CONFIRMED":
                    # Stock reserved, moved to PACKAGING, task spawned -> Send confirmation email!
                    outbound_msg = await EmailService._send_outbound_notification(
                        db=db,
                        customer=customer,
                        order=created_order,
                        template_type="CONFIRMATION",
                        target_language=customer.preferred_language,
                    )
                elif order_outcome == "OUT_OF_STOCK":
                    # Out of stock notification
                    outbound_msg = await EmailService._send_outbound_notification(
                        db=db,
                        customer=customer,
                        order=created_order,
                        template_type="OUT_OF_STOCK",
                        target_language=customer.preferred_language,
                    )

        else:
            # Non-purchase order intent handling (e.g. status inquiry, cancellation)
            if extraction.intent_category == "STATUS_INQUIRY":
                latest_order = await EmailService._get_latest_customer_order(db, customer.id)
                if latest_order:
                    outbound_msg = await EmailService._send_outbound_notification(
                        db=db,
                        customer=customer,
                        order=latest_order,
                        template_type=latest_order.status if latest_order.status in ["PACKED", "OUT_FOR_DELIVERY", "DELIVERED"] else "CONFIRMATION",
                        target_language=customer.preferred_language,
                    )

        await db.commit()
        await db.refresh(email_msg)
        if created_order:
            await db.refresh(created_order)

        return InboundEmailWebhookResponse(
            email_id=email_msg.id,
            message_id=email_msg.message_id,
            status=final_status,
            order_id=created_order.id if created_order else None,
            order_number=created_order.order_number if created_order else None,
            order_status=created_order.status if created_order else None,
            customer_id=customer.id,
            customer_email=customer.email,
            detected_language=extraction.detected_language,
            is_order_intent=extraction.is_order_intent,
            needs_human_review=extraction.needs_human_review,
            review_reasons=extraction.review_reasons,
            outbound_email_id=outbound_msg.id if outbound_msg else None,
            message=f"Email successfully processed with intent '{extraction.intent_category}'.",
        )

    @staticmethod
    async def _resolve_or_create_customer(
        db: AsyncSession,
        sender_email: str,
        sender_name: Optional[str],
        shipping_address: Optional[str],
        phone: Optional[str],
        language: str,
    ) -> Customer:
        """
        Looks up customer by email or creates a new profile with extracted attributes.
        """
        stmt = select(Customer).where(Customer.email == sender_email.lower().strip())
        customer = (await db.execute(stmt)).scalar_one_or_none()

        if customer:
            # Update customer details if new info was parsed
            if language:
                customer.preferred_language = language
            if sender_name and (not customer.name or customer.name == "Customer"):
                customer.name = sender_name.strip()
            if shipping_address and not customer.address:
                customer.address = shipping_address.strip()
            if phone and not customer.phone:
                customer.phone = phone.strip()
        else:
            customer = Customer(
                email=sender_email.lower().strip(),
                name=(sender_name.strip() if sender_name else "Customer"),
                address=shipping_address.strip() if shipping_address else "",
                phone=phone.strip() if phone else None,
                preferred_language=language or "en",
                is_active=True,
            )
            db.add(customer)
            await db.flush()
            logger.info(f"Auto-created new customer record {customer.id} for {customer.email}")

        return customer

    @staticmethod
    async def _create_review_order(
        db: AsyncSession,
        customer: Customer,
        email_msg: EmailMessage,
        extraction: OrderExtractionResult,
        resolved_items: List[Any],
    ) -> Order:
        """
        Creates an Order marked as NEEDS_REVIEW with audit events detailing why human triage is needed.
        """
        order_number = OrderService.generate_order_number()
        shipping_addr = extraction.shipping_address or customer.address or "Address Required (Flagged for Review)"

        order = Order(
            customer_id=customer.id,
            order_number=order_number,
            status="NEEDS_REVIEW",
            delivery_address=shipping_addr,
            source_email_id=email_msg.message_id,
            total_amount=Decimal("0.00"),
        )
        db.add(order)
        await db.flush()

        total = Decimal("0.00")
        for it in resolved_items:
            unit_price = it.unit_price or Decimal("0.00")
            item_total = unit_price * it.quantity
            total += item_total
            oi = OrderItem(
                order_id=order.id,
                product_id=it.matched_product_id,
                quantity=it.quantity,
                unit_price=unit_price,
                total_price=item_total,
            )
            db.add(oi)

        order.total_amount = total

        ev = OrderEvent(
            order_id=order.id,
            from_status="RECEIVED",
            to_status="NEEDS_REVIEW",
            event_type="AI_EXTRACTION_FLAGGED",
            description=f"Routed to Admin Review Queue: {'; '.join(extraction.review_reasons)}",
        )
        db.add(ev)
        await db.flush()
        return order

    @staticmethod
    async def _process_valid_order(
        db: AsyncSession,
        customer: Customer,
        email_msg: EmailMessage,
        extraction: OrderExtractionResult,
        resolved_items: List[Any],
    ) -> Tuple[Order, str]:
        """
        Executes order creation, automated stock check, reservation, and task spawning.
        """
        shipping_addr = extraction.shipping_address or customer.address
        create_items = [
            CreateOrderItemRequest(product_id=it.matched_product_id, quantity=it.quantity)
            for it in resolved_items
        ]

        # 1. Create order in RECEIVED state
        order_req = CreateOrderRequest(
            customer_email=customer.email,
            customer_name=customer.name,
            shipping_address=shipping_addr,
            items=create_items,
            source=email_msg.message_id or "EMAIL",
        )
        order_resp = await OrderService.create_order(db, order_req)



        # 2. Advance: RECEIVED -> PROCESSING
        await OrderService.update_order_status(
            db,
            order_resp.id,
            UpdateOrderStatusRequest(new_status="PROCESSING", reason="AI pipeline automated verification"),
        )

        # 3. Attempt CONFIRMED (Atomic stock reservation)
        try:
            await OrderService.update_order_status(
                db,
                order_resp.id,
                UpdateOrderStatusRequest(new_status="CONFIRMED", reason="Stock validated & reserved"),
            )
            # Advance: CONFIRMED -> PACKAGING (Triggers least-loaded packaging task spawning!)
            await OrderService.update_order_status(
                db,
                order_resp.id,
                UpdateOrderStatusRequest(new_status="PACKAGING", reason="Automated packaging queue dispatch"),
            )
            # Spawn packaging task
            await TaskService.spawn_packaging_task(db, order_resp.id)
            db_order = await OrderService.get_order_by_id(db, order_resp.id)
            return db_order, "CONFIRMED"  # type: ignore

        except InsufficientStockException as e:
            logger.warning(f"Order {order_resp.order_number} marked OUT_OF_STOCK: {e.message}")
            await OrderService.update_order_status(
                db,
                order_resp.id,
                UpdateOrderStatusRequest(new_status="OUT_OF_STOCK", reason=f"Stock insufficient: {e.message}"),
            )
            db_order = await OrderService.get_order_by_id(db, order_resp.id)
            return db_order, "OUT_OF_STOCK"  # type: ignore


    @staticmethod
    def _send_smtp_sync(
        to_email: str,
        subject: str,
        body_plain: str,
        body_html: Optional[str] = None,
    ) -> bool:
        """
        Synchronous SMTP transport worker executed within a background worker thread.
        Supports TLS encryption and standard SMTP authentication (Gmail App Password, SendGrid, Amazon SES, Mailgun).
        """
        if not settings.SMTP_HOST or not settings.SMTP_USER or not settings.SMTP_PASSWORD:
            logger.info(f"[Mock SMTP Dispatch] Outbound email to '{to_email}' logged (SMTP credentials not configured in .env).")
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = settings.SMTP_FROM_EMAIL or "orders@opsmind.io"
            msg["To"] = to_email

            part1 = MIMEText(body_plain, "plain", "utf-8")
            msg.attach(part1)

            if body_html:
                part2 = MIMEText(body_html, "html", "utf-8")
                msg.attach(part2)

            port = settings.SMTP_PORT or 587
            with smtplib.SMTP(settings.SMTP_HOST, port, timeout=10) as server:
                if settings.SMTP_TLS:
                    server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(msg["From"], [to_email], msg.as_string())

            logger.info(f"Successfully delivered live SMTP email to '{to_email}' via {settings.SMTP_HOST}:{port}")
            return True
        except Exception as ex:
            logger.error(f"Failed to deliver live SMTP email to '{to_email}': {ex}")
            return False

    @staticmethod
    async def _dispatch_real_smtp_email(
        to_email: str,
        subject: str,
        body_plain: str,
        body_html: Optional[str] = None,
    ) -> bool:
        """
        Non-blocking asynchronous SMTP dispatcher that runs in a threadpool to prevent blocking FastAPI event loop.
        """
        try:
            return await asyncio.to_thread(
                EmailService._send_smtp_sync,
                to_email=to_email,
                subject=subject,
                body_plain=body_plain,
                body_html=body_html,
            )
        except Exception as ex:
            logger.error(f"Async SMTP dispatch error: {ex}")
            return False

    @staticmethod
    async def _send_outbound_notification(
        db: AsyncSession,
        customer: Customer,
        order: Order,
        template_type: str,
        target_language: str,
    ) -> EmailMessage:
        """
        Synthesizes fact-grounded localized transactional email, logs to email_messages,
        and dispatches real email via SMTP if configured.
        """
        # Load order items and product titles
        order_stmt = select(Order).options(
            selectinload(Order.items).selectinload(OrderItem.product)
        ).where(Order.id == order.id)
        loaded_order = (await db.execute(order_stmt)).scalar_one_or_none() or order

        items_summary = []
        if loaded_order.items:
            for oi in loaded_order.items:
                items_summary.append({
                    "name": oi.product.name if oi.product else "Product Item",
                    "sku": oi.product.sku if oi.product else "SKU",
                    "quantity": oi.quantity,
                })

        synth_req = OutboundSynthesisRequest(
            template_type=template_type,
            target_language=target_language or "en",
            customer_name=customer.name,
            order_number=order.order_number,
            items_summary=items_summary,
            total_amount=order.total_amount,
            shipping_address=order.delivery_address,
        )
        synth_resp = AIService.synthesize_fact_grounded_email(synth_req)

        outbound_msg_id = f"outbound_{order.order_number}_{uuid.uuid4().hex[:8]}@opsmind.io"
        outbound_email = EmailMessage(
            message_id=outbound_msg_id,
            customer_id=customer.id,
            order_id=order.id,
            direction="OUTBOUND",
            sender_email=settings.SMTP_FROM_EMAIL or "orders@opsmind.io",
            recipient_email=customer.email,
            subject=synth_resp.subject,
            body_plain=synth_resp.body_plain,
            body_html=synth_resp.body_html,
            detected_language=synth_resp.language,
        )
        db.add(outbound_email)
        await db.flush()

        logger.info(f"Persisted OUTBOUND {template_type} email {outbound_email.id} for {customer.email} in '{synth_resp.language}'")

        # Asynchronously dispatch real SMTP email
        await EmailService._dispatch_real_smtp_email(
            to_email=customer.email,
            subject=synth_resp.subject,
            body_plain=synth_resp.body_plain,
            body_html=synth_resp.body_html,
        )

        return outbound_email

    @staticmethod
    async def notify_customer_order_status(
        db: AsyncSession,
        order_id: uuid.UUID,
        new_status: str,
    ) -> Optional[EmailMessage]:
        """
        Public notification trigger called whenever order lifecycle changes:
        PACKED -> 'Your order is packed & assigned to delivery'
        OUT_FOR_DELIVERY -> 'Out for delivery'
        DELIVERED -> 'Delivered! Thank you for ordering with OpsMind'
        OUT_OF_STOCK -> 'Stock update notification'
        CANCELLED -> 'Order cancellation notice'
        """
        order_stmt = (
            select(Order)
            .options(selectinload(Order.customer), selectinload(Order.items).selectinload(OrderItem.product))
            .where(Order.id == order_id)
        )
        order = (await db.execute(order_stmt)).scalar_one_or_none()
        if not order or not order.customer:
            logger.warning(f"Cannot notify customer: Order {order_id} or associated customer not found.")
            return None

        # Map order status to synthesis template
        template_map = {
            "CONFIRMED": "CONFIRMATION",
            "PACKED": "PACKED",
            "OUT_FOR_DELIVERY": "OUT_FOR_DELIVERY",
            "DELIVERED": "DELIVERED",
            "OUT_OF_STOCK": "OUT_OF_STOCK",
            "CANCELLED": "CANCELLED",
        }
        template_type = template_map.get(new_status)
        if not template_type:
            logger.debug(f"No customer notification template needed for status '{new_status}'.")
            return None

        outbound = await EmailService._send_outbound_notification(
            db=db,
            customer=order.customer,
            order=order,
            template_type=template_type,
            target_language=order.customer.preferred_language or "en",
        )
        await db.commit()
        await db.refresh(outbound)
        return outbound

    @staticmethod
    async def test_smtp_connection(to_email: str) -> Dict[str, Any]:
        """
        Diagnostics endpoint helper to verify SMTP connectivity and configuration.
        """
        configured = bool(settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD)
        if not configured:
            return {
                "success": False,
                "configured": False,
                "message": "SMTP credentials (SMTP_HOST, SMTP_USER, SMTP_PASSWORD) are not configured in environment.",
                "smtp_host": settings.SMTP_HOST,
                "smtp_port": settings.SMTP_PORT,
            }

        test_subject = "OpsMind AI — SMTP Test Connection"
        test_plain = f"Hello,\n\nThis is a verification email from OpsMind AI Fulfillment Platform.\n\nTime: {datetime.now(timezone.utc).isoformat()}\nStatus: SMTP Connection Successful!"
        test_html = f"<h3>OpsMind AI — SMTP Test</h3><p>This is a verification email from <strong>OpsMind AI Fulfillment Platform</strong>.</p><p>Status: <span style='color:green;font-weight:bold;'>SMTP Connection Successful!</span></p>"

        delivered = await EmailService._dispatch_real_smtp_email(
            to_email=to_email,
            subject=test_subject,
            body_plain=test_plain,
            body_html=test_html,
        )

        return {
            "success": delivered,
            "configured": True,
            "recipient": to_email,
            "smtp_host": settings.SMTP_HOST,
            "smtp_port": settings.SMTP_PORT,
            "message": "Test email successfully sent!" if delivered else "Failed to send test email. Check SMTP server logs and credentials.",
        }

    @staticmethod
    async def _get_latest_customer_order(db: AsyncSession, customer_id: uuid.UUID) -> Optional[Order]:
        stmt = (
            select(Order)
            .where(Order.customer_id == customer_id)
            .order_by(Order.created_at.desc())
            .limit(1)
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    @staticmethod
    async def list_email_logs(
        db: AsyncSession,
        direction: Optional[str] = None,
        customer_id: Optional[uuid.UUID] = None,
        order_id: Optional[uuid.UUID] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[EmailMessageResponse], int]:
        """
        Paginated audit listing of all inbound and outbound email interactions for Admin inspection.
        """
        query = select(EmailMessage).options(
            selectinload(EmailMessage.customer),
            selectinload(EmailMessage.order),
        )
        count_query = select(func.count(EmailMessage.id))

        if direction:
            query = query.where(EmailMessage.direction == direction.upper().strip())
            count_query = count_query.where(EmailMessage.direction == direction.upper().strip())

        if customer_id:
            query = query.where(EmailMessage.customer_id == customer_id)
            count_query = count_query.where(EmailMessage.customer_id == customer_id)

        if order_id:
            query = query.where(EmailMessage.order_id == order_id)
            count_query = count_query.where(EmailMessage.order_id == order_id)

        if search:
            term = f"%{search.strip()}%"
            query = query.where(
                or_(
                    EmailMessage.sender_email.ilike(term),
                    EmailMessage.recipient_email.ilike(term),
                    EmailMessage.subject.ilike(term),
                    EmailMessage.message_id.ilike(term),
                )
            )
            count_query = count_query.where(
                or_(
                    EmailMessage.sender_email.ilike(term),
                    EmailMessage.recipient_email.ilike(term),
                    EmailMessage.subject.ilike(term),
                    EmailMessage.message_id.ilike(term),
                )
            )

        total_res = await db.execute(count_query)
        total = total_res.scalar() or 0

        query = query.order_by(EmailMessage.created_at.desc()).offset(skip).limit(limit)
        res = await db.execute(query)
        emails = res.scalars().all()

        dtos = [
            EmailMessageResponse(
                id=e.id,
                message_id=e.message_id,
                customer_id=e.customer_id,
                customer_name=e.customer.name if e.customer else None,
                order_id=e.order_id,
                order_number=e.order.order_number if e.order else None,
                direction=e.direction,
                sender_email=e.sender_email,
                recipient_email=e.recipient_email,
                subject=e.subject,
                body_plain=e.body_plain,
                body_html=e.body_html,
                detected_language=e.detected_language,
                ai_extraction_payload=e.ai_extraction_payload,
                created_at=e.created_at,
            )
            for e in emails
        ]

        return dtos, total
