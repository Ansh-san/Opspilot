"""EvaluationRun ORM model — AI quality evaluation metrics per AI run."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    ai_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_runs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # ─── Quality scores (0.0 – 1.0) ──────────────────────────────────────────
    retrieval_relevance: Mapped[float | None] = mapped_column(Float, nullable=True)
    answer_groundedness: Mapped[float | None] = mapped_column(Float, nullable=True)
    classification_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    tool_success_rate: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ─── Performance ──────────────────────────────────────────────────────────
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ─── Human override ───────────────────────────────────────────────────────
    human_override: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
