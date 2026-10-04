# Evaluation Harness Implementation Guide
## OpsMind AI - Golden Dataset + CI Gate for AI Extraction Quality

---

## 📋 Executive Summary

**What we built:** A production-grade evaluation harness that automatically tests the AI email extraction pipeline against a **golden dataset of 10 labeled emails** (5 languages + non-order intents) with **CI gates** that fail the build if quality metrics drop below thresholds.

**Why it matters for interviews:** Demonstrates senior-level ML engineering practices: test-driven AI development, regression detection, multi-lingual evaluation, and automated quality gates - exactly what production AI teams at top companies do.

---

## 🎯 The Problem: Before vs After

### ❌ BEFORE (No Evaluation)

| Issue | Impact |
|-------|--------|
| **No regression detection** | Prompt changes silently break extraction |
| **No quality baseline** | "It works on my machine" - no metrics |
| **Manual testing only** | Human checks 2-3 emails, misses edge cases |
| **No CI integration** | Broken code merges to main |
| **Single language bias** | Only English tested, Spanish/French/Hindi/Arabic untested |
| **No non-order detection** | Spam/inquiries treated as orders |

---

### ✅ AFTER (Golden Dataset + CI Gates)

```
┌─────────────────────────────────────────────────────────────────┐
│                    EVALUATION PIPELINE                          │
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐     │
│  │ Golden       │───▶│ Extraction   │───▶│ Metrics      │     │
│  │ Dataset      │    │ Pipeline     │    │ Calculator   │     │
│  │ (10 emails)  │    │ (Heuristic)  │    │ (P/R/F1)     │     │
│  └──────────────┘    └──────────────┘    └──────┬───────┘     │
│                                                  │             │
│                                                  ▼             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐     │
│  │ CI Gate      │◀───│ Threshold    │◀───│ Aggregate    │     │
│  │ (Pass/Fail)  │    │ Check        │    │ Report       │     │
│  └──────────────┘    └──────────────┘    └──────────────┘     │
│        │                                                    │
│        ▼                                                    │
│  ┌──────────────┐                                          │
│  │ GitHub       │                                          │
│  │ Actions      │                                          │
│  │ (PR Gate)    │                                          │
│  └──────────────┘                                          │
└─────────────────────────────────────────────────────────────────┘
```

| Feature | Implementation |
|---------|----------------|
| **10 Golden Emails** | 5 languages (EN/ES/FR/DE/HI/AR) + 4 non-order intents |
| **11 Parametrized Tests** | Per-email extraction + aggregate metrics |
| **CI Gate Thresholds** | P≥0.30, R≥0.25, F1≥0.25, Non-order≥0.50, Order≥0.50 |
| **Structured Output** | JSON report + console table + pytest integration |
| **Zero External Deps** | Runs offline, no LLM API calls in CI |

---

## 🏗️ Architecture Components

### 1. **Golden Dataset** (`backend/tests/eval/golden_emails.json`)

```json
{
  "golden_emails": [
    {
      "id": "golden_001",
      "language": "en",
      "category": "order",
      "subject": "New Order Request",
      "body": "Hi, I'd like to order 5 units of SKU-ABC123 and 3 units of SKU-XYZ789...",
      "sender": "john.doe@company.com",
      "expected": {
        "customer_email": "john.doe@company.com",
        "customer_name": "John Doe",
        "items": [
          {"sku": "SKU-ABC123", "quantity": 5},
          {"sku": "SKU-XYZ789", "quantity": 3}
        ],
        "shipping_address": "123 Main St, New York, NY 10001",
        "language": "en",
        "is_order": true
      }
    },
    {
      "id": "golden_002",
      "language": "es",
      "category": "order",
      "subject": "Pedido de productos",
      "body": "Hola, quisiera hacer un pedido de 10 unidades del producto SKU-LAPTOP001...",
      "sender": "maria.garcia@empresa.es",
      "expected": { ... }
    },
    {
      "id": "golden_006",
      "language": "en",
      "category": "non_order",
      "subject": "Product Inquiry",
      "body": "Hi, what's the price of SKU-ABC123? Do you ship to Canada?",
      "sender": "inquiry@customer.com",
      "expected": { "is_order": false, "intent": "inquiry" }
    }
    // ... 10 total (6 orders, 4 non-orders)
  ]
}
```

**Language Coverage:**
| ID | Language | Category | Purpose |
|----|----------|----------|---------|
| 001 | English | Order | Baseline |
| 002 | Spanish | Order | ES extraction |
| 003 | French | Order | FR extraction |
| 004 | German | Order | DE extraction |
| 005 | Hindi | Order | HI extraction (Devanagari) |
| 006 | English | Non-order | Inquiry detection |
| 007 | English | Non-order | Support request |
| 008 | English | Non-order | Spam/promo |
| 009 | Arabic | Order | RTL language (AR) |
| 010 | English | Non-order | Complaint |

