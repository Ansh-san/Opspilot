"""Observability and Evaluation API endpoints."""

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.observability import AIRunSummary, AIRunTrace, ObservabilityKPIs
from app.core.dependencies import get_current_user, get_db
from app.db.models.user import User
from app.services.observability_service import ObservabilityService


router = APIRouter(prefix="/observability", tags=["Observability"])


@router.get(
    "/metrics",
    response_model=ObservabilityKPIs,
    summary="Get aggregated AI KPIs",
    description="Returns aggregated metrics across all AI agent runs for the organization. Uses efficient SQL aggregation.",
)
async def get_observability_metrics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = ObservabilityService(db)
    return await service.get_kpis(org_id=current_user.org_id)


@router.get(
    "/runs",
    response_model=List[AIRunSummary],
    summary="List paginated AI runs",
    description="Returns a paginated list of historical AI agent runs for the organization.",
)
async def list_ai_runs(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ObservabilityService(db)
    return await service.list_runs(org_id=current_user.org_id, limit=limit, offset=offset)


@router.get(
    "/runs/{ai_run_id}",
    response_model=AIRunTrace,
    summary="Get full AI run trace",
    description="Fetches a complete execution trace of an AI run, eagerly loading associated tickets, approvals, and tool executions to prevent N+1 queries.",
)
async def get_ai_run_trace(
    ai_run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ObservabilityService(db)
    trace = await service.get_run_trace(org_id=current_user.org_id, ai_run_id=ai_run_id)
    if not trace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI run not found in this organization.",
        )
    return trace
