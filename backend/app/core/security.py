"""
OpsPilot — Security Utilities

Handles:
- Password hashing (bcrypt)
- JWT access and refresh token creation / verification
- Token payload types
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from jose import JWTError, jwt

from app.core.config import settings

# ─── Password hashing ─────────────────────────────────────────────────────────
import bcrypt as _bcrypt_lib


def hash_password(plain: str) -> str:
    """Return bcrypt hash of a plain-text password."""
    return _bcrypt_lib.hashpw(plain.encode(), _bcrypt_lib.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if plain matches the bcrypt hash."""
    return _bcrypt_lib.checkpw(plain.encode(), hashed.encode())


# ─── JWT ──────────────────────────────────────────────────────────────────────
_TOKEN_TYPE_ACCESS = "access"
_TOKEN_TYPE_REFRESH = "refresh"


def _create_token(
    data: dict[str, Any],
    token_type: str,
    expires_delta: timedelta,
) -> str:
    payload = data.copy()
    now = datetime.now(timezone.utc)
    payload.update(
        {
            "iat": now,
            "exp": now + expires_delta,
            "type": token_type,
        }
    )
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(user_id: UUID | str, org_id: UUID | str) -> str:
    """Create a short-lived JWT access token."""
    return _create_token(
        data={"sub": str(user_id), "org": str(org_id)},
        token_type=_TOKEN_TYPE_ACCESS,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(user_id: UUID | str, org_id: UUID | str) -> str:
    """Create a long-lived JWT refresh token."""
    return _create_token(
        data={"sub": str(user_id), "org": str(org_id)},
        token_type=_TOKEN_TYPE_REFRESH,
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str, expected_type: str = _TOKEN_TYPE_ACCESS) -> dict[str, Any]:
    """
    Decode and validate a JWT token.

    Raises:
        JWTError: if the token is invalid, expired, or has the wrong type.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise

    if payload.get("type") != expected_type:
        raise JWTError(f"Invalid token type. Expected '{expected_type}'.")

    return payload


def decode_access_token(token: str) -> dict[str, Any]:
    return decode_token(token, expected_type=_TOKEN_TYPE_ACCESS)


def decode_refresh_token(token: str) -> dict[str, Any]:
    return decode_token(token, expected_type=_TOKEN_TYPE_REFRESH)
