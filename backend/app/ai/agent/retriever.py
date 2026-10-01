"""
Phase 4 — Agent-facing RAG retriever.

The Phase 3 KnowledgeService.search() requires a full User object for RBAC
and audit logging.  Inside the agent graph, we only have org_id (from the ticket).

This module provides AgentRetriever — a thin async wrapper that:
  1. Embeds the query using the configured embedding provider.
  2. Executes the same cosine-similarity SQL as KnowledgeService.search(), but
     accepts org_id directly instead of a User object.
  3. Strictly filters by org_id (multi-tenant isolation guaranteed).
  4. Returns plain dicts — no ORM objects — to avoid lazy-load issues inside
     the LangGraph async context.

Usage:
    retriever = AgentRetriever(db_session)
    chunks = await retriever.retrieve(
        query="redis cache miss",
        org_id=uuid.UUID("…"),
        top_k=5,
    )
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.rag.embedder import get_embedder

logger = logging.getLogger(__name__)


def _vector_to_pg(vec: list[float]) -> str:
    """Serialise a Python float list to a PostgreSQL vector literal '[1.0,2.0,…]'."""
    return "[" + ",".join(f"{v:.8f}" for v in vec) + "]"


class AgentRetriever:
    """
    Async semantic retriever for the agent graph.

    Shares the same SQL + pgvector logic as KnowledgeService.search() but
    accepts org_id directly so nodes don't need a full User object.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def retrieve(
        self,
        query: str,
        org_id: uuid.UUID,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Embed query and perform cosine similarity search, strictly scoped to org_id.

        Returns:
            List of dicts with keys:
              chunk_id, document_id, document_title, content,
              similarity_score, page, section, source_title
        """
        if not query.strip():
            logger.warning("AgentRetriever.retrieve() called with empty query — skipping.")
            return []

        top_k = max(1, min(top_k, 10))

        embedder = get_embedder()
        query_vec = await embedder.embed_one(query)
        vec_literal = _vector_to_pg(query_vec)

        # Inline the vector literal to avoid asyncpg :param::type casting errors.
        sql = text(
            f"""
            SELECT
                kc.id             AS chunk_id,
                kc.document_id    AS document_id,
                kd.title          AS document_title,
                kc.content        AS content,
                1 - (kc.embedding <=> '{vec_literal}'::vector) AS similarity_score,
                (kc.chunk_metadata->>'page')::int              AS page,
                kc.chunk_metadata->>'section'                  AS section,
                kc.chunk_metadata->>'source_title'             AS source_title
            FROM knowledge_chunks kc
            JOIN knowledge_documents kd ON kd.id = kc.document_id
            WHERE kc.org_id   = :org_id
              AND kd.status   = 'ready'
              AND kc.embedding IS NOT NULL
            ORDER BY kc.embedding <=> '{vec_literal}'::vector
            LIMIT :top_k
            """
        )

        result = await self._db.execute(sql, {"org_id": org_id, "top_k": top_k})
        rows = result.mappings().all()
        # Convert UUID objects → str so hits can be safely stored in JSONB columns.
        hits = []
        for row in rows:
            hit = {}
            for k, v in dict(row).items():
                hit[k] = str(v) if isinstance(v, uuid.UUID) else v
            hits.append(hit)

        logger.info(
            "AgentRetriever: query=%r org=%s top_k=%d → %d hits",
            query[:80], org_id, top_k, len(hits),
        )
        return hits

