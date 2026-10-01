"""
Pydantic schemas for the Knowledge Base API (Phase 3).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.db.models.knowledge import DocumentSourceType, DocumentStatus


# ─── Document response schemas ────────────────────────────────────────────────

class KnowledgeChunkResponse(BaseModel):
    id: uuid.UUID
    chunk_index: int
    content: str
    chunk_metadata: dict[str, Any]

    model_config = {"from_attributes": True}


class KnowledgeDocumentResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    title: str
    source_type: DocumentSourceType
    source_path: str | None
    status: DocumentStatus
    chunk_count: int
    uploaded_by: uuid.UUID
    created_at: datetime
    chunks: list[KnowledgeChunkResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class KnowledgeDocumentListItem(BaseModel):
    """Lightweight response for list endpoints (no chunks)."""
    id: uuid.UUID
    org_id: uuid.UUID
    title: str
    source_type: DocumentSourceType
    status: DocumentStatus
    chunk_count: int
    uploaded_by: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Search schemas ───────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000, description="Natural-language query")
    top_k: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Number of results to return (max 10)",
    )

    @field_validator("query")
    @classmethod
    def query_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("query must not be blank")
        return v.strip()


class SearchHit(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    content: str
    similarity_score: float
    page: int | None = None
    section: str | None = None
    source_title: str | None = None


class SearchResponse(BaseModel):
    query: str
    top_k: int
    results: list[SearchHit]
