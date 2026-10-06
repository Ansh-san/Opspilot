"""
OpsPilot — Redis-backed Distributed Rate Limiting.
"""

from fastapi import FastAPI, Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import settings

def get_user_or_ip(request: Request) -> str:
    """
    Extracts the user ID from the request state if available (set by deps),
    otherwise falls back to the client's IP address.
    """
    user = getattr(request.state, "user", None)
    if user and hasattr(user, "id"):
        return str(user.id)
    return get_remote_address(request)


# Redis-backed distributed rate limiter.
# If Redis is unreachable (e.g. no Redis service on the host), fall back to
# in-memory limiting and swallow storage errors rather than failing requests
# with a 500 — which the browser would surface as a CORS/network error.
limiter = Limiter(
    key_func=get_user_or_ip,
    storage_uri=settings.REDIS_URL,
    strategy="fixed-window",
    in_memory_fallback_enabled=True,
    swallow_errors=True,
)


def setup_rate_limiter(app: FastAPI) -> None:
    """Configures the rate limiter on the FastAPI application."""
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
