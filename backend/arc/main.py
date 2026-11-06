"""Application assembly and unexpected-error boundary."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from arc.api.router import router
from arc.config import APP_NAME, APP_VERSION, Settings
from arc.models.error import ErrorResponse
from arc.services.monitor import Monitor

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None, monitor: Monitor | None = None
) -> FastAPI:
    settings = settings or Settings()
    monitor = monitor or Monitor(settings)

    @asynccontextmanager
    async def lifespan(app):
        await monitor.start()
        try:
            yield
        finally:
            await monitor.close()

    application = FastAPI(
        title=APP_NAME,
        lifespan=lifespan,
        version=APP_VERSION,
        responses={500: {"model": ErrorResponse}},
    )
    application.state.monitor = monitor
    application.state.settings = settings
    application.include_router(router)

    @application.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled API error", exc_info=exc)
        error = ErrorResponse(detail="Internal server error")
        return JSONResponse(status_code=500, content=error.model_dump())

    return application


app = create_app()
