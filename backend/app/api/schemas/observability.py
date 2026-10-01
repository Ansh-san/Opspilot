"""Pydantic schemas for the Observability APIs."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict


class ObservabilityKPIs(BaseModel):
    total_runs: int
    success_rate: Optional[float] = None
    avg_latency: Optional[float] = None
    p50_latency: Optional[float] = None
    p95_latency: Optional[float] = None
    total_tokens: int
    total_cost: float
    approval_rate: Optional[float] = None
    rejection_rate: Optional[float] = None
    tool_success_rate: Optional[float] = None
    blocked_count: int


class AIRunSummary(BaseModel):
    id: uuid.UUID
    ticket_id: Optional[uuid.UUID] = None
    confidence: Optional[float] = None
    risk_level: Optional[str] = None
    latency_ms: Optional[int] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    estimated_cost_usd: Optional[float] = None
    model_used: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())


class TraceTicketSummary(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    priority: str

    model_config = ConfigDict(from_attributes=True)


class TraceApprovalSummary(BaseModel):
    id: uuid.UUID
    status: str
    proposed_action: str

    model_config = ConfigDict(from_attributes=True)


class TraceToolExecutionSummary(BaseModel):
    id: uuid.UUID
    tool_name: str
    status: str

    model_config = ConfigDict(from_attributes=True)


class AIRunTrace(AIRunSummary):
    agent_trace: Optional[Dict[str, Any]] = None
    decision: Optional[str] = None
    reasoning: Optional[str] = None
    evidence: Optional[List[Any]] = None
    policy_result: Optional[Dict[str, Any]] = None
    
    # Minimal relation outputs
    ticket: Optional[TraceTicketSummary] = None
    approval: Optional[TraceApprovalSummary] = None
    tool_executions: Optional[List[TraceToolExecutionSummary]] = None

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())