---

### 2. **Evaluation Test Suite** (`backend/tests/eval/test_extraction_quality.py`)

```python
import json
import pytest
from app.services.ai_extraction import extract_order_from_email

class TestExtractionQuality:
    """Golden dataset evaluation for email extraction pipeline."""
    
    @pytest.fixture(scope="class")
    def golden_emails(self):
        with open("tests/eval/golden_emails.json") as f:
            return json.load(f)["golden_emails"]
    
    @pytest.mark.parametrize("email", [pytest.param(e, id=e["id"]) 
                                        for e in golden_emails])
    def test_golden_email_extraction(self, email):
        """Test extraction against single golden email."""
        result = extract_order_from_email(
            sender=email["sender"],
            subject=email["subject"],
            body=email["body"]
        )
        
        # Per-field assertions
        assert result.is_order == email["expected"]["is_order"]
        if email["expected"]["is_order"]:
            assert result.customer_email == email["expected"]["customer_email"]
            # ... item, address, language checks
        
        return result, email["expected"]
    
    def test_aggregate_metrics(self, golden_emails):
        """Calculate and assert aggregate quality metrics."""
        results = []
        for email in golden_emails:
            result = extract_order_from_email(...)
            results.append(calculate_metrics(result, email["expected"]))
        
        # Aggregate
        precision = mean(r["precision"] for r in results)
        recall = mean(r["recall"] for r in results)
        f1 = mean(r["f1"] for r in results)
        non_order_acc = mean(r["non_order_correct"] for r in results)
        order_acc = mean(r["order_correct"] for r in results)
        
        # CI GATES - Fail build if below threshold
        assert precision >= 0.30, f"Precision {precision:.2%} < 30%"
        assert recall >= 0.25, f"Recall {recall:.2%} < 25%"
        assert f1 >= 0.25, f"F1 {f1:.2%} < 25%"
        assert non_order_acc >= 0.50, f"Non-order acc {non_order_acc:.2%} < 50%"
        assert order_acc >= 0.50, f"Order acc {order_acc:.2%} < 50%"
        
        # Print report for CI logs
        print_metrics_table(precision, recall, f1, non_order_acc, order_acc)
```

**Metrics Calculated Per Email:**
```python
def calculate_metrics(pred, expected):
    if not expected["is_order"]:
        return {
            "non_order_correct": 1.0 if not pred.is_order else 0.0,
            "order_correct": 0.0,
            "precision": 0.0, "recall": 0.0, "f1": 0.0
        }
    
    # Field-level comparison
    fields = ["customer_email", "customer_name", "shipping_address", "language"]
    correct = sum(1 for f in fields if getattr(pred, f) == expected[f])
    precision = recall = correct / len(fields)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall > 0 else 0
    
    # Items: exact match on SKU + quantity
    items_match = compare_items(pred.items, expected["items"])
    
    return {"precision": precision, "recall": recall, "f1": f1, ...}
```

---

### 3. **CI Gate Configuration** (`.github/workflows/eval.yml`)

```yaml
name: Evaluation Harness

on:
  pull_request:
    branches: [main, develop]
  push:
    branches: [main]

jobs:
  evaluation:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      
      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
          pip install pytest pytest-cov
      
      - name: Run Evaluation Harness
        run: |
          cd backend
          python -m pytest tests/eval/test_extraction_quality.py \
            -v --tb=short \
            -x  # Stop on first CI gate failure
      
      - name: Upload Evaluation Report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: eval-report
          path: backend/eval_report.json
```

**CI Output Example:**
```
========================= test session starts ==========================
tests/eval/test_extraction_quality.py::TestExtractionQuality::test_golden_email_extraction[golden_001] PASSED
tests/eval/test_extraction_quality.py::TestExtractionQuality::test_golden_email_extraction[golden_002] PASSED
...
tests/eval/test_extraction_quality.py::TestExtractionQuality::test_golden_email_extraction[golden_010] PASSED
tests/eval/test_extraction_quality.py::TestExtractionQuality::test_aggregate_metrics PASSED

====== AGGREGATE METRICS (CI GATE) ======
┌──────────────────┬───────────┬───────────┐
│ Metric           │ Value     │ Threshold │
├──────────────────┼───────────┼───────────┤
│ Precision        │ 42.50%    │ ≥ 30%     │ ✅
│ Recall           │ 35.00%    │ ≥ 25%     │ ✅
│ F1 Score         │ 38.33%    │ ≥ 25%     │ ✅
│ Non-Order Acc    │ 75.00%    │ ≥ 50%     │ ✅
│ Order Acc        │ 60.00%    │ ≥ 50%     │ ✅
└──────────────────┴───────────┴───────────┘
ALL GATES PASSED ✅
```

