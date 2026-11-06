from urllib.parse import urlsplit

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class MutationGuard(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("origin")
            expected = f"{request.url.scheme}://{request.headers.get('host', '')}"
            if (
                not origin
                or origin != expected
                or urlsplit(origin).hostname not in {"localhost", "127.0.0.1"}
                or request.headers.get("x-arc-request") != "1"
                or request.headers.get("sec-fetch-site") == "cross-site"
            ):
                return JSONResponse(
                    {"detail": "Same-origin ARC request required"}, status_code=403
                )
        return await call_next(request)
