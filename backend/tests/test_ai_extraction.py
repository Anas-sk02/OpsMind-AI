import uuid
import pytest
from httpx import AsyncClient
from decimal import Decimal

from app.core.security import create_access_token
from app.schemas.ai_extraction import (
    ExtractedOrderItem,
    OrderExtractionResult,
    OutboundSynthesisRequest,
)
from app.services.ai_service import AIService


@pytest.fixture
def admin_headers():
    admin_id = str(uuid.uuid4())
    token = create_access_token(
        subject=admin_id,
        role="ADMIN",
        extra_claims={"email": "admin_ai@opsmind.io", "app_metadata": {"role": "ADMIN"}},
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def packager_1():
    pkg_id = str(uuid.uuid4())
    token = create_access_token(
        subject=pkg_id,
        role="PACKAGING",
        extra_claims={"email": "pkg_ai@opsmind.io", "app_metadata": {"role": "PACKAGING"}},
    )
    return {"id": pkg_id, "headers": {"Authorization": f"Bearer {token}"}}


@pytest.mark.asyncio
async def test_multilingual_extraction_english():
    subject = "Urgent Purchase Order - Office Supplies"
    body = """
    Hi OpsMind Sales,
    
    Please send 3x SKU-HEADSET-PRO and 2 units of Ergonomic Mechanical Keyboard RGB.
    Please deliver to: 100 Broadway, 14th Floor, New York, NY 10005.
    
    Thanks,
    Sarah Connor
    Phone: +1-212-555-0199
    """
    result, elapsed, model = await AIService.extract_order_from_email(subject, body, "sarah@cyberdyne.com")
    
    assert result.is_order_intent is True
    assert result.intent_category == "NEW_ORDER"
    assert result.detected_language == "en"
    assert result.sender_name == "Sarah Connor"
    assert result.shipping_address is not None
    assert "Broadway" in result.shipping_address
    assert len(result.items) >= 2


@pytest.mark.asyncio
async def test_multilingual_extraction_spanish():
    subject = "Nuevo pedido para sucursal Madrid"
    body = """
    Hola equipo,
    
    Quiero pedir 5 unidades de SKU-MONITOR-4K para nuestra nueva oficina.
    Dirección de envío: Calle Mayor 45, 3B, 28013 Madrid, España.
    
    Saludos,
    Carlos Mendoza
    """
    result, elapsed, model = await AIService.extract_order_from_email(subject, body, "carlos@madrid.es")
    
    assert result.is_order_intent is True
    assert result.detected_language == "es"
    assert result.sender_name == "Carlos Mendoza"
    assert result.shipping_address is not None
    assert "Calle Mayor" in result.shipping_address
    assert len(result.items) >= 1
    assert result.items[0].quantity == 5


@pytest.mark.asyncio
async def test_multilingual_extraction_french_and_german():
    # French
    fr_res, _, _ = await AIService.extract_order_from_email(
        subject="Commande express de matériel",
        body="Bonjour, veuillez envoyer 2x HyperX Headset. Adresse: 12 Rue de Rivoli, 75001 Paris. Merci, Jean Dupont",
    )
    assert fr_res.detected_language == "fr"
    assert fr_res.is_order_intent is True

    # German
    de_res, _, _ = await AIService.extract_order_from_email(
        subject="Bestellung für Berlin Büro",
        body="Hallo, bitte 4x Tastatur liefern an: Friedrichstraße 100, 10117 Berlin. Danke, Hans Schmidt",
    )
    assert de_res.detected_language == "de"
    assert de_res.is_order_intent is True


@pytest.mark.asyncio
async def test_non_order_intents_classification():
    # Status Inquiry
    res_status, _, _ = await AIService.extract_order_from_email(
        subject="Where is my order ORD-9921?",
        body="Hello, could you please check the tracking status of my delivery? Thanks!",
    )
    assert res_status.is_order_intent is False
    assert res_status.intent_category == "STATUS_INQUIRY"

    # Cancellation
    res_cancel, _, _ = await AIService.extract_order_from_email(
        subject="Cancel order request",
        body="Please cancel my previous order, we found an alternative supplier.",
    )
    assert res_cancel.is_order_intent is False
    assert res_cancel.intent_category == "CANCELLATION"

    # Spam
    res_spam, _, _ = await AIService.extract_order_from_email(
        subject="YOU HAVE WON A LOTTERY PRIZE",
        body="Claim your cash reward of 1,000,000 dollars by clicking this casino link!",
    )
    assert res_spam.is_order_intent is False
    assert res_spam.intent_category == "SPAM"


@pytest.mark.asyncio
async def test_catalog_entity_resolution_via_api(client: AsyncClient, admin_headers: dict):
    # 1. Create Catalog Products
    p1 = (
        await client.post(
            "/api/v1/admin/products",
            json={
                "sku": "SKU-HEADSET-PRO",
                "name": "HyperX Noise Cancelling Headset",
                "price": 129.99,
                "initial_stock": 20,
            },
            headers=admin_headers,
        )
    ).json()["data"]

    p2 = (
        await client.post(
            "/api/v1/admin/products",
            json={
                "sku": "SKU-KEYBOARD-MECH",
                "name": "Ergonomic Mechanical Keyboard RGB",
                "price": 89.50,
                "initial_stock": 15,
            },
            headers=admin_headers,
        )
    ).json()["data"]

    p3 = (
        await client.post(
            "/api/v1/admin/products",
            json={
                "sku": "SKU-MONITOR-4K",
                "name": "Dell UltraSharp 27-inch 4K Monitor",
                "price": 499.00,
                "initial_stock": 10,
            },
            headers=admin_headers,
        )
    ).json()["data"]

    # 2. Test Entity Resolution Endpoint
    queries = [
        "SKU-HEADSET-PRO",
        "Ergonomic Mechanical Keyboard RGB",
        "Dell UltraSharp 4K screen",
        "unknown quantum battery pack",
    ]
    res = await client.post(
        "/api/v1/ai/resolve-entities",
        json={"queries": queries},
        headers=admin_headers,
    )
    assert res.status_code == 200
    matches = res.json()["data"]["matches"]

    # Match 1: Exact SKU
    assert matches[0]["match_type"] == "EXACT_SKU"
    assert matches[0]["matched_product_id"] == p1["id"]
    assert matches[0]["confidence"] == 1.0

    # Match 2: Exact Name
    assert matches[1]["match_type"] == "EXACT_NAME"
    assert matches[1]["matched_product_id"] == p2["id"]
    assert matches[1]["confidence"] == 0.95

    # Match 3: Fuzzy Match
    assert matches[2]["match_type"] == "FUZZY_MATCH"
    assert matches[2]["matched_product_id"] == p3["id"]
    assert matches[2]["confidence"] >= 0.80

    # Match 4: Unresolved
    assert matches[3]["match_type"] == "UNRESOLVED"
    assert matches[3]["matched_product_id"] is None


@pytest.mark.asyncio
async def test_validation_guardrails_triggering():
    # Case 1: Low confidence or missing address
    bad_order = OrderExtractionResult(
        is_order_intent=True,
        intent_category="NEW_ORDER",
        detected_language="en",
        sender_name="John Doe",
        shipping_address=None,  # Missing address!
        items=[ExtractedOrderItem(raw_product_query="SKU-HEADSET-PRO", quantity=1)],
        confidence_score=0.60,  # Below 0.75 threshold!
    )
    guarded = AIService.apply_guardrails(bad_order, threshold=0.75)
    assert guarded.needs_human_review is True
    assert len(guarded.review_reasons) >= 2
    assert any("confidence" in r.lower() for r in guarded.review_reasons)
    assert any("address" in r.lower() for r in guarded.review_reasons)

    # Case 2: Unresolved items trigger review
    unresolved_order = OrderExtractionResult(
        is_order_intent=True,
        intent_category="NEW_ORDER",
        detected_language="en",
        shipping_address="123 Main St, Anytown",
        items=[ExtractedOrderItem(raw_product_query="Quantum CPU Core", quantity=1, match_type="UNRESOLVED")],
        confidence_score=0.95,
    )
    guarded2 = AIService.apply_guardrails(unresolved_order, threshold=0.75)
    assert guarded2.needs_human_review is True
    assert any("unresolved" in r.lower() for r in guarded2.review_reasons)


@pytest.mark.asyncio
async def test_fact_grounded_response_synthesis():
    # Test Spanish synthesis
    es_req = OutboundSynthesisRequest(
        template_type="CONFIRMATION",
        target_language="es",
        customer_name="Mateo Silva",
        order_number="ORD-2026-0042",
        items_summary=[{"name": "Monitor 4K", "quantity": 2}],
        shipping_address="Av. Reforma 222, CDMX",
    )
    es_resp = AIService.synthesize_fact_grounded_email(es_req)
    assert "ORD-2026-0042" in es_resp.subject
    assert "Mateo Silva" in es_resp.body_plain
    assert "Confirmación de Pedido" in es_resp.subject
    assert "Av. Reforma 222" in es_resp.body_plain

    # Test Hindi synthesis
    hi_req = OutboundSynthesisRequest(
        template_type="CONFIRMATION",
        target_language="hi",
        customer_name="रोहित शर्मा",
        order_number="ORD-HI-100",
        items_summary=[{"name": "Mechanical Keyboard", "quantity": 1}],
        shipping_address="MG Road, Bengaluru",
    )
    hi_resp = AIService.synthesize_fact_grounded_email(hi_req)
    assert "ORD-HI-100" in hi_resp.subject
    assert "ऑर्डर पुष्टिकरण" in hi_resp.subject


@pytest.mark.asyncio
async def test_ai_api_endpoints_rbac_and_execution(
    client: AsyncClient, admin_headers: dict, packager_1: dict
):
    # 1. Non-admin forbidden from AI endpoints
    forbidden_res = await client.post(
        "/api/v1/ai/extract",
        json={"subject": "Order", "body": "1x SKU-123"},
        headers=packager_1["headers"],
    )
    assert forbidden_res.status_code == 403

    # 2. Admin successfully extracts order
    extract_res = await client.post(
        "/api/v1/ai/extract",
        json={
            "subject": "New Order for Packaging Studio",
            "body": "Hi, please ship 2x Studio Mic to 456 Broadway, NY 10013. Thanks, Mike Ross",
            "sender_email": "mike@pearson.com",
        },
        headers=admin_headers,
    )
    assert extract_res.status_code == 200
    res_data = extract_res.json()["data"]
    assert "extraction" in res_data
    assert res_data["extraction"]["is_order_intent"] is True
    assert res_data["execution_time_ms"] > 0

    # 3. Test entity resolution endpoint
    resolve_res = await client.post(
        "/api/v1/ai/resolve-entities",
        json={"queries": ["SKU-TEST-001", "Gaming Headset"]},
        headers=admin_headers,
    )
    assert resolve_res.status_code == 200
    assert "matches" in resolve_res.json()["data"]
    assert len(resolve_res.json()["data"]["matches"]) == 2

    # 4. Test response synthesis endpoint
    synth_res = await client.post(
        "/api/v1/ai/synthesize-response",
        json={
            "template_type": "DELIVERED",
            "target_language": "en",
            "customer_name": "Rachel Zane",
            "order_number": "ORD-5501",
            "shipping_address": "789 5th Ave, NY",
        },
        headers=admin_headers,
    )
    assert synth_res.status_code == 200
    synth_data = synth_res.json()["data"]
    assert "ORD-5501" in synth_data["subject"]
    assert "Rachel Zane" in synth_data["body_plain"]
