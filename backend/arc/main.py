"""Application assembly and unexpected-error boundary."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from arc.api.router import router
from arc.config import APP_NAME, APP_VERSION
from arc.models.error import ErrorResponse

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    application = FastAPI(
        title=APP_NAME,
        version=APP_VERSION,
        responses={500: {"model": ErrorResponse}},
    )
    application.include_router(router)

    @application.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled API error", exc_info=exc)
        error = ErrorResponse(detail="Internal server error")
        return JSONResponse(status_code=500, content=error.model_dump())

    return application


app = create_app()
