"""
Evaluation Harness for AI Extraction Quality.
Runs golden dataset against AIService.extract_order_from_email and asserts:
- Intent classification accuracy
- Entity extraction (name, phone, address)
- Language detection
- Items presence detection
- Confidence thresholds
- Guardrail flags (needs_human_review)
"""
import json
import pytest
from pathlib import Path
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ai_service import AIService
from app.schemas.ai_extraction import OrderExtractionResult


GOLDEN_PATH = Path(__file__).parent / "golden_emails.json"


def load_golden_emails() -> list[dict[str, Any]]:
    """Load labeled golden emails from JSON fixture."""
    with GOLDEN_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _addr_contains(actual: str | None, expected_fragments: list[str]) -> bool:
    """Check if all expected address fragments appear in actual address (case-insensitive)."""
    if not actual or not expected_fragments:
        return not expected_fragments
    actual_lower = actual.lower()
    return all(frag.lower() in actual_lower for frag in expected_fragments)


class TestExtractionQuality:
    """Golden dataset evaluation tests for AI extraction pipeline."""

    @pytest.fixture(scope="class")
    def golden_cases(self) -> list[dict[str, Any]]:
        return load_golden_emails()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("case", load_golden_emails(), ids=lambda c: c["id"])
    async def test_golden_email_extraction(
        self,
        case: dict[str, Any],
        db_session: AsyncSession,
    ) -> None:
        """
        Run single golden email through full extraction pipeline and assert expectations.
        Uses deterministic offline parser (no Gemini API call in testing env).
        """
        exp = case["expected"]

        # Execute extraction
        result: OrderExtractionResult
        result, exec_ms, model_name = await AIService.extract_order_from_email(
            subject=case["subject"],
            body=case["body"],
            sender_email=case["sender_email"],
            db=db_session,
        )

        # ---- Core Assertions ----

        # Intent classification
        assert result.is_order_intent == exp["is_order_intent"], (
            f"[{case['id']}] is_order_intent: expected {exp['is_order_intent']}, got {result.is_order_intent}"
        )
        assert result.intent_category == exp["intent_category"], (
            f"[{case['id']}] intent_category: expected {exp['intent_category']}, got {result.intent_category}"
        )

        # Language detection
        assert result.detected_language == exp["detected_language"], (
            f"[{case['id']}] language: expected {exp['detected_language']}, got {result.detected_language}"
        )

        # Sender name (allow None match)
        exp_name = exp.get("sender_name")
        if exp_name is not None:
            assert result.sender_name == exp_name, (
                f"[{case['id']}] sender_name: expected '{exp_name}', got '{result.sender_name}'"
            )

        # Phone (allow None match)
        exp_phone = exp.get("sender_phone")
        if exp_phone is not None:
            assert result.sender_phone == exp_phone, (
                f"[{case['id']}] sender_phone: expected '{exp_phone}', got '{result.sender_phone}'"
            )

        # Shipping address (fragment containment)
        exp_addr_frags = exp.get("shipping_address_contains", [])
        assert _addr_contains(result.shipping_address, exp_addr_frags), (
            f"[{case['id']}] shipping_address missing fragments {exp_addr_frags} in '{result.shipping_address}'"
        )

        # Items presence check (heuristic parser has limited item extraction)
        if exp.get("has_items"):
            assert len(result.items) > 0, f"[{case['id']}] expected items but got none"
        else:
            assert len(result.items) == 0, f"[{case['id']}] expected no items but got {len(result.items)}"

        # Confidence threshold
        conf_min = exp.get("confidence_min", 0.0)
        assert result.confidence_score >= conf_min, (
            f"[{case['id']}] confidence {result.confidence_score:.2f} < minimum {conf_min:.2f}"
        )

        # Guardrail flag
        assert result.needs_human_review == exp["needs_human_review"], (
            f"[{case['id']}] needs_human_review: expected {exp['needs_human_review']}, got {result.needs_human_review}"
        )

        # Review reasons (if flagged)
        if exp["needs_human_review"]:
            exp_reasons = exp.get("review_reasons_contains", [])
            for reason_frag in exp_reasons:
                assert any(reason_frag in r for r in result.review_reasons), (
                    f"[{case['id']}] expected review reason containing '{reason_frag}' not in {result.review_reasons}"
                )

        # Performance sanity (offline parser should be fast)
        assert exec_ms < 500, f"[{case['id']}] extraction took {exec_ms:.1f}ms (expected < 500ms)"

    # ---- Aggregate Metrics Test (runs after all parametrized tests) ----

    @pytest.mark.asyncio
    async def test_aggregate_metrics(self, db_session: AsyncSession) -> None:
        """
        Compute and assert aggregate metrics across full golden dataset.
        Fails if overall metrics drop below thresholds.
        """
        cases = load_golden_emails()

        total = len(cases)
        intent_correct = 0
        lang_correct = 0
        items_correct = 0
        guarded_correct = 0

        for case in cases:
            exp = case["expected"]
            result, _, _ = await AIService.extract_order_from_email(
                subject=case["subject"],
                body=case["body"],
                sender_email=case["sender_email"],
                db=db_session,
            )

            # Intent accuracy
            if result.is_order_intent == exp["is_order_intent"]:
                intent_correct += 1

            # Language accuracy
            if result.detected_language == exp["detected_language"]:
                lang_correct += 1

            # Items presence accuracy
            exp_has = exp.get("has_items", False)
            got_has = len(result.items) > 0
            if exp_has == got_has:
                items_correct += 1

            # Guardrail accuracy
            if result.needs_human_review == exp["needs_human_review"]:
                guarded_correct += 1

        # Aggregate metrics
        intent_acc = intent_correct / total
        lang_acc = lang_correct / total
        items_acc = items_correct / total
        guard_acc = guarded_correct / total

        # Print for CI visibility
        print("\n=== GOLDEN DATASET AGGREGATE METRICS ===")
        print(f"Total cases:           {total}")
        print(f"Intent Accuracy:       {intent_acc:.2%}")
        print(f"Language Accuracy:     {lang_acc:.2%}")
        print(f"Items Presence Acc:    {items_acc:.2%}")
        print(f"Guardrail Accuracy:    {guard_acc:.2%}")

        # Thresholds for current heuristic parser (offline fallback)
        # These reflect actual parser capabilities - will improve with Gemini API
        assert intent_acc >= 0.90, f"Intent accuracy {intent_acc:.2%} below 90%"
        assert lang_acc >= 0.80, f"Language accuracy {lang_acc:.2%} below 80%"
        assert items_acc >= 0.70, f"Items presence accuracy {items_acc:.2%} below 70%"
        assert guard_acc >= 0.50, f"Guardrail accuracy {guard_acc:.2%} below 50%"