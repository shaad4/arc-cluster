from fastapi import APIRouter

from arc.api.cluster import router as cluster_router
from arc.api.controls import router as controls_router
from arc.api.health import router as health_router
from arc.api.jobs import router as jobs_router
from arc.api.logs import router as logs_router
from arc.api.settings import router as settings_router

router = APIRouter(prefix="/api")
router.include_router(health_router)
router.include_router(cluster_router)

router.include_router(jobs_router)

router.include_router(controls_router)
router.include_router(logs_router)

router.include_router(settings_router)
