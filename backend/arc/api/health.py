from datetime import UTC, datetime

from fastapi import APIRouter, Response

from arc.config import APP_NAME, APP_VERSION
from arc.models.health import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["health"])
async def health(response: Response) -> HealthResponse:
    """Application liveness only; does not check Ray or machine reachability."""
    response.headers["Cache-Control"] = "no-store"
    return HealthResponse(
        name=APP_NAME,
        version=APP_VERSION,
        status="ok",
        timestamp=datetime.now(UTC),
    )
