"""AuditLog ORM model — immutable event trail for all system activities."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ActorType(str, enum.Enum):
    USER = "user"
    SYSTEM = "system"
    AI = "ai"


class AuditLog(Base):
    """
    Audit logs are append-only. No UPDATE or DELETE is permitted on this table.
    Enforced by DB triggers in production; the application only inserts.
    """

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    actor_type: Mapped[ActorType] = mapped_column(
        Enum(ActorType, name="actortype", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=ActorType.SYSTEM,
    )

    # ─── Event classification ─────────────────────────────────────────────────
    # event_type follows dot-notation convention: "resource.action"
    # e.g. "ticket.created", "user.login", "approval.approved", "tool.executed"
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    # ─── Immutable snapshot ───────────────────────────────────────────────────
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
