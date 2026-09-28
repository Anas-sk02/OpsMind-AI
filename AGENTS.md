# AGENTS.md — Development Guidelines for OpsMind AI Platform

## Project Overview
OpsMind is an AI-powered, email-driven order-to-delivery fulfillment engine built with **FastAPI**, **PostgreSQL**, **SQLAlchemy 2.0**, **Pydantic v2**, and modern **React / TypeScript**.

For complete architecture, database schemas, and API documentation, refer to the [`docs/`](docs/) directory:
- [01. PRD / SRS](docs/01_PRD_SRS.md)
- [02. Software Architecture](docs/02_SOFTWARE_ARCHITECTURE.md)
- [03. Database Design & ERD](docs/03_DATABASE_DESIGN_ERD.md)
- [04. API Specification](docs/04_API_SPECIFICATION.md)
- [05. AI/ML Specification](docs/05_AI_ML_SPECIFICATION.md)
- [06. UI/UX Specification](docs/06_UI_UX_SPECIFICATION.md)
- [07. Roles & Permissions (RBAC)](docs/07_ROLES_AND_PERMISSIONS.md)
- [08. Codebase Architecture](docs/08_CODEBASE_ARCHITECTURE.md)
- [09. Testing Strategy](docs/09_TESTING_STRATEGY.md)
- [10. Deployment Guide](docs/10_DEPLOYMENT_GUIDE.md)
- [11. AI Coding Rules](docs/11_AI_CODING_RULES.md)
- [12. Phased Development Roadmap](docs/12_PHASED_DEVELOPMENT_ROADMAP.md)
- [Master PDF Roadmap](docs/OpsMind_Phased_Development_Roadmap.pdf)

---

## Core Rules for AI Assistants & Developers

1. **No Untrusted AI Execution:** The AI model processes text into Pydantic models. It never writes directly to the database or executes raw queries.
2. **Customer Zero-Login Rule:** Customers do NOT have login credentials, dashboards, or portals. They interact exclusively via email.
3. **Database (Supabase PostgreSQL):** The primary production & remote database is **Supabase PostgreSQL**. Asynchronous queries use `AsyncPG` with SSL enabled (`ssl=require`).
4. **Deferred Redis / Lean Execution:** Redis is deferred for early development phases; asynchronous jobs run via lightweight FastAPI `BackgroundTasks` / in-process async workers until external message brokers are plugged in.
5. **Idempotency:** Repeated delivery or status transition events must never deduct stock twice.
6. **Soft Deletes:** Products, employees, and customers use `is_active = false` to preserve referential integrity and audit history.
7. **Clean & Professional Code:** No dummy vibe-coding placeholders, no unstyled HTML, and strict type annotations across backend and frontend.
