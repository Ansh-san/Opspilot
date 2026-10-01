"""
Auth service — business logic for registration, login, and token refresh.
Keeps route handlers thin.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.db.models.organization import Organization
from app.db.models.user import User, UserRole
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse

logger = logging.getLogger(__name__)


class AuthError(Exception):
    """Raised for authentication / authorisation failures."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ─── Registration ─────────────────────────────────────────────────────────
    async def register(self, data: RegisterRequest) -> tuple[User, Organization]:
        """
        Create a new organization and the first admin user.

        Raises:
            AuthError: if the slug or email is already taken.
        """
        # Check slug uniqueness
        existing_org = await self._db.scalar(
            select(Organization).where(Organization.slug == data.org_slug)
        )
        if existing_org:
            raise AuthError(f"Organization slug '{data.org_slug}' is already taken.", 409)

        # Check email uniqueness
        existing_user = await self._db.scalar(
            select(User).where(User.email == data.email.lower())
        )
        if existing_user:
            raise AuthError("An account with this email already exists.", 409)

        # Create org
        org = Organization(
            id=uuid.uuid4(),
            name=data.org_name,
            slug=data.org_slug,
            settings={},
        )
        self._db.add(org)
        await self._db.flush()  # Get org.id without committing

        # Create admin user
        user = User(
            id=uuid.uuid4(),
            org_id=org.id,
            email=data.email.lower(),
            hashed_password=hash_password(data.password),
            full_name=data.full_name,
            role=UserRole.ADMIN,
            is_active=True,
        )
        self._db.add(user)
        await self._db.flush()

        logger.info(
            "New organization registered",
            extra={"org_id": str(org.id), "user_id": str(user.id)},
        )

        return user, org

    # ─── Login ────────────────────────────────────────────────────────────────
    async def login(self, data: LoginRequest) -> tuple[User, TokenResponse]:
        """
        Authenticate a user and return JWT tokens.

        Raises:
            AuthError: if credentials are invalid or user is inactive.
        """
        user = await self._db.scalar(
            select(User).where(User.email == data.email.lower())
        )

        if not user or not verify_password(data.password, user.hashed_password):
            raise AuthError("Invalid email or password.", 401)

        if not user.is_active:
            raise AuthError("Your account has been deactivated. Contact your admin.", 403)

        # Update last_login
        user.last_login = datetime.now(timezone.utc)
        await self._db.flush()

        tokens = _build_token_response(user)
        logger.info("User logged in", extra={"user_id": str(user.id), "email": user.email})
        return user, tokens

    # ─── Refresh ──────────────────────────────────────────────────────────────
    async def refresh(self, refresh_token: str) -> TokenResponse:
        """
        Issue a new access token from a valid refresh token.

        Raises:
            AuthError: if the refresh token is invalid or the user is gone.
        """
        from jose import JWTError

        try:
            payload = decode_refresh_token(refresh_token)
        except JWTError as exc:
            raise AuthError(f"Invalid refresh token: {exc}", 401)

        user_id = uuid.UUID(payload["sub"])
        user = await self._db.scalar(
            select(User).where(User.id == user_id, User.is_active == True)  # noqa: E712
        )
        if not user:
            raise AuthError("User not found or inactive.", 401)

        return _build_token_response(user)


# ─── Helpers ──────────────────────────────────────────────────────────────────
def _build_token_response(user: User) -> TokenResponse:
    access = create_access_token(user.id, user.org_id)
    refresh = create_refresh_token(user.id, user.org_id)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
