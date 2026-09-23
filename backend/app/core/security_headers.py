"""Security-headers middleware (F2 hardening)."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

CSP = "default-src 'self'; frame-ancestors 'none'; object-src 'none'"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach baseline response headers on every request."""

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = CSP
        response.headers["Referrer-Policy"] = "no-referrer"
        return response
