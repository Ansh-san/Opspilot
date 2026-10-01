"""
OpsPilot — FastAPI Dependency Injection

Provides reusable dependencies for:
- Database sessions
- Current user extraction from JWT
- Role-based access control (RBAC)
"""

from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.session import get_db
from app.db.models.user import User, UserRole

logger = logging.getLogger(__name__)

# HTTP Bearer token extractor
_bearer = HTTPBearer(auto_error=True)


# ─── Database session ─────────────────────────────────────────────────────────
DBSession = Annotated[AsyncSession, Depends(get_db)]


# ─── Authentication ───────────────────────────────────────────────────────────
async def get_current_user(
    db: DBSession,
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> User:
    """
    Decode the Bearer JWT and return the authenticated User.

    Raises HTTP 401 if the token is missing, invalid, or the user no longer exists.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(credentials.credentials)
        user_id_str: str | None = payload.get("sub")
        if not user_id_str:
            raise credentials_exception
        user_id = uuid.UUID(user_id_str)
    except (JWTError, ValueError):
        raise credentials_exception

    from sqlalchemy import select

    result = await db.execute(select(User).where(User.id == user_id, User.is_active == True))  # noqa: E712
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


# ─── Role-based access control ────────────────────────────────────────────────
def require_roles(*roles: UserRole):
    """
    Factory that returns a dependency which asserts the current user has one of
    the given roles.  Raises HTTP 403 otherwise.

    Usage:
        @router.delete("/...", dependencies=[Depends(require_roles(UserRole.ADMIN))])
    """

    async def _check_role(current_user: CurrentUser) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' is not permitted for this action.",
            )
        return current_user

    return _check_role


def require_admin():
    return require_roles(UserRole.ADMIN)


def require_manager_or_above():
    return require_roles(UserRole.ADMIN, UserRole.MANAGER)


def require_agent_or_above():
    return require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.AGENT)
