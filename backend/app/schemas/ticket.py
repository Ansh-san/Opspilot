"""
Ticket Pydantic v2 schemas — request/response models for /api/v1/tickets/*.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.db.models.ticket import TicketPriority, TicketSeverity, TicketStatus


# ─── Comment schemas ──────────────────────────────────────────────────────────

class CommentCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=10_000)


class CommentResponse(BaseModel):
    id: uuid.UUID
    ticket_id: uuid.UUID
    author_id: uuid.UUID
    body: str
    is_ai_generated: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Ticket schemas ───────────────────────────────────────────────────────────

class TicketCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=500)
    description: str = Field(..., min_length=10)
    category: str | None = Field(None, max_length=100)
    priority: TicketPriority = TicketPriority.MEDIUM
    severity: TicketSeverity | None = None
    affected_service: str | None = Field(None, max_length=255)


class TicketUpdate(BaseModel):
    title: str | None = Field(None, min_length=3, max_length=500)
    description: str | None = Field(None, min_length=10)
    category: str | None = Field(None, max_length=100)
    priority: TicketPriority | None = None
    severity: TicketSeverity | None = None
    status: TicketStatus | None = None
    affected_service: str | None = Field(None, max_length=255)
    assigned_agent_id: uuid.UUID | None = None


class TicketResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    title: str
    description: str
    category: str | None
    priority: TicketPriority
    severity: TicketSeverity | None
    status: TicketStatus
    requester_id: uuid.UUID
    assigned_agent_id: uuid.UUID | None
    affected_service: str | None
    ai_confidence: float | None
    ai_recommendation: str | None
    ai_diagnosis: dict | None
    comments: list[CommentResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TicketListResponse(BaseModel):
    items: list[TicketResponse]
    total: int
    page: int
    total_pages: int
