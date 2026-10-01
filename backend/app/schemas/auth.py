"""
Auth Pydantic v2 schemas — request/response models for authentication endpoints.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.db.models.user import UserRole


# ─── Registration ─────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    """Create a new organization with the first admin user."""

    org_name: str = Field(..., min_length=2, max_length=255, examples=["Acme Corp"])
    org_slug: str = Field(
        ...,
        min_length=2,
        max_length=100,
        pattern=r"^[a-z0-9-]+$",
        examples=["acme-corp"],
        description="Lowercase letters, numbers, hyphens only.",
    )
    full_name: str = Field(..., min_length=2, max_length=255, examples=["Jane Smith"])
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit.")
        return v


# ─── Login ────────────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


# ─── Refresh ──────────────────────────────────────────────────────────────────
class RefreshRequest(BaseModel):
    refresh_token: str


# ─── Current user ─────────────────────────────────────────────────────────────
class UserOut(BaseModel):
    """Safe user representation — no password hash exposed."""

    id: uuid.UUID
    org_id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    last_login: datetime | None = None

    model_config = {"from_attributes": True}
