"""Evaluations API endpoints for OpsPilot Phase 6."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import get_current_user, get_db
from app.db.models.user import User
from app.db.models.ai_run import AIRun
from app.ai.evaluation.registry import eval_registry

router = APIRouter(prefix="/evaluations", tags=["evaluations"])


@router.get("")
async def list_evaluations(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """List historical evaluations based on AI Runs."""
    stmt = (
        select(AIRun)
        .where(AIRun.org_id == current_user.org_id)
        .where(AIRun.is_synthetic == False)
        .where(AIRun.evaluation_results.is_not(None))
        .order_by(AIRun.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    runs = result.scalars().all()
    
    return {
        "items": [
            {
                "ai_run_id": str(r.id),
                "ticket_id": str(r.ticket_id) if r.ticket_id else None,
                "created_at": r.created_at,
                "evaluation_results": r.evaluation_results,
            }
            for r in runs
        ]
    }


@router.get("/{ai_run_id}")
async def get_evaluation(
    ai_run_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Get specific evaluation results for an AI run."""
    stmt = (
        select(AIRun)
        .where(AIRun.id == ai_run_id, AIRun.org_id == current_user.org_id)
    )
    result = await db.execute(stmt)
    ai_run = result.scalar_one_or_none()

    if not ai_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI Run not found.",
        )

    return {
        "ai_run_id": str(ai_run.id),
        "ticket_id": str(ai_run.ticket_id) if ai_run.ticket_id else None,
        "created_at": ai_run.created_at,
        "evaluation_results": ai_run.evaluation_results or [],
    }


@router.post("/run/{ai_run_id}")
async def run_evaluation(
    ai_run_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Manually trigger the evaluation registry for a specific historical AI run."""
    
    # 1. Fetch the run with ticket and approval
    stmt = (
        select(AIRun)
        .options(
            selectinload(AIRun.ticket),
            selectinload(AIRun.approval),
        )
        .where(AIRun.id == ai_run_id, AIRun.org_id == current_user.org_id)
    )
    result = await db.execute(stmt)
    ai_run = result.scalar_one_or_none()

    if not ai_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI Run not found.",
        )

    # 2. Construct the ai_run_data payload matching the expected format
    agent_trace = ai_run.agent_trace or {}
    
    # Convert ticket to dict safely
    ticket_data = None
    if ai_run.ticket:
        ticket_data = {
            "id": str(ai_run.ticket.id),
            "title": ai_run.ticket.title,
            "description": ai_run.ticket.description,
            "category": ai_run.ticket.category,
            "priority": ai_run.ticket.priority.value if ai_run.ticket.priority else None,
            "severity": ai_run.ticket.severity.value if ai_run.ticket.severity else None,
            "affected_service": ai_run.ticket.affected_service,
        }

    approval_data = None
    if ai_run.approval:
        approval_data = {
            "id": str(ai_run.approval.id),
            "status": ai_run.approval.status.value if ai_run.approval.status else None,
        }

    eval_payload = {
        "ticket_data": ticket_data,
        "retrieved_documents": agent_trace.get("retrieved_documents", []),
        "classification": agent_trace.get("classification"),
        "diagnosis": agent_trace.get("diagnosis"),
        "recommendation": agent_trace.get("recommendation"),
        "action_proposal": agent_trace.get("action_proposal"),
        "confidence": ai_run.confidence,
        "risk_level": ai_run.risk_level.value if ai_run.risk_level else None,
        "policy_result": ai_run.policy_result or {},
        "approval_data": approval_data,
    }

    # 3. Run the registry
    evaluation_results = eval_registry.run_all(eval_payload)

    # 4. Save to DB
    ai_run.evaluation_results = evaluation_results
    await db.commit()

    return {
        "ai_run_id": str(ai_run.id),
        "evaluation_results": evaluation_results,
    }
