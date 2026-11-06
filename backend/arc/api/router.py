from fastapi import APIRouter

from arc.api.health import router as health_router

router = APIRouter(prefix="/api")
router.include_router(health_router)
