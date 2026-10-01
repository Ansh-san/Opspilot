"""
Ticket service — all business logic for the ticket lifecycle.

Design principles enforced here:
- RBAC: every query is scoped to current_user.org_id (multi-tenant safety).
- No N+1: all relationships are eagerly loaded via selectinload().
- Status workflow: only valid transitions are allowed.
- Atomic transactions: audit and business records committed together.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.audit_log import ActorType
from app.db.models.ticket import Ticket, TicketComment, TicketStatus
from app.db.models.user import User
from app.schemas.ticket import CommentCreate, TicketCreate, TicketUpdate
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

# ─── Status workflow DAG ──────────────────────────────────────────────────────
# Only the transitions listed here are permitted. Anything else → 400.
VALID_TRANSITIONS: dict[TicketStatus, list[TicketStatus]] = {
    TicketStatus.OPEN: [TicketStatus.INVESTIGATING, TicketStatus.IN_PROGRESS],
    TicketStatus.INVESTIGATING: [
        TicketStatus.IN_PROGRESS,
        TicketStatus.RESOLVED,
        TicketStatus.OPEN,
    ],
    TicketStatus.IN_PROGRESS: [TicketStatus.RESOLVED, TicketStatus.INVESTIGATING],
    TicketStatus.RESOLVED: [TicketStatus.CLOSED, TicketStatus.IN_PROGRESS],
    TicketStatus.CLOSED: [TicketStatus.OPEN],  # re-open path
}


def _assert_valid_transition(current: TicketStatus, new: TicketStatus) -> None:
    """Raise 400 if the status transition is not permitted."""
    allowed = VALID_TRANSITIONS.get(current, [])
    if new not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid status transition: '{current.value}' → '{new.value}'. "
                f"Allowed: {[s.value for s in allowed]}"
            ),
        )


def _ticket_stmt(org_id: uuid.UUID) -> Any:
    """Base SELECT statement — always org-scoped + eager-loads."""
    return (
        select(Ticket)
        .where(Ticket.org_id == org_id)
        .options(
            selectinload(Ticket.comments),
        )
    )


# ─── Service class ────────────────────────────────────────────────────────────

class TicketService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._audit = AuditService(db)

    # ── List ──────────────────────────────────────────────────────────────────
    async def get_tickets(
        self,
        current_user: User,
        skip: int = 0,
        limit: int = 20,
        status_filter: TicketStatus | None = None,
        priority_filter: str | None = None,
    ) -> dict:
        stmt = _ticket_stmt(current_user.org_id)

        if status_filter:
            stmt = stmt.where(Ticket.status == status_filter)
        if priority_filter:
            stmt = stmt.where(Ticket.priority == priority_filter.lower())

        stmt = stmt.order_by(Ticket.created_at.desc())

        # Paginated count (efficient — counts the filtered rows, not all)
        count_stmt = select(func.count()).select_from(
            stmt.with_only_columns(Ticket.id).subquery()
        )
        total: int = (await self._db.execute(count_stmt)).scalar() or 0

        result = await self._db.execute(stmt.offset(skip).limit(limit))
        tickets = result.scalars().all()

        return {
            "items": tickets,
            "total": total,
            "page": (skip // limit) + 1,
            "total_pages": max(1, (total + limit - 1) // limit),
        }

    # ── Get one ───────────────────────────────────────────────────────────────
    async def get_ticket(self, ticket_id: uuid.UUID, current_user: User) -> Ticket:
        result = await self._db.execute(
            _ticket_stmt(current_user.org_id).where(Ticket.id == ticket_id)
        )
        ticket = result.scalar_one_or_none()
        if ticket is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ticket {ticket_id} not found.",
            )
        return ticket

    # ── Create ────────────────────────────────────────────────────────────────
    async def create_ticket(
        self, body: TicketCreate, current_user: User
    ) -> Ticket:
        ticket_id = uuid.uuid4()
        ticket = Ticket(
            id=ticket_id,
            org_id=current_user.org_id,
            requester_id=current_user.id,
            status=TicketStatus.OPEN,
            **body.model_dump(),
        )
        self._db.add(ticket)

        await self._audit.log(
            org_id=current_user.org_id,
            event_type="ticket.created",
            resource_type="ticket",
            resource_id=ticket_id,
            actor_id=current_user.id,
            actor_type=ActorType.USER,
            details={"title": ticket.title, "priority": ticket.priority.value},
        )

        await self._db.commit()
        # Re-fetch with selectinload so Pydantic can access .comments synchronously
        return await self.get_ticket(ticket_id, current_user)

    # ── Update ────────────────────────────────────────────────────────────────
    async def update_ticket(
        self,
        ticket_id: uuid.UUID,
        body: TicketUpdate,
        current_user: User,
    ) -> Ticket:
        ticket = await self.get_ticket(ticket_id, current_user)
        updates = body.model_dump(exclude_none=True)
        old_status = ticket.status  # capture before any mutation

        # Validate status transition before applying any changes
        if "status" in updates and updates["status"] != ticket.status:
            _assert_valid_transition(ticket.status, updates["status"])

        for field, value in updates.items():
            setattr(ticket, field, value)

        # Audit status changes separately for better traceability
        if "status" in updates and ticket.status != old_status:
            await self._audit.log(
                org_id=current_user.org_id,
                event_type="ticket.status_changed",
                resource_type="ticket",
                resource_id=ticket.id,
                actor_id=current_user.id,
                actor_type=ActorType.USER,
                details={
                    "from": old_status.value,
                    "to": ticket.status.value,
                },
            )
        else:
            await self._audit.log(
                org_id=current_user.org_id,
                event_type="ticket.updated",
                resource_type="ticket",
                resource_id=ticket.id,
                actor_id=current_user.id,
                actor_type=ActorType.USER,
                details={"fields_changed": list(updates.keys())},
            )

        await self._db.commit()
        # Re-fetch with selectinload so Pydantic can access .comments synchronously
        return await self.get_ticket(ticket_id, current_user)

    # ── Delete ────────────────────────────────────────────────────────────────
    async def delete_ticket(
        self, ticket_id: uuid.UUID, current_user: User
    ) -> None:
        ticket = await self.get_ticket(ticket_id, current_user)
        await self._db.delete(ticket)

        await self._audit.log(
            org_id=current_user.org_id,
            event_type="ticket.deleted",
            resource_type="ticket",
            resource_id=ticket_id,
            actor_id=current_user.id,
            actor_type=ActorType.USER,
            details={"title": ticket.title},
        )

        await self._db.commit()

    # ── Comments ──────────────────────────────────────────────────────────────
    async def list_comments(
        self, ticket_id: uuid.UUID, current_user: User
    ) -> list[TicketComment]:
        ticket = await self.get_ticket(ticket_id, current_user)
        return list(ticket.comments)

    async def add_comment(
        self,
        ticket_id: uuid.UUID,
        body: CommentCreate,
        current_user: User,
        is_ai_generated: bool = False,
    ) -> TicketComment:
        # Verify ticket exists and belongs to org
        await self.get_ticket(ticket_id, current_user)

        comment = TicketComment(
            id=uuid.uuid4(),
            ticket_id=ticket_id,
            author_id=current_user.id,
            body=body.body,
            is_ai_generated=is_ai_generated,
        )
        self._db.add(comment)

        await self._audit.log(
            org_id=current_user.org_id,
            event_type="ticket.comment_added",
            resource_type="ticket",
            resource_id=ticket_id,
            actor_id=current_user.id,
            actor_type=ActorType.USER,
            details={"is_ai_generated": is_ai_generated},
        )

        await self._db.commit()
        await self._db.refresh(comment)
        return comment
