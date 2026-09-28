from fastapi import APIRouter
from app.api.v1.health import router as health_router
from app.api.v1.auth import router as auth_router
from app.api.v1.admin_employees import router as admin_employees_router

api_v1_router = APIRouter()

# Health & Probe Status
api_v1_router.include_router(health_router, prefix="", tags=["Health & Status"])

# Authentication & Session Management
api_v1_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])

# Admin Staff & Employee Management
api_v1_router.include_router(admin_employees_router, prefix="/admin/employees", tags=["Admin Employees"])

# Subsequent phase routers will be registered here cleanly:
# api_v1_router.include_router(admin_products_router, prefix="/admin/products", tags=["Admin Products"])
# api_v1_router.include_router(admin_inventory_router, prefix="/admin/inventory", tags=["Admin Inventory"])
# api_v1_router.include_router(admin_orders_router, prefix="/admin/orders", tags=["Admin Orders"])
# api_v1_router.include_router(employee_tasks_router, prefix="/employee/tasks", tags=["Employee Tasks"])
# api_v1_router.include_router(webhooks_router, prefix="/webhooks", tags=["Webhooks"])
