"""
Phase 4 — Pydantic API schemas for agent runs.

AgentRunResponse  — POST /tickets/{id}/run-agent
AIRunSummary      — used in paginated list responses
AIRunDetail       — GET /agents/runs/{id}
AIRunListResponse — GET /agents/runs (paginated)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, ConfigDict


# ─── Run response (returned immediately after execution) ─────────────────────

class AgentRunResponse(BaseModel):
    """Response returned by POST /tickets/{id}/run-agent."""
    model_config = ConfigDict(protected_namespaces=())

    ai_run_id: str
    ticket_id: str
    classification: dict[str, Any] | None = None
    diagnosis: dict[str, Any] | None = None
    recommendation: dict[str, Any] | None = None
    confidence: float | None = None
    risk_level: str | None = None
    requires_approval: bool = False
    insufficient_evidence: bool = False
    latency_ms: int | None = None
    model_used: str | None = None
    errors: list[str] = Field(default_factory=list)
    
    # Phase 5 Additions
    proposed_action: str | None = None
    action_arguments: dict[str, Any] | None = None
    approval_id: str | None = None
    approval_status: str | None = None


# ─── History schemas ──────────────────────────────────────────────────────────

class AIRunSummary(BaseModel):
    """Compact summary used in paginated list views."""

    id: str
    ticket_id: str | None = None
    confidence: float | None = None
    risk_level: str | None = None
    decision: str | None = None
    latency_ms: int | None = None
    model_used: str | None = None
    created_at: datetime
    approval_status: str | None = None
    execution_result: str | None = None

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())


class AIRunDetail(BaseModel):
    """Full detail returned by GET /agents/runs/{id}."""

    id: str
    org_id: str
    ticket_id: str | None = None

    # Agent output
    agent_trace: dict[str, Any] | None = None
    decision: str | None = None
    reasoning: str | None = None
    evidence: list[str] | None = None
    confidence: float | None = None
    risk_level: str | None = None
    policy_result: dict[str, Any] | None = None

    # Classification / diagnosis / recommendation snapshots
    classification: dict[str, Any] | None = None
    diagnosis: dict[str, Any] | None = None
    recommendation: dict[str, Any] | None = None

    # Usage
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int | None = None
    model_used: str | None = None

    created_at: datetime

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())


class AIRunListResponse(BaseModel):
    """Paginated list of agent run summaries."""

    items: list[AIRunSummary]
    total: int
    page: int
    page_size: int
    total_pages: int
