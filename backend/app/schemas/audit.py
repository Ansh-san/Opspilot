from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class AuditLogResponse(BaseModel):
    id: UUID
    actor_id: UUID | None
    actor_type: str
    event_type: str
    resource_type: str
    resource_id: UUID | None
    details: dict[str, Any]
    ip_address: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator("ip_address", mode="before")
    @classmethod
    def coerce_ip_address(cls, v: object) -> str | None:
        """SQLAlchemy / psycopg2 may return IPv4Address/IPv6Address objects.
        Coerce to string so Pydantic V2 validation always succeeds."""
        if v is None:
            return None
        return str(v)


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
