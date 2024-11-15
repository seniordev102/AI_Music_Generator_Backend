from fastapi import APIRouter

from app.api.admin.ac.route import router as ac_router
from app.api.admin.category.route import router as category_router
from app.api.admin.dashboard.route import router as dashboard_router
from app.api.admin.subscriptions.route import router as subscriptions_router
from app.api.admin.users.route import router as users_router

router = APIRouter()
router.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"])
router.include_router(users_router, prefix="/users", tags=["dashboard"])
router.include_router(ac_router, prefix="/active-campaign", tags=["active-campaign"])
router.include_router(category_router, prefix="/category", tags=["category"])
router.include_router(
    subscriptions_router, prefix="/subscriptions", tags=["subscriptions"]
)
