"""Ticket and TicketComment ORM models with status/priority/severity enums."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.models.ai_run import AIRun

from app.db.base import Base


class TicketStatus(str, enum.Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    WAITING_APPROVAL = "waiting_approval"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TicketSeverity(str, enum.Enum):
    S1 = "s1"
    S2 = "s2"
    S3 = "s3"
    S4 = "s4"


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    priority: Mapped[TicketPriority] = mapped_column(
        Enum(TicketPriority, name="ticketpriority", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=TicketPriority.MEDIUM,
    )
    severity: Mapped[TicketSeverity | None] = mapped_column(
        Enum(TicketSeverity, name="ticketseverity", values_callable=lambda x: [e.value for e in x]), nullable=True
    )
    status: Mapped[TicketStatus] = mapped_column(
        Enum(TicketStatus, name="ticketstatus", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=TicketStatus.OPEN,
        index=True,
    )
    requester_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
        index=True,
    )
    assigned_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    affected_service: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # ─── AI fields ────────────────────────────────────────────────────────────
    ai_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_diagnosis: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # ─── Relationships ────────────────────────────────────────────────────────
    comments: Mapped[list["TicketComment"]] = relationship(
        "TicketComment", back_populates="ticket", cascade="all, delete-orphan"
    )
    ai_runs: Mapped[list["AIRun"]] = relationship(
        "AIRun", back_populates="ticket", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Ticket id={self.id} status={self.status} priority={self.priority}>"


class TicketComment(Base):
    __tablename__ = "ticket_comments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ─── Relationships ────────────────────────────────────────────────────────
    ticket: Mapped["Ticket"] = relationship("Ticket", back_populates="comments")
