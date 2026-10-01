from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.db.models.audit_log import AuditLog
from app.db.models.user import User
from app.schemas.audit import AuditLogListResponse

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    event_type: Annotated[str | None, Query()] = None,
    resource_type: Annotated[str | None, Query()] = None,
):
    """
    List audit logs for the current user's organization.
    Paginated and optionally filtered by event_type or resource_type.
    """
    query = select(AuditLog).where(AuditLog.org_id == current_user.org_id)

    if event_type:
        query = query.where(AuditLog.event_type == event_type)
    if resource_type:
        query = query.where(AuditLog.resource_type == resource_type)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar_one_or_none() or 0

    # Paginate
    query = query.order_by(AuditLog.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    return AuditLogListResponse(
        items=list(items),
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
