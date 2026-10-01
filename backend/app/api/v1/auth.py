"""
Auth API routes — /api/v1/auth/*
"""

import logging

from fastapi import APIRouter, HTTPException, Request, status

from app.core.dependencies import CurrentUser, DBSession
from app.db.models.audit_log import ActorType
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)
from app.schemas.common import MessageResponse
from app.services.audit_service import AuditService
from app.services.auth_service import AuthError, AuthService
from app.core.rate_limiter import limiter
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new organization and admin user",
)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
async def register(
    body: RegisterRequest,
    request: Request,
    db: DBSession,
) -> UserOut:
    service = AuthService(db)
    audit = AuditService(db)

    try:
        user, org = await service.register(body)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))

    await audit.log(
        org_id=org.id,
        event_type="user.registered",
        resource_type="user",
        resource_id=user.id,
        actor_id=user.id,
        actor_type=ActorType.USER,
        details={"email": user.email, "org_slug": org.slug},
        ip_address=_get_ip(request),
    )

    return UserOut.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and receive JWT tokens",
)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
async def login(
    body: LoginRequest,
    request: Request,
    db: DBSession,
) -> TokenResponse:
    service = AuthService(db)
    audit = AuditService(db)

    try:
        user, tokens = await service.login(body)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))

    await audit.log(
        org_id=user.org_id,
        event_type="user.login",
        resource_type="user",
        resource_id=user.id,
        actor_id=user.id,
        actor_type=ActorType.USER,
        details={"email": user.email},
        ip_address=_get_ip(request),
    )

    return tokens


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token using a refresh token",
)
async def refresh(
    body: RefreshRequest,
    db: DBSession,
) -> TokenResponse:
    service = AuthService(db)

    try:
        tokens = await service.refresh(body.refresh_token)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))

    return tokens


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Logout (stateless — client should discard tokens)",
)
async def logout(current_user: CurrentUser) -> MessageResponse:
    # JWT is stateless; logout is handled client-side.
    # In production, add tokens to a Redis blacklist here.
    logger.info("User logged out", extra={"user_id": str(current_user.id)})
    return MessageResponse(message="Logged out successfully.")


@router.get(
    "/me",
    response_model=UserOut,
    summary="Get the currently authenticated user",
)
async def get_me(current_user: CurrentUser) -> UserOut:
    return UserOut.model_validate(current_user)


# ─── Helpers ──────────────────────────────────────────────────────────────────
def _get_ip(request: Request) -> str | None:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None
