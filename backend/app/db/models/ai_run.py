"""AIRun ORM model — records every AI agent execution."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.models.ticket import Ticket
    from app.db.models.approval import ApprovalRequest
    from app.db.models.tool_execution import ToolExecution

from app.db.base import Base


class RiskLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    BLOCKED = "blocked"


class AIRun(Base):
    __tablename__ = "ai_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    ticket_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tickets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ─── Agent output ─────────────────────────────────────────────────────────
    agent_trace: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    decision: Mapped[str | None] = mapped_column(Text, nullable=True)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_level: Mapped[RiskLevel | None] = mapped_column(
        Enum(RiskLevel, name="risklevel", values_callable=lambda x: [e.value for e in x]), nullable=True
    )
    policy_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    evaluation_results: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # ─── Usage / cost tracking ────────────────────────────────────────────────
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    is_synthetic: Mapped[bool] = mapped_column(
        Boolean, server_default="false", default=False, nullable=False
    )

    # ─── Relationships ────────────────────────────────────────────────────────
    ticket: Mapped["Ticket"] = relationship("Ticket", back_populates="ai_runs")
    approval: Mapped["ApprovalRequest"] = relationship("ApprovalRequest", back_populates="ai_run", uselist=False)
    tool_executions: Mapped[list["ToolExecution"]] = relationship("ToolExecution", back_populates="ai_run")
