"""
Tickets API routes — /api/v1/tickets/*
"""

import uuid
import logging

from fastapi import APIRouter, Depends, Query, Request, status, Response

from app.core.dependencies import CurrentUser, DBSession, require_agent_or_above
from app.core.rate_limiter import limiter
from app.core.config import settings
from app.schemas.agent import AgentRunResponse, AIRunDetail, AIRunListResponse
from app.schemas.ticket import (
    CommentCreate,
    CommentResponse,
    TicketCreate,
    TicketListResponse,
    TicketResponse,
    TicketUpdate,
)
from app.schemas.common import MessageResponse
from app.db.models.ticket import TicketStatus
from app.services.agent_service import AgentService
from app.services.ticket_service import TicketService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tickets", tags=["tickets"])


# ─── Ticket CRUD ─────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=TicketListResponse,
    summary="List tickets for the current organization",
)
async def list_tickets(
    db: DBSession,
    current_user: CurrentUser,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: TicketStatus | None = Query(None, description="Filter by status"),
    priority: str | None = Query(None, description="Filter by priority"),
) -> TicketListResponse:
    service = TicketService(db)
    result = await service.get_tickets(
        current_user=current_user,
        skip=skip,
        limit=limit,
        status_filter=status,
        priority_filter=priority,
    )
    return TicketListResponse(**result)


@router.post(
    "",
    response_model=TicketResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new ticket",
)
async def create_ticket(
    body: TicketCreate,
    db: DBSession,
    current_user: CurrentUser,
) -> TicketResponse:
    service = TicketService(db)
    ticket = await service.create_ticket(body, current_user)
    return TicketResponse.model_validate(ticket)


@router.get(
    "/{ticket_id}",
    response_model=TicketResponse,
    summary="Get a single ticket by ID",
)
async def get_ticket(
    ticket_id: uuid.UUID,
    db: DBSession,
    current_user: CurrentUser,
) -> TicketResponse:
    service = TicketService(db)
    ticket = await service.get_ticket(ticket_id, current_user)
    return TicketResponse.model_validate(ticket)


@router.patch(
    "/{ticket_id}",
    response_model=TicketResponse,
    summary="Update a ticket (including status transitions)",
)
async def update_ticket(
    ticket_id: uuid.UUID,
    body: TicketUpdate,
    db: DBSession,
    current_user: CurrentUser,
) -> TicketResponse:
    service = TicketService(db)
    ticket = await service.update_ticket(ticket_id, body, current_user)
    return TicketResponse.model_validate(ticket)


@router.delete(
    "/{ticket_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete a ticket (agent or above)",
    dependencies=[Depends(require_agent_or_above())],
)
async def delete_ticket(
    ticket_id: uuid.UUID,
    db: DBSession,
    current_user: CurrentUser,
) -> Response:
    service = TicketService(db)
    await service.delete_ticket(ticket_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)



# ─── Comments ────────────────────────────────────────────────────────────────

@router.get(
    "/{ticket_id}/comments",
    response_model=list[CommentResponse],
    summary="List comments on a ticket",
)
async def list_comments(
    ticket_id: uuid.UUID,
    db: DBSession,
    current_user: CurrentUser,
) -> list[CommentResponse]:
    service = TicketService(db)
    comments = await service.list_comments(ticket_id, current_user)
    return [CommentResponse.model_validate(c) for c in comments]


@router.post(
    "/{ticket_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a comment to a ticket",
)
async def add_comment(
    ticket_id: uuid.UUID,
    body: CommentCreate,
    db: DBSession,
    current_user: CurrentUser,
) -> CommentResponse:
    service = TicketService(db)
    comment = await service.add_comment(ticket_id, body, current_user)
    return CommentResponse.model_validate(comment)



# ─── AI Agent ────────────────────────────────────────────────────────────────

@router.post(
    "/{ticket_id}/run-agent",
    response_model=AgentRunResponse,
    summary="Run the AI agent on a ticket (Phase 4)",
    description=(
        "Triggers the LangGraph agent pipeline: classify → retrieve knowledge → "
        "diagnose → recommend → finalize.  "
        "Returns structured classification, diagnosis, recommendation, confidence, "
        "and risk level.  All LLM calls are async and non-blocking."
    ),
)
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
async def run_agent(
    ticket_id: uuid.UUID,
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
) -> AgentRunResponse:
    service = AgentService(db)
    result = await service.run_on_ticket(ticket_id, current_user)
    return AgentRunResponse(**result)