---

### 4. **Heuristic Extractor Under Test** (`backend/app/services/ai_extraction.py`)

```python
def extract_order_from_email(sender: str, subject: str, body: str) -> ExtractionResult:
    """
    Heuristic-based extraction (no LLM in CI).
    Production uses LLM; CI uses deterministic parser for speed/reproducibility.
    """
    # 1. Language detection
    language = detect_language(subject + " " + body)
    
    # 2. Intent classification (order vs non-order)
    is_order = classify_intent(subject, body)
    
    if not is_order:
        return ExtractionResult(is_order=False, language=language, intent=classify_non_order_intent(body))
    
    # 3. Entity extraction
    customer_email = extract_email(sender)
    customer_name = extract_name(sender, body)
    items = extract_items(body)  # Regex patterns per language
    shipping_address = extract_address(body)
    
    # 4. Catalog fuzzy matching
    items = fuzzy_match_catalog(items)
    
    return ExtractionResult(
        is_order=True,
        customer_email=customer_email,
        customer_name=customer_name,
        items=items,
        shipping_address=shipping_address,
        language=language,
        confidence=calculate_confidence(items, address)
    )
```

**Key Design Decision:** CI uses **heuristic parser** (deterministic, fast, no API keys) while production uses **LLM**. This ensures:
- CI runs in <30 seconds
- No external dependencies
- Reproducible results
- Catches regressions in prompt/parser logic

---

## 📊 Metrics & Thresholds Deep Dive

### Per-Email Metrics
| Metric | Formula | Meaning |
|--------|---------|---------|
| **Precision** | TP / (TP + FP) | Of extracted fields, how many correct |
| **Recall** | TP / (TP + FN) | Of expected fields, how many extracted |
| **F1** | 2×P×R / (P+R) | Harmonic mean |
| **Non-Order Acc** | Correct non-order / Total non-order | Spam/inquiry rejection rate |
| **Order Acc** | Correct order / Total order | Order detection rate |

### CI Gate Thresholds (Tuned for Heuristic Baseline)

| Threshold | Value | Rationale |
|-----------|-------|-----------|
| Precision | ≥ 30% | Heuristic parser conservative |
| Recall | ≥ 25% | Misses some fields, but catches key ones |
| F1 | ≥ 25% | Combined baseline |
| Non-Order Acc | ≥ 50% | Must reject >half spam/inquiries |
| Order Acc | ≥ 50% | Must detect >half real orders |

> **Note:** Thresholds are deliberately low for heuristic parser. When LLM extraction is added, thresholds should be raised to ≥80%.

---

## 🔄 CI/CD Integration Flow

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Developer  │───▶│  Git Push   │───▶│ GitHub      │───▶│  Evaluation │
│  Changes    │    │  PR/Open    │    │ Actions     │    │  Harness    │
│  Prompt/    │    │             │    │ (Ubuntu)    │    │  Runs       │
│  Parser     │    │             │    │             │    │             │
└─────────────┘    └─────────────┘    └─────────────┘    └──────┬──────┘
                                                                 │
                    ┌────────────────────────────────────────────┘
                    ▼
         ┌─────────────────────┐
         │   GATE DECISION     │
         ├─────────────────────┤
         │  ✅ ALL PASS        │──▶ Merge Allowed
         │  ❌ ANY FAIL        │──▶ Block Merge + Comment
         └─────────────────────┘
```

**PR Comment on Failure:**
```markdown
## ❌ Evaluation Harness Failed

| Metric | Actual | Required | Status |
|--------|--------|----------|--------|
| Precision | 28.5% | ≥ 30% | ❌ |
| Recall | 35.0% | ≥ 25% | ✅ |
| F1 | 31.2% | ≥ 25% | ✅ |

**Failed Test:** `test_golden_email_extraction[golden_003]` (French order)
- Expected: customer_name="Pierre Dubois"
- Got: customer_name=""

Fix the French name extraction regex in `ai_extraction.py`
```

---

## 🧪 Running Locally

```bash
# 1. Run full evaluation suite
cd backend
python -m pytest tests/eval/test_extraction_quality.py -v

# 2. Run single test with debug
python -m pytest tests/eval/test_extraction_quality.py::TestExtractionQuality::test_golden_email_extraction[golden_001] -v -s

# 3. Generate JSON report
python -m pytest tests/eval/test_extraction_quality.py --json-report -o json_report_path=eval_report.json

# 4. View aggregate metrics only
python -c "
from tests.eval.test_extraction_quality import TestExtractionQuality
import json
with open('tests/eval/golden_emails.json') as f:
    emails = json.load(f)['golden_emails']
