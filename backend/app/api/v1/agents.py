"""
Phase 4 — Agents API routes: /api/v1/agents/*

Endpoints:
  GET  /agents/runs              — paginated run history (filterable)
  GET  /agents/runs/{id}         — single run detail

The POST /tickets/{id}/run-agent endpoint lives in tickets.py.

All endpoints enforce strict org_id isolation via the CurrentUser dependency.
No stack traces are ever returned to the client.
"""

import uuid

from fastapi import APIRouter, Query

from app.core.dependencies import CurrentUser, DBSession
from app.schemas.agent import AIRunDetail, AIRunListResponse, AIRunSummary
from app.services.agent_service import AgentService

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get(
    "/runs",
    response_model=AIRunListResponse,
    summary="List agent run history for this organization",
    description=(
        "Returns a paginated list of all AI agent runs within the current organization. "
        "Optionally filter by ticket_id, date range, or minimum confidence score. "
        "Results are ordered by most recent first."
    ),
)
async def list_agent_runs(
    db: DBSession,
    current_user: CurrentUser,
    ticket_id: uuid.UUID | None = Query(
        None, description="Filter runs for a specific ticket"
    ),
    min_confidence: float | None = Query(
        None, ge=0.0, le=1.0, description="Return runs with confidence ≥ this value"
    ),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(20, ge=1, le=100, description="Results per page"),
) -> AIRunListResponse:
    service = AgentService(db)
    result = await service.list_runs(
        current_user=current_user,
        ticket_id=ticket_id,
        min_confidence=min_confidence,
        page=page,
        page_size=page_size,
    )
    return AIRunListResponse(
        items=[
            AIRunSummary(
                id=str(run.id),
                ticket_id=str(run.ticket_id) if run.ticket_id else None,
                confidence=run.confidence,
                risk_level=run.risk_level.value if run.risk_level else None,
                decision=run.decision,
                latency_ms=run.latency_ms,
                model_used=run.model_used,
                created_at=run.created_at,
                approval_status=run.approval.status.value if run.approval else None,
                execution_result=run.tool_executions[0].status.value if run.tool_executions else None,
            )
            for run in result["items"]
        ],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        total_pages=result["total_pages"],
    )


@router.get(
    "/runs/{run_id}",
    response_model=AIRunDetail,
    summary="Get a single agent run by ID",
    description=(
        "Returns full detail of a specific agent run including the agent trace, "
        "classification, diagnosis, recommendation, evidence, and usage statistics. "
        "Strictly scoped to the current organization — returns 404 if the run "
        "belongs to another org."
    ),
)
async def get_agent_run(
    run_id: uuid.UUID,
    db: DBSession,
    current_user: CurrentUser,
) -> AIRunDetail:
    service = AgentService(db)
    run = await service.get_run(run_id, current_user)

    # Extract structured outputs from agent_trace (stored there for auditability)
    trace = run.agent_trace or {}

    return AIRunDetail(
        id=str(run.id),
        org_id=str(run.org_id),
        ticket_id=str(run.ticket_id) if run.ticket_id else None,
        agent_trace=trace,
        decision=run.decision,
        reasoning=run.reasoning,
        evidence=run.evidence,
        confidence=run.confidence,
        risk_level=run.risk_level.value if run.risk_level else None,
        policy_result=run.policy_result,
        classification=trace.get("classification"),
        diagnosis=trace.get("diagnosis"),
        recommendation=trace.get("recommendation"),
        input_tokens=run.input_tokens,
        output_tokens=run.output_tokens,
        latency_ms=run.latency_ms,
        model_used=run.model_used,
        created_at=run.created_at,
    )
