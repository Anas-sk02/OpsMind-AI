import re
import json
import time
import uuid
import difflib
import logging
from typing import List, Optional, Dict, Any, Tuple
from decimal import Decimal
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.product import Product
from app.schemas.ai_extraction import (
    ExtractedOrderItem,
    OrderExtractionResult,
    EntityMatchItem,
    OutboundSynthesisRequest,
    OutboundSynthesisResponse,
)

logger = logging.getLogger("opsmind.ai_service")

# Multi-lingual prompt with few-shot schema instructions
SYSTEM_EXTRACTION_PROMPT = """
You are OpsMind AI, an enterprise-grade precision entity extraction engine for order fulfillment.
Your objective is to extract structured purchase order data from customer emails into strict JSON format.

JSON SCHEMA REQUIREMENT:
{
  "is_order_intent": boolean, // true if email contains an explicit purchase/order intent
  "intent_category": string, // "NEW_ORDER" | "STATUS_INQUIRY" | "ORDER_MODIFICATION" | "CANCELLATION" | "SUPPORT_OTHER" | "SPAM"
  "detected_language": string, // ISO-639-1 code: "en", "es", "fr", "de", "hi", "ar", etc.
  "sender_name": string | null, // Customer full name
  "sender_phone": string | null, // Contact phone number if specified
  "shipping_address": string | null, // Physical delivery address
  "items": [
    {
      "raw_product_query": string, // Exact product name, model, or SKU mentioned
      "quantity": integer, // Number of units (must be > 0)
      "unit": string | null // "units", "boxes", "kg", "packs", etc.
    }
  ],
  "requested_delivery_date": string | null, // Mentioned target date
  "confidence_score": float, // 0.0 to 1.0 based on clarity and completeness
  "notes": string | null // Special instructions, gate codes, etc.
}

CRITICAL RULES:
1. Extract ONLY facts explicitly stated in the email. Never invent items, addresses, or phone numbers.
2. For multilingual emails (Spanish, French, German, Hindi, Arabic, etc.), understand the intent in that language, extract the line items, and set detected_language correctly.
3. If an email is ambiguous, unclear, or lacks shipping address, extract what is present and lower confidence_score (e.g. 0.50 - 0.70).
4. If the email is not a purchase order (e.g. asking for status, cancelling an order, spam), set is_order_intent: false and categorize appropriately.
5. Return ONLY valid JSON. Do not include introductory text or formatting outside JSON.
"""


