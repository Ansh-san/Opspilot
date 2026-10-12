"""
OpsPilot Backend — FastAPI Application Entry Point
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging_config import setup_logging
from app.api.v1.router import api_router
from app.core.middleware import RequestIDMiddleware, SecurityHeadersMiddleware
from app.core.rate_limiter import setup_rate_limiter

# Initialise structured logging before anything else
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup / shutdown lifecycle."""
    logger.info(
        "OpsPilot starting",
        extra={"version": settings.VERSION, "environment": settings.ENVIRONMENT},
    )
    yield
    logger.info("OpsPilot shutting down")


# ─── FastAPI application ──────────────────────────────────────────────────────
app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "OpsPilot — AI-powered Enterprise WorkOps/ServiceOps Platform. "
        "Reliable · Observable · Secure · Explainable · Actionable."
    ),
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan,
)


# ─── Middleware ───────────────────────────────────────────────────────────────
# IMPORTANT: Starlette executes middleware in REVERSE order of registration —
# the LAST middleware added is the OUTERMOST and sees the request first.
# CORSMiddleware is therefore added LAST so it answers OPTIONS preflight
# requests and attaches CORS headers before any other middleware can reject
# or fail the request.
setup_rate_limiter(app)

if settings.ENVIRONMENT == "production":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.ALLOWED_HOSTS,
    )

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIDMiddleware)

# TEMPORARY: allow all origins while debugging the Vercel ↔ Render deployment.
# TODO: restore to settings.CORS_ORIGINS once production is confirmed working.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# ─── Routers ─────────────────────────────────────────────────────────────────
app.include_router(api_router, prefix=settings.API_V1_STR)


# ─── Root health check ────────────────────────────────────────────────────────
@app.get("/health", tags=["health"], summary="Health check (Render)")
@app.get("/api/v1/health", tags=["health"], summary="Health check")
async def health_check() -> dict:
    """Returns service health status."""
    return {
        "status": "ok",
        "project_name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "llm_provider": settings.LLM_PROVIDER,
        "llm_model": settings.LLM_MODEL,
        "embedding_model": settings.EMBEDDING_MODEL,
    }


# ─── Global exception handler ────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception) -> JSONResponse:
    from app.core.middleware import request_id_var
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    
    # Unhandled-exception responses are produced by Starlette's outermost
    # ServerErrorMiddleware, which sits OUTSIDE CORSMiddleware. Without these
    # headers the browser hides the 500 and reports a network/CORS failure.
    origin = request.headers.get("origin")
    cors_headers = (
        {"Access-Control-Allow-Origin": origin, "Access-Control-Allow-Credentials": "true", "Vary": "Origin"}
        if origin
        else {}
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": f"Server error: {str(exc)}",
            "type": type(exc).__name__,
        },
        headers=cors_headers,
    )

@app.on_event("startup")
async def startup_create_tables():
    from app.db.session import engine
    from app.db.base import Base
    import app.db.models  # noqa: F401  (registers all models on Base.metadata)

    print("🔥 Creating database tables if they don't exist...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Database tables verified/created.")
    logger.info("Application startup complete")
