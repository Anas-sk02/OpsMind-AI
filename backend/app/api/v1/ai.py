import logging
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user, require_admin
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.ai_extraction import (
    ExtractEmailRequest,
    ExtractEmailResponse,
    EntityResolutionRequest,
    EntityResolutionResponse,
    OutboundSynthesisRequest,
    OutboundSynthesisResponse,
)
from app.services.ai_service import AIService

logger = logging.getLogger("opsmind.api.ai")
router = APIRouter(prefix="/ai", tags=["AI & Extraction"])


@router.post(
    "/extract",
    response_model=ApiResponse[ExtractEmailResponse],
    status_code=status.HTTP_200_OK,
    summary="Extract structured order data from raw email text",
)
async def extract_order_from_email(
    payload: ExtractEmailRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Extracts structured purchase order data from raw customer email text using Google Gemini
    (or deterministic NLP fallback), fuzzy matches catalog products in PostgreSQL,
    and applies strict safety guardrails.
    """
    extraction, exec_ms, model_name = await AIService.extract_order_from_email(
        subject=payload.subject,
        body=payload.body,
        sender_email=payload.sender_email,
        db=db,
    )

    return ApiResponse.ok(
        data=ExtractEmailResponse(
            extraction=extraction,
            execution_time_ms=exec_ms,
            model_name=model_name,
        )
    )


@router.post(
    "/resolve-entities",
    response_model=ApiResponse[EntityResolutionResponse],
    status_code=status.HTTP_200_OK,
    summary="Fuzzy resolve product queries against the active catalog",
)
async def resolve_entities(
    payload: EntityResolutionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Evaluates raw product query strings against active catalog items using
    exact SKU, exact Name, and Levenshtein token similarity matching.
    """
    matches = await AIService.match_raw_queries(db, payload.queries)
    return ApiResponse.ok(data=EntityResolutionResponse(matches=matches))


@router.post(
    "/synthesize-response",
    response_model=ApiResponse[OutboundSynthesisResponse],
    status_code=status.HTTP_200_OK,
    summary="Generate a fact-grounded multilingual customer transactional email",
)
async def synthesize_response(
    payload: OutboundSynthesisRequest,
    current_user: User = Depends(require_admin),
):
    """
    Generates a localized, fact-grounded transactional email in the customer's native language
    conditioned on verified backend data without hallucination.
    """
    result = AIService.synthesize_fact_grounded_email(payload)
    return ApiResponse.ok(data=result)
