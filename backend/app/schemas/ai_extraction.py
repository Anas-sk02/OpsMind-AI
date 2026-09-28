import uuid
from decimal import Decimal
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, EmailStr, ConfigDict


class ExtractedOrderItem(BaseModel):
    """
    Extracted order line item from natural language input.
    """
    model_config = ConfigDict(from_attributes=True)

    raw_product_query: str = Field(..., description="Raw product name, brand, or SKU mentioned in the email")
    quantity: int = Field(..., gt=0, description="Requested positive integer quantity")
    unit: Optional[str] = Field(None, description="Packaging unit if mentioned (e.g., units, boxes, kg, packs)")
    
    # Entity Resolution enrichments
    matched_product_id: Optional[uuid.UUID] = Field(None, description="Resolved Product UUID in catalog")
    matched_sku: Optional[str] = Field(None, description="Resolved official product SKU")
    matched_name: Optional[str] = Field(None, description="Resolved official product title")
    unit_price: Optional[Decimal] = Field(None, description="Current catalog unit price")
    match_confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Confidence of catalog entity match")
    match_type: Optional[str] = Field(
        None,
        description="Type of resolution: EXACT_SKU | EXACT_NAME | FUZZY_MATCH | UNRESOLVED"
    )
    suggested_alternatives: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Top candidate catalog products if confidence is below threshold"
    )


class OrderExtractionResult(BaseModel):
    """
    Complete structured extraction output produced by AI model and verified by Pydantic guardrails.
    """
    model_config = ConfigDict(from_attributes=True)

    is_order_intent: bool = Field(
        ...,
        description="True if the email contains an explicit purchase order request"
    )
    intent_category: str = Field(
        default="NEW_ORDER",
        description="Classification: NEW_ORDER | STATUS_INQUIRY | ORDER_MODIFICATION | CANCELLATION | SUPPORT_OTHER | SPAM"
    )
    detected_language: str = Field(
        default="en",
        description="Detected ISO-639-1 language code (e.g. en, es, fr, de, hi, ar)"
    )
    sender_name: Optional[str] = Field(
        None,
        description="Customer full name if present in email text or sign-off"
    )
    sender_phone: Optional[str] = Field(
        None,
        description="Customer contact phone number if specified"
    )
    shipping_address: Optional[str] = Field(
        None,
        description="Extracted physical shipping / delivery address"
    )
    items: List[ExtractedOrderItem] = Field(
        default_factory=list,
        description="List of requested line items"
    )
    requested_delivery_date: Optional[str] = Field(
        None,
        description="ISO date string or explicit delivery date requested by customer"
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall self-assessed extraction confidence score from AI model"
    )
    notes: Optional[str] = Field(
        None,
        description="Special instructions, gate codes, or remarks provided by customer"
    )
    needs_human_review: bool = Field(
        default=False,
        description="Flagged true if confidence < threshold or ambiguous entities require Admin triage"
    )
    review_reasons: List[str] = Field(
        default_factory=list,
        description="Detailed list of specific guardrail flags requiring human verification"
    )


class ExtractEmailRequest(BaseModel):
    """
    Request payload for extracting structured data from raw email text.
    """
    subject: str = Field(..., min_length=1, description="Email subject line")
    body: str = Field(..., min_length=1, description="Raw plain or HTML email body")
    sender_email: Optional[EmailStr] = Field(None, description="Sender email address")


class ExtractEmailResponse(BaseModel):
    """
    Response envelope containing structured extraction and performance metadata.
    """
    extraction: OrderExtractionResult
    execution_time_ms: float
    model_name: str


class EntityResolutionRequest(BaseModel):
    """
    Test request for catalog entity resolution.
    """
    queries: List[str] = Field(..., min_length=1, description="List of raw product query strings")


class EntityMatchItem(BaseModel):
    query: str
    matched_product_id: Optional[uuid.UUID] = None
    matched_sku: Optional[str] = None
    matched_name: Optional[str] = None
    unit_price: Optional[Decimal] = None
    confidence: float
    match_type: str
    suggested_alternatives: List[Dict[str, Any]] = Field(default_factory=list)


class EntityResolutionResponse(BaseModel):
    matches: List[EntityMatchItem]


class OutboundSynthesisRequest(BaseModel):
    """
    Request payload for fact-grounded multilingual response generation.
    """
    template_type: str = Field(
        ...,
        description="CONFIRMATION | OUT_OF_STOCK | PACKED | OUT_FOR_DELIVERY | DELIVERED | REVIEW_NOTICE"
    )
    target_language: str = Field(default="en", description="Target ISO language code")
    customer_name: Optional[str] = None
    order_number: str
    items_summary: List[Dict[str, Any]] = Field(default_factory=list)
    total_amount: Optional[Decimal] = None
    shipping_address: Optional[str] = None
    extra_notes: Optional[str] = None


class OutboundSynthesisResponse(BaseModel):
    subject: str
    body_plain: str
    body_html: Optional[str] = None
    language: str
