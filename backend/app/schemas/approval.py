from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ApprovalRequestResponse(BaseModel):
    id: UUID
    org_id: UUID
    ticket_id: UUID
    ai_run_id: UUID | None
    
    proposed_action: str
    action_args: dict[str, Any]
    reason: str
    evidence: list[str]
    confidence: float | None
    risk_level: str
    
    status: str
    requested_by_id: UUID
    reviewed_by_id: UUID | None
    reviewed_at: datetime | None
    review_note: str | None
    
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApprovalActionRequest(BaseModel):
    note: str = ""


class ApprovalCreateRequest(BaseModel):
    """Human-initiated request to route an AI recommendation for approval."""

    ticket_id: UUID
    ai_run_id: UUID | None = None
    recommended_action: str = Field(min_length=1, max_length=255)
    risk_level: str = "medium"
    reason: str = ""
    confidence: float | None = None
    evidence: list[str] = Field(default_factory=list)
