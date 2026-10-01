"""
Audit service — append-only audit log writer.

Provides a simple interface for all parts of the system to record
important events without coupling to the ORM directly.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit_log import ActorType, AuditLog

logger = logging.getLogger(__name__)


class AuditService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def log(
        self,
        org_id: uuid.UUID,
        event_type: str,
        resource_type: str,
        resource_id: uuid.UUID | None = None,
        actor_id: uuid.UUID | None = None,
        actor_type: ActorType = ActorType.SYSTEM,
        details: dict[str, Any] | None = None,
        ip_address: str | None = None,
    ) -> AuditLog:
        """
        Append an event to the audit log.

        Parameters:
            event_type: dot-notation event, e.g. "user.login", "ticket.created"
            resource_type: e.g. "user", "ticket", "approval"
            resource_id: UUID of the affected resource (if applicable)
            actor_id: UUID of the user / system / AI acting
            actor_type: ActorType enum value
            details: arbitrary JSON dict (immutable snapshot)
            ip_address: optional requester IP
        """
        entry = AuditLog(
            id=uuid.uuid4(),
            org_id=org_id,
            actor_id=actor_id,
            actor_type=actor_type,
            event_type=event_type,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            ip_address=ip_address,
        )
        self._db.add(entry)
        # Note: do NOT commit here — let the calling service/route commit the
        # transaction so that audit and business records are committed atomically.
        logger.debug(
            "Audit event",
            extra={
                "event_type": event_type,
                "resource_type": resource_type,
                "resource_id": str(resource_id) if resource_id else None,
            },
        )
        return entry
