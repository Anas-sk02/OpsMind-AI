from fastapi import APIRouter
from app.api.v1.health import router as health_router
from app.api.v1.auth import router as auth_router
from app.api.v1.admin_employees import router as admin_employees_router
from app.api.v1.admin_products import router as admin_products_router
from app.api.v1.admin_inventory import router as admin_inventory_router
from app.api.v1.admin_orders import router as admin_orders_router
from app.api.v1.employee_tasks import router as employee_tasks_router
from app.api.v1.ai import router as ai_router
from app.api.v1.webhooks import router as webhooks_router
from app.api.v1.admin_emails import router as admin_emails_router

api_v1_router = APIRouter()

# Health & Probe Status
api_v1_router.include_router(health_router, prefix="", tags=["Health & Status"])

# Authentication & Session Management
api_v1_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])

# Admin Staff & Employee Management
api_v1_router.include_router(admin_employees_router, tags=["Admin Employees"])

# Admin Product Catalog
api_v1_router.include_router(admin_products_router, tags=["Admin Products"])

# Admin Inventory & Stock Movement Ledger
api_v1_router.include_router(admin_inventory_router, tags=["Admin Inventory"])

# Admin Orders & State Machine
api_v1_router.include_router(admin_orders_router, tags=["Admin Orders"])

# Employee Tasks & Workload Management
api_v1_router.include_router(employee_tasks_router, tags=["Employee & Warehouse Tasks"])

# AI Extraction & Guardrails
api_v1_router.include_router(ai_router, tags=["AI & Extraction"])

# Inbound Email Webhooks
api_v1_router.include_router(webhooks_router, tags=["Inbound Email Webhooks"])

# Admin Email Communications Audit
api_v1_router.include_router(admin_emails_router, tags=["Admin Email Audit"])




