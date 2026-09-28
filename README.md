# OpsMind AI

OpsMind is an AI-powered, email-driven order-to-delivery fulfillment engine built with **FastAPI**, **Supabase PostgreSQL**, **SQLAlchemy 2.0**, **Pydantic v2**, and modern **React / TypeScript**.

## Architecture & Features
- **Supabase Authentication & PostgreSQL:** Unified server-side RBAC and relational database with AsyncPG.
- **FastAPI Core Engine:** Clean architecture with async sessions, custom error envelopes, and automated testing.
- **Zero-Customer Login Email Fulfillment:** Automated processing of inbound customer order emails.
- **State Machine Guardrails:** Idempotent order transitions from creation to packaging, dispatch, and delivery.

## Getting Started

### 1. Virtual Environment & Dependencies
```bash
# Create venv and activate
python -m venv backend/.venv
.\backend\.venv\Scripts\activate

# Install dependencies
pip install -r backend/requirements.txt
```

### 2. Environment Configuration
Copy `.env.example` to `backend/.env` and update your Supabase credentials:
```bash
cp .env.example backend/.env
```

### 3. Run Test Suite
```bash
pytest -v backend/tests
```

### 4. Start Backend Server
```bash
uvicorn app.main:app --reload --port 8000
```
