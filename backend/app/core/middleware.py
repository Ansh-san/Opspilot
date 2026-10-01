"""
OpsPilot — API Middlewares (Security & Tracing)
"""

import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


# Context variable to hold the request ID across async calls
request_id_var: ContextVar[str] = ContextVar("request_id", default="none")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Injects a UUID into a ContextVar for structured logging and adds it to the response headers.
    """
    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request_id_var.set(req_id)
        
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Applies security hardening headers to all responses.
    """
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response
