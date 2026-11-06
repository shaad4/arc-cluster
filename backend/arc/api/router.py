from fastapi import APIRouter

from arc.api.cluster import router as cluster_router
from arc.api.health import router as health_router

router = APIRouter(prefix="/api")
router.include_router(health_router)
router.include_router(cluster_router)