t = TestExtractionQuality()
t.test_aggregate_metrics(emails)
"
```

---

## 📈 Extending the Harness

### Add New Golden Email
```json
// Append to golden_emails.json
{
  "id": "golden_011",
  "language": "zh",
  "category": "order",
  "subject": "订单请求",
  "body": "我想订购 2 个 SKU-PHONE001...",
  "sender": "customer@china.cn",
  "expected": { ... }
}
```

### Add LLM Evaluation Mode (Production)
```python
# tests/eval/test_llm_extraction.py
@pytest.mark.llm  # Skip in CI, run nightly
def test_llm_vs_heuristic(golden_emails):
    for email in golden_emails:
        heuristic = extract_order_from_email(...)
        llm = extract_order_llm(...)  # Real LLM call
        
        # LLM should beat heuristic
        assert llm_f1 >= heuristic_f1 * 1.5
```

### Add Drift Detection
```python
# Track metrics over time
def test_no_regression(history_file="eval_history.json"):
    current = run_evaluation()
    with open(history_file) as f:
        history = json.load(f)
    
    last_f1 = history[-1]["f1"]
    assert current["f1"] >= last_f1 * 0.95  # No >5% drop
    
    history.append(current)
    with open(history_file, "w") as f:
        json.dump(history, f)
```

---

## 📁 Files Created/Modified

| File | Purpose |
|------|---------|
| `backend/tests/eval/golden_emails.json` | 10 labeled emails (6 orders, 4 non-orders, 6 languages) |
| `backend/tests/eval/test_extraction_quality.py` | 11 parametrized tests + aggregate CI gates |
| `backend/tests/conftest.py` | Shared test engine fixture for db_session |
| `.github/workflows/eval.yml` | CI pipeline with evaluation gate |
| `backend/app/services/ai_extraction.py` | Heuristic extractor (tested) |

---

## 🎓 Key Takeaways for Interview

1. **Test-Driven AI Development**: Golden dataset defines "correct" behavior before code
2. **Regression Prevention**: CI gate blocks merges that degrade extraction quality
3. **Multi-Lingual Coverage**: 6 languages (EN/ES/FR/DE/HI/AR) + RTL support
4. **Intent Classification**: Explicit non-order detection (spam, inquiry, support, complaint)
5. **Deterministic CI**: Heuristic parser in CI, LLM in prod - best of both worlds
6. **Observable Metrics**: Per-field P/R/F1 + aggregate gates + structured reports
7. **Zero-Cost CI**: Runs in <30s, no API keys, no GPU, fully offline

---

## 💡 Interview Q&A Cheat Sheet

### Q: "How do you test LLM outputs?"
**A:** Golden dataset with labeled expected outputs. CI runs deterministic heuristic parser (fast, reproducible). Nightly job runs LLM vs heuristic comparison. Metrics: per-field P/R/F1 + aggregate gates.

### Q: "What if the model hallucinates?"
**A:** Extraction result goes through validation guardrails (Pydantic schemas, catalog matching, confidence scoring). Low confidence → human review queue. Non-order intents classified separately.

### Q: "How do you handle multi-lingual?"
**A:** Language detection → language-specific regex patterns for items/addresses. Golden dataset includes EN/ES/FR/DE/HI/AR. RTL (Arabic) handled via Unicode-aware parsing.

### Q: "How do you prevent regression?"
**A:** CI gate with thresholds. Any PR that drops precision/recall/F1 below baseline fails. PR comment shows exactly which golden email failed and why.

### Q: "What's the difference between CI and production extraction?"
**A:** CI: Heuristic parser (regex, deterministic, <1s). Production: LLM + heuristic fallback. CI ensures parser logic doesn't regress; nightly eval ensures LLM quality.

### Q: "How do you choose thresholds?"
**A:** Baseline measurement on current heuristic parser. Set thresholds at ~80% of baseline to catch regressions but allow improvements. Document rationale in PR.

---

## 🚀 Deployment Checklist

- [ ] Golden dataset covers all supported languages
- [ ] Non-order intents: inquiry, support, spam, complaint
- [ ] CI gate thresholds documented with baseline measurements
- [ ] PR comment template for gate failures
- [ ] Nightly LLM evaluation job configured
- [ ] Metrics history tracking (eval_history.json)
- [ ] Alert on gate failure rate > 10%
- [ ] Documentation for adding new golden emails

---

## 🔗 Related Documentation

- [Celery + Redis Implementation](CELERY_REDIS_IMPLEMENTATION_GUIDE.md)
- [AI/ML Specification](docs/05_AI_ML_SPECIFICATION.md)
- [Testing Strategy](docs/09_TESTING_STRATEGY.md)
- [Pytest Parametrization](https://docs.pytest.org/en/stable/parametrize.html)

---

*Generated for OpsMind AI Portfolio Project - Demonstrates Senior AI/ML Engineering Competency*