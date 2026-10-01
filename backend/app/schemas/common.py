"""Common Pydantic schemas shared across the application."""

from __future__ import annotations

from pydantic import BaseModel


class MessageResponse(BaseModel):
    """Generic message response."""
    message: str


class ErrorDetail(BaseModel):
    """Standard error response body."""
    detail: str