class AIService:
    """
    Precision Multilingual AI Engine powered by Google Gemini,
    with deterministic Catalog Fuzzy Resolution and Pydantic Guardrails.
    """

    @staticmethod
    async def extract_order_from_email(
        subject: str,
        body: str,
        sender_email: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> Tuple[OrderExtractionResult, float, str]:
        """
        Parses inbound email into structured OrderExtractionResult.
        Executes Google Gemini LLM extraction (or offline fallback), resolves catalog items,
        and applies safety guardrails.
        """
        start_time = time.perf_counter()
        model_name = "gemini-1.5-flash"

        # Check if live Gemini API call is possible or mock/test fallback needed
        raw_result = await AIService._call_gemini_or_fallback(subject, body, sender_email)

        # Resolve catalog entities if database session is provided
        if db and raw_result.items:
            raw_result.items = await AIService.resolve_product_entities(db, raw_result.items)

        # Apply safety guardrails (confidence threshold, address checks, item resolution)
        final_result = AIService.apply_guardrails(raw_result, threshold=settings.AI_CONFIDENCE_THRESHOLD)

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        return final_result, round(elapsed_ms, 2), model_name

    @staticmethod
    async def _call_gemini_or_fallback(
        subject: str,
        body: str,
        sender_email: Optional[str] = None,
    ) -> OrderExtractionResult:
        """
        Calls Google Gemini API. If in test environment, key is missing, or network fails,
        uses high-precision deterministic heuristic parser.
        """
        api_key = settings.GEMINI_API_KEY

        # Skip live API network calls during test runs or if key is unconfigured/mock
        if (
            settings.ENVIRONMENT != "testing"
            and api_key
            and not api_key.startswith("mock_")
            and len(api_key) > 10
        ):
            try:
                prompt_content = f"Subject: {subject}\nSender: {sender_email or 'Unknown'}\n\nBody:\n{body}"
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
                
                payload = {
                    "contents": [
                        {
                            "role": "user",
                            "parts": [{"text": f"{SYSTEM_EXTRACTION_PROMPT}\n\nEmail to process:\n{prompt_content}"}]
                        }
                    ],
                    "generationConfig": {
                        "response_mime_type": "application/json",
                        "temperature": 0.1,
                    },
                }

                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(url, json=payload)
                    if response.status_code == 200:
                        data = response.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            raw_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "{}")
                            cleaned_json = AIService._clean_json_string(raw_text)
                            parsed_dict = json.loads(cleaned_json)
                            return OrderExtractionResult.model_validate(parsed_dict)
                    else:
                        logger.warning(f"Gemini API returned status {response.status_code}: {response.text}")
            except Exception as e:
                logger.error(f"Error invoking Gemini API: {e}. Falling back to deterministic NLP parser.")

        # Deterministic offline heuristic parser
        return AIService._heuristic_offline_parser(subject, body)

    @staticmethod
    def _clean_json_string(raw_text: str) -> str:
        """
        Strips markdown JSON formatting (```json ... ```) or trailing comments.
        """
        text = raw_text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

    @staticmethod
    def _heuristic_offline_parser(subject: str, body: str) -> OrderExtractionResult:
        """
        Deterministic regex & NLP heuristic parser for offline development, local unit tests,
        and multilingual parsing fallbacks.
        """
        full_text = f"{subject} {body}".strip()
        lower_text = full_text.lower()

        # Language Detection
        detected_lang = "en"
        if any(w in lower_text for w in ["hola", "pedido", "enviar", "unidades", "gracias", "dirección", "quiero"]):
            detected_lang = "es"
        elif any(w in lower_text for w in ["bonjour", "commande", "livrer", "adresse", "merci", "veuillez"]):
            detected_lang = "fr"
        elif any(w in lower_text for w in ["hallo", "bestellung", "liefern", "adresse", "danke", "bitte"]):
            detected_lang = "de"
        elif any(w in lower_text for w in ["नमस्ते", "ऑर्डर", "कृपया", "भेजें", "धन्यवाद"]):
            detected_lang = "hi"
        elif any(w in lower_text for w in ["مرحبا", "طلب", "شحن", "عنوان", "شكرا"]):
            detected_lang = "ar"

        # Intent Classification
        is_order = True
        intent_cat = "NEW_ORDER"
        confidence = 0.90

        if any(w in lower_text for w in ["status", "where is", "tracking", "suivi", "estado de mi pedido", "कब आएगा"]):
            is_order = False
            intent_cat = "STATUS_INQUIRY"
        elif any(w in lower_text for w in ["cancel", "annuler", "cancelar", "stornieren", "रद्द"]):
            is_order = False
            intent_cat = "CANCELLATION"
        elif any(w in lower_text for w in ["spam", "lottery", "winner", "casino"]):
            is_order = False
            intent_cat = "SPAM"
            confidence = 0.98

        # Extract Shipping Address
        shipping_addr: Optional[str] = None
        addr_match = re.search(
            r"(?:deliver to|ship to|shipping address|address|adresse|dirección de envío|dirección|envío a|पता|عنوان)[:\s]+([^\n\r]+)",
            full_text,
            re.IGNORECASE,
        )
        if addr_match:
            raw_addr = addr_match.group(1).strip()
            # Clean trailing words
            raw_addr = re.sub(r"\s*(?:thanks|saludos|merci|danke|regards).*$", "", raw_addr, flags=re.IGNORECASE).strip()
            shipping_addr = raw_addr
        elif "street" in lower_text or "avenue" in lower_text or "road" in lower_text or "way" in lower_text:
            for line in body.split("\n"):
                if any(k in line.lower() for k in ["street", "ave", "st", "road", "rd", "blvd", "lane"]):
                    shipping_addr = line.strip()
                    break

        # Extract Customer Name
        sender_name: Optional[str] = None
        name_match = re.search(
            r"(?:regards|thanks|sincerely|cordialement|saludos|atentamente|danke|merci)[,\s\n]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            full_text,
            re.IGNORECASE,
        )
        if name_match:
            sender_name = name_match.group(1).strip()

        # Extract Phone Number
        sender_phone: Optional[str] = None
        phone_match = re.search(r"(\+?\d{1,3}[-.\s]?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4})", full_text)
        if phone_match:
            sender_phone = phone_match.group(1).strip()

        # Extract Line Items
        items: List[ExtractedOrderItem] = []

        item_patterns = [
            r"(\d+)\s*(?:x|units of|pcs of|pieces of|unidades de|exemplaires de|stücke)?\s+([A-Za-z0-9\-\s]{3,40}?)(?=\n|\.|$|,|\s+(?:para|for|pour|für|an|to))",
            r"([A-Za-z0-9\-\s]{3,40}?)\s*[:\-]\s*(\d+)\s*(?:units|pcs|qty|pieces)?",
            r"(?:order|buy|purchase|quiero pedir|pedir|veuillez envoyer|bitte)\s+(\d+)\s*(?:x|unidades de|exemplaires de)?\s+([A-Za-z0-9\-\s]{3,40}?)(?=\n|\.|$|,|\s+(?:para|for|pour|für|an|to))",
        ]

        for pat in item_patterns:
            matches = re.findall(pat, body, re.IGNORECASE)
            for m in matches:
                if len(m) == 2:
                    if m[0].isdigit():
                        qty = int(m[0])
                        raw_q = m[1].strip()
                    elif m[1].isdigit():
                        qty = int(m[1])
                        raw_q = m[0].strip()
                    else:
                        continue

                    # Filter noise prefixes and trailing clauses
                    raw_q = re.sub(r"^(?:please send|i need|order for|deliver|pedir|unidades de|exemplaires de)\s+", "", raw_q, flags=re.IGNORECASE).strip()
                    raw_q = re.sub(r"\s+(?:para|for|pour|für|an|to|with|con)\s+.*$", "", raw_q, flags=re.IGNORECASE).strip()
                    
                    if raw_q and len(raw_q) >= 2 and qty > 0 and not any(it.raw_product_query.lower() == raw_q.lower() for it in items):
                        items.append(ExtractedOrderItem(raw_product_query=raw_q, quantity=qty))

        # Adjust confidence
        if is_order and not items:
            confidence = 0.40
        elif is_order and not shipping_addr:
            confidence = 0.65

        return OrderExtractionResult(
            is_order_intent=is_order,
            intent_category=intent_cat,
            detected_language=detected_lang,
            sender_name=sender_name,
            sender_phone=sender_phone,
            shipping_address=shipping_addr,
            items=items,
            confidence_score=confidence,
            notes=None,
        )

    @staticmethod
    async def resolve_product_entities(
        db: AsyncSession,
        items: List[ExtractedOrderItem],
    ) -> List[ExtractedOrderItem]:
        """
        Fuzzy entity matching algorithm resolving raw customer item strings
        against PostgreSQL active product catalog with confidence scoring.
        """
        stmt = select(Product).where(Product.is_active == True)
        res = await db.execute(stmt)
        products = res.scalars().all()

        if not products:
            for it in items:
                it.match_type = "UNRESOLVED"
                it.match_confidence = 0.0
            return items

        resolved_items: List[ExtractedOrderItem] = []

        for it in items:
            query = it.raw_product_query.strip()
            query_lower = query.lower()

            best_match: Optional[Product] = None
            best_score: float = 0.0
            match_type = "UNRESOLVED"
            alternatives: List[Dict[str, Any]] = []

            # 1. Exact SKU Match
            for p in products:
                if p.sku.lower() == query_lower or p.sku.lower() == query_lower.replace(" ", "-"):
                    best_match = p
                    best_score = 1.0
                    match_type = "EXACT_SKU"
                    break

            # 2. Exact Name Match
            if not best_match:
                for p in products:
                    if p.name.lower() == query_lower:
                        best_match = p
                        best_score = 0.95
                        match_type = "EXACT_NAME"
                        break

            # 3. Fuzzy Similarity & Token Overlap Match
            if not best_match:
                scores = []
                query_tokens = set(re.findall(r"\w+", query_lower))

                for p in products:
                    prod_name_lower = p.name.lower()
                    prod_sku_lower = p.sku.lower()
                    prod_tokens = set(re.findall(r"\w+", f"{prod_name_lower} {prod_sku_lower}"))

                    # Sequence similarity
                    name_sim = difflib.SequenceMatcher(None, query_lower, prod_name_lower).ratio()
                    sku_sim = difflib.SequenceMatcher(None, query_lower, prod_sku_lower).ratio()

                    # Token set overlap
                    overlap_cnt = len(query_tokens & prod_tokens)
                    token_coverage = (overlap_cnt / len(query_tokens)) if query_tokens else 0.0
                    token_score = 0.85 if token_coverage >= 0.75 else (token_coverage * 0.90 if token_coverage >= 0.50 else 0.0)

                    # Substring inclusion bonus
                    sub_bonus = 0.25 if (query_lower in prod_name_lower or prod_name_lower in query_lower) else 0.0

                    combined_score = min(
                        1.0,
                        max(
                            name_sim + sub_bonus,
                            sku_sim,
                            token_score,
                            (token_coverage * 0.5 + name_sim * 0.5) + (0.1 if token_coverage >= 0.5 else 0.0)
                        )
                    )
                    scores.append((combined_score, p))

                scores.sort(key=lambda x: x[0], reverse=True)

                if scores:
                    top_score, top_prod = scores[0]
                    if top_score >= 0.80:
                        best_match = top_prod
                        best_score = round(top_score, 2)
                        match_type = "FUZZY_MATCH"

                    else:
                        # Ambiguous or below threshold -> Collect top alternatives
                        for score, prod in scores[:3]:
                            if score > 0.35:
                                alternatives.append({
                                    "product_id": str(prod.id),
                                    "sku": prod.sku,
                                    "name": prod.name,
                                    "unit_price": float(prod.price),
                                    "similarity": round(score, 2),
                                })


            # Update item attributes
            if best_match and best_score >= 0.80:
                it.matched_product_id = best_match.id
                it.matched_sku = best_match.sku
                it.matched_name = best_match.name
                it.unit_price = best_match.price
                it.match_confidence = best_score
                it.match_type = match_type
                it.suggested_alternatives = []
            else:
                it.matched_product_id = None
                it.matched_sku = None
                it.matched_name = None
                it.unit_price = None
                it.match_confidence = round(best_score, 2)
                it.match_type = "UNRESOLVED"
                it.suggested_alternatives = alternatives

            resolved_items.append(it)

        return resolved_items

    @staticmethod
    def apply_guardrails(
        result: OrderExtractionResult,
        threshold: float = 0.75,
    ) -> OrderExtractionResult:
        """
        Enforces strict safety guardrails on AI outputs. Flagged items require Admin human triage.
        """
        reasons: List[str] = []

        if result.is_order_intent:
            if result.confidence_score < threshold:
                reasons.append(f"AI extraction confidence ({result.confidence_score:.2f}) is below security threshold ({threshold:.2f}).")

            if not result.items:
                reasons.append("Purchase order intent detected but zero line items were successfully extracted.")

            if not result.shipping_address or len(result.shipping_address.strip()) < 5:
                reasons.append("Missing or incomplete shipping address in email.")

            unresolved_items = [
                it.raw_product_query
                for it in result.items
                if it.match_type == "UNRESOLVED" or not it.matched_product_id
            ]
            if unresolved_items:
                reasons.append(f"Unresolved or ambiguous catalog items: {', '.join(unresolved_items)}.")

        if reasons:
            result.needs_human_review = True
            result.review_reasons = reasons
        else:
            result.needs_human_review = False
            result.review_reasons = []

        return result

    @staticmethod
    async def match_raw_queries(
        db: AsyncSession,
        queries: List[str],
    ) -> List[EntityMatchItem]:
        """
        Bulk entity resolution endpoint helper for raw query testing.
        """
        items = [ExtractedOrderItem(raw_product_query=q, quantity=1) for q in queries]
        resolved = await AIService.resolve_product_entities(db, items)

        matches = []
        for r in resolved:
            matches.append(
                EntityMatchItem(
                    query=r.raw_product_query,
                    matched_product_id=r.matched_product_id,
                    matched_sku=r.matched_sku,
                    matched_name=r.matched_name,
                    unit_price=r.unit_price,
                    confidence=r.match_confidence or 0.0,
                    match_type=r.match_type or "UNRESOLVED",
                    suggested_alternatives=r.suggested_alternatives,
                )
            )
        return matches

    @staticmethod
    def synthesize_fact_grounded_email(
        req: OutboundSynthesisRequest,
    ) -> OutboundSynthesisResponse:
        """
        Synthesizes fact-grounded multilingual transactional emails in the customer's native language.
        Guarantees zero hallucination by strictly interpolating verified backend facts.
        """
        lang = (req.target_language or "en").lower()
        customer = req.customer_name or "Valued Customer"
        order_no = req.order_number
        address = req.shipping_address or "your registered address"

        # Item summaries
        items_text_list = []
        for it in req.items_summary:
            qty = it.get("quantity", 1)
            name = it.get("name") or it.get("sku", "Item")
            items_text_list.append(f"• {qty}x {name}")
        items_str = "\n".join(items_text_list) if items_text_list else "• Your requested items"

        templates: Dict[str, Dict[str, Tuple[str, str]]] = {
            "CONFIRMATION": {
                "en": (
                    f"Order Confirmation — #{order_no}",
                    f"Hello {customer},\n\nThank you for your order! We have confirmed order #{order_no}.\n\nItems:\n{items_str}\n\nShipping Address:\n{address}\n\nOur warehouse packaging team is preparing your package. We will notify you once it ships.\n\nBest regards,\nOpsMind Fulfillment Team"
                ),
                "es": (
                    f"Confirmación de Pedido — #{order_no}",
                    f"Hola {customer},\n\n¡Gracias por su pedido! Hemos confirmado su pedido #{order_no}.\n\nArtículos:\n{items_str}\n\nDirección de Envío:\n{address}\n\nNuestro equipo de almacén está preparando su paquete. Le notificaremos cuando esté en camino.\n\nAtentamente,\nEquipo de OpsMind"
                ),
                "fr": (
                    f"Confirmation de Commande — #{order_no}",
                    f"Bonjour {customer},\n\nMerci pour votre commande ! Nous avons confirmé votre commande #{order_no}.\n\nArticles:\n{items_str}\n\nAdresse de livraison:\n{address}\n\nNotre équipe prépare votre colis avec soin.\n\nCordialement,\nL'équipe OpsMind"
                ),
                "de": (
                    f"Bestellbestätigung — #{order_no}",
                    f"Hallo {customer},\n\nvielen Dank für Ihre Bestellung! Wir haben die Bestellung #{order_no} bestätigt.\n\nArtikel:\n{items_str}\n\nLieferadresse:\n{address}\n\nUnser Team bereitet Ihre Sendung vor.\n\nMit freundlichen Grüßen,\nIhr OpsMind Team"
                ),
                "hi": (
                    f"ऑर्डर पुष्टिकरण — #{order_no}",
                    f"नमस्ते {customer},\n\nआपके ऑर्डर के लिए धन्यवाद! हमने ऑर्डर #{order_no} की पुष्टि कर दी है।\n\nसामान:\n{items_str}\n\nडिलीवरी का पता:\n{address}\n\nहमारा वेयरहाउस पैकेज तैयार कर रहा है।\n\nसादर,\nऑप्समाइंड टीम"
                ),
                "ar": (
                    f"تأكيد الطلب — #{order_no}",
                    f"مرحبا {customer}،\n\nشكراً لطلبك! تم تأكيد طلبك رقم #{order_no}.\n\nالمنتجات:\n{items_str}\n\nعنوان التوصيل:\n{address}\n\nيقوم فريقنا بتجهيز شحنتك حالياً.\n\nمع تحياتنا،\nفريق أوبس مايند"
                ),
            },
            "PACKED": {
                "en": (
                    f"Order #{order_no} Packed & Ready for Dispatch",
                    f"Hello {customer},\n\nGood news! Your order #{order_no} has been securely packed and assigned to our delivery team.\n\nItems:\n{items_str}\n\nDestination:\n{address}\n\nBest regards,\nOpsMind Team"
                ),
                "es": (
                    f"Pedido #{order_no} Empaquetado y Listo",
                    f"Hola {customer},\n\n¡Buenas noticias! Su pedido #{order_no} ha sido empaquetado y asignado a nuestro equipo de entrega.\n\nAtentamente,\nEquipo de OpsMind"
                ),
            },
            "OUT_FOR_DELIVERY": {
                "en": (
                    f"Out for Delivery: Order #{order_no}",
                    f"Hello {customer},\n\nYour order #{order_no} is currently out for delivery to:\n{address}\n\nPlease ensure someone is available to receive it.\n\nBest regards,\nOpsMind Delivery Team"
                ),
                "es": (
                    f"En Camino: Pedido #{order_no}",
                    f"Hola {customer},\n\nSu pedido #{order_no} está en camino a su dirección:\n{address}\n\nAtentamente,\nEquipo de OpsMind"
                ),
            },
            "DELIVERED": {
                "en": (
                    f"Delivered: Order #{order_no}",
                    f"Hello {customer},\n\nYour order #{order_no} has been successfully delivered to:\n{address}\n\nThank you for shopping with us!\n\nBest regards,\nOpsMind Team"
                ),
                "es": (
                    f"Entregado: Pedido #{order_no}",
                    f"Hola {customer},\n\nSu pedido #{order_no} ha sido entregado exitosamente en:\n{address}\n\n¡Gracias por su preferencia!\n\nAtentamente,\nEquipo de OpsMind"
                ),
            },
            "OUT_OF_STOCK": {
                "en": (
                    f"Stock Update Regarding Order #{order_no}",
                    f"Hello {customer},\n\nWe received your request for order #{order_no}. However, one or more items are currently out of stock:\n{items_str}\n\nOur procurement team has been alerted and we will fulfill your order as soon as fresh inventory arrives.\n\nBest regards,\nOpsMind Support"
                ),
                "es": (
                    f"Actualización de Inventario para Pedido #{order_no}",
                    f"Hola {customer},\n\nRecibimos su solicitud para el pedido #{order_no}. Lamentablemente, uno o más artículos están agotados temporalmente:\n{items_str}\n\nLe mantendremos informado.\n\nAtentamente,\nSoporte OpsMind"
                ),
            },
            "REVIEW_NOTICE": {
                "en": (
                    f"We are Reviewing Your Order Request — #{order_no}",
                    f"Hello {customer},\n\nThank you for contacting OpsMind. Our support team is currently verifying the details of your request (#{order_no}) to ensure exact accuracy.\n\nWe will update you shortly.\n\nBest regards,\nOpsMind Customer Care"
                ),
                "es": (
                    f"Estamos Revisando su Solicitud — #{order_no}",
                    f"Hola {customer},\n\nGracias por comunicarse con OpsMind. Nuestro equipo está revisando los detalles de su pedido (#{order_no}) para garantizar su precisión.\n\nAtentamente,\nAtención al Cliente OpsMind"
                ),
            },
        }

        template_group = templates.get(req.template_type, templates["CONFIRMATION"])
        subject_template, body_template = template_group.get(lang, template_group.get("en", ("", "")))

        return OutboundSynthesisResponse(
            subject=subject_template,
            body_plain=body_template,
            body_html=f"<pre style='font-family: sans-serif; font-size: 14px;'>{body_template}</pre>",
            language=lang,
        )
