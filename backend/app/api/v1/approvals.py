import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.db.models.user import User
from app.schemas.approval import ApprovalActionRequest, ApprovalRequestResponse
from app.services.approval_service import ApprovalService

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("", response_model=list[ApprovalRequestResponse])
async def list_approvals(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status: Annotated[str | None, Query(description="Filter by status (pending, approved, rejected, executed, failed)")] = None,
):
    """List approval requests for the organization."""
    service = ApprovalService(db)
    return await service.list_approvals(current_user, status_filter=status)


@router.get("/{id}", response_model=ApprovalRequestResponse)
async def get_approval(
    id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get a specific approval request."""
    service = ApprovalService(db)
    return await service.get_approval(id, current_user)


@router.post("/{id}/approve")
async def approve_request(
    id: uuid.UUID,
    payload: ApprovalActionRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Approve a pending request and execute the tool."""
    service = ApprovalService(db)
    result = await service.approve_request(id, current_user, payload.note)
    return result


@router.post("/{id}/reject")
async def reject_request(
    id: uuid.UUID,
    payload: ApprovalActionRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Reject a pending request."""
    service = ApprovalService(db)
    await service.reject_request(id, current_user, payload.note)
    return {"status": "rejected"}
