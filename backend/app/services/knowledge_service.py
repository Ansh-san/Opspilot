"""
Knowledge document service — Phase 3 Knowledge Base.

Responsibilities:
  1. Validate uploaded file (type + size).
  2. Persist file to /app/data/uploads/{org_id}/{filename}.
  3. Create KnowledgeDocument record with status=PROCESSING + audit log.
  4. Extract text → chunk → generate embeddings → bulk-insert KnowledgeChunk rows.
  5. Update status to READY or FAILED + audit log.
  6. Semantic search: embed query → cosine similarity via pgvector, org-scoped.
  7. Audit log: knowledge.search events.

RBAC: every DB query is scoped to current_user.org_id (multi-tenant safety).
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.rag.embedder import get_embedder
from app.db.models.audit_log import ActorType
from app.db.models.knowledge import (
    DocumentSourceType,
    DocumentStatus,
    KnowledgeChunk,
    KnowledgeDocument,
)
from app.db.models.user import User
from app.services.audit_service import AuditService
from app.services.chunker import chunk_pages
from app.services.document_processor import get_processor

logger = logging.getLogger(__name__)

# ─── Constants ───────────────────────────────────────────────────────────────
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
UPLOAD_ROOT = Path("/app/data/uploads")
MAX_TOP_K = 10

ALLOWED_EXTENSIONS: dict[str, DocumentSourceType] = {
    ".pdf": DocumentSourceType.PDF,
    ".txt": DocumentSourceType.TXT,
    ".md": DocumentSourceType.MARKDOWN,
}


# ─── Validation helpers ──────────────────────────────────────────────────────

def _sanitize_filename(filename: str) -> str:
    """Sanitize the filename to prevent path traversal."""
    from werkzeug.utils import secure_filename
    safe = secure_filename(filename)
    return safe or "upload.txt"

def _validate_file(filename: str, content: bytes) -> tuple[str, DocumentSourceType]:
    """Validate extension and MIME type using python-magic."""
    import magic
    
    suffix = Path(filename).suffix.lower()
    source_type = ALLOWED_EXTENSIONS.get(suffix)
    if source_type is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported file type '{suffix}'. Allowed: PDF, TXT, MD.",
        )
        
    mime_type = magic.from_buffer(content, mime=True)
    
    # Map allowed source types to expected MIME prefixes/types
    if source_type == DocumentSourceType.PDF and mime_type != "application/pdf":
        raise HTTPException(status_code=422, detail="MIME type does not match PDF extension.")
    elif source_type in (DocumentSourceType.TXT, DocumentSourceType.MARKDOWN) and not mime_type.startswith("text/"):
        raise HTTPException(status_code=422, detail="MIME type does not match Text/Markdown extension.")
        
    return suffix, source_type


def _validate_size(size: int) -> None:
    if size > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the 10 MB limit (got {size / 1_048_576:.1f} MB).",
        )


# ─── Persistence helpers ─────────────────────────────────────────────────────

from app.services.storage import get_storage_provider


def _vector_to_pg(vec: list[float]) -> str:
    """Serialise a Python float list to PostgreSQL vector literal '[1.0,2.0,…]'."""
    return "[" + ",".join(f"{v:.8f}" for v in vec) + "]"


# ─── Main service ────────────────────────────────────────────────────────────

class KnowledgeService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._audit = AuditService(db)

    # ── Upload + process ─────────────────────────────────────────────────────

    async def upload_document(
        self,
        file: UploadFile,
        current_user: User,
    ) -> KnowledgeDocument:
        """
        Full ingestion pipeline:
          validate → save file → create doc → extract → chunk → embed → insert → READY/FAILED

        Status flow: PROCESSING → (READY | FAILED)
        Audit events: knowledge.document_uploaded, knowledge.document_processed
        """
        # 1. Validate
        content = await file.read()
        _validate_size(len(content))
        
        filename = _sanitize_filename(file.filename or "upload")
        _suffix, source_type = _validate_file(filename, content)

        # 2. Persist file via StorageProvider
        storage = get_storage_provider()
        file_path = storage.upload(content, current_user.org_id, filename)

        # 3. Create DB record (status = PROCESSING)
        doc = KnowledgeDocument(
            id=uuid.uuid4(),
            org_id=current_user.org_id,
            title=filename,
            source_type=source_type,
            source_path=file_path,
            status=DocumentStatus.PROCESSING,
            chunk_count=0,
            uploaded_by=current_user.id,
        )
        self._db.add(doc)

        # Audit: document uploaded
        await self._audit.log(
            org_id=current_user.org_id,
            event_type="knowledge.document_uploaded",
            resource_type="knowledge_document",
            resource_id=doc.id,
            actor_id=current_user.id,
            actor_type=ActorType.USER,
            details={
                "filename": filename,
                "source_type": source_type.value,
                "size_bytes": len(content),
            },
        )
        await self._db.commit()
        await self._db.refresh(doc)

        logger.info(
            "Document %s created (org=%s file=%s size=%d bytes)",
            doc.id, current_user.org_id, filename, len(content),
        )

        # 4. Extract → chunk → embed → insert (with error isolation)
        try:
            storage = get_storage_provider()
            content = storage.download(file_path)

            processor = get_processor(filename)
            raw_pages = processor.extract(content, filename)
            chunks = chunk_pages(raw_pages, doc.id, source_title=filename)

            chunk_texts = [c.content for c in chunks]
            embedder = get_embedder()
            embeddings = await embedder.embed_many(chunk_texts)

            import json as _json
            chunk_ids: list[uuid.UUID] = []
            for c in chunks:
                chunk_id = uuid.uuid4()
                chunk_ids.append(chunk_id)
                await self._db.execute(
                    text(
                        "INSERT INTO knowledge_chunks "
                        "(id, document_id, org_id, chunk_index, content, chunk_metadata) "
                        "VALUES (:id, :doc_id, :org_id, :idx, :content, CAST(:meta AS jsonb)) "
                        "ON CONFLICT (id) DO NOTHING"
                    ),
                    {
                        "id": chunk_id,
                        "doc_id": doc.id,
                        "org_id": current_user.org_id,
                        "idx": c.chunk_index,
                        "content": c.content,
                        "meta": _json.dumps(c.chunk_metadata),
                    },
                )

            # Update embedding column — embed vector literal in SQL (asyncpg
            # rejects :param::vector named-param+cast combos)
            for chunk_id, vec in zip(chunk_ids, embeddings):
                vec_str = _vector_to_pg(vec)
                await self._db.execute(
                    text(
                        f"UPDATE knowledge_chunks "
                        f"SET embedding = '{vec_str}'::vector "
                        f"WHERE id = :id"
                    ),
                    {"id": chunk_id},
                )

            # 6. Mark READY
            doc.status = DocumentStatus.READY
            doc.chunk_count = len(chunk_ids)

            # Audit: processing complete
            await self._audit.log(
                org_id=current_user.org_id,
                event_type="knowledge.document_processed",
                resource_type="knowledge_document",
                resource_id=doc.id,
                actor_id=current_user.id,
                actor_type=ActorType.USER,
                details={
                    "chunk_count": len(chunk_ids),
                    "status": "ready",
                    "embedder": type(embedder).__name__,
                },
            )
            await self._db.commit()

            logger.info(
                "Document %s processed: %d chunks with embeddings (status=READY)",
                doc.id, len(chunk_ids),
            )

        except Exception as exc:  # noqa: BLE001
            logger.exception("Processing failed for document %s: %s", doc.id, exc)
            try:
                doc.status = DocumentStatus.FAILED
                await self._audit.log(
                    org_id=current_user.org_id,
                    event_type="knowledge.document_processed",
                    resource_type="knowledge_document",
                    resource_id=doc.id,
                    actor_id=current_user.id,
                    actor_type=ActorType.USER,
                    details={"status": "failed", "error": str(exc)},
                )
                await self._db.commit()
            except Exception:  # noqa: BLE001
                logger.exception("Could not update FAILED status for document %s", doc.id)

        return await self._get_document_by_id(doc.id, current_user)

    # ── Semantic search ──────────────────────────────────────────────────────

    async def search(
        self,
        query: str,
        current_user: User,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Embed query → cosine similarity search, strictly filtered by org_id.

        Returns a list of dicts (not ORM objects) to avoid lazy-load issues:
          {
            chunk_id, document_id, document_title,
            content, similarity_score, page, section, source_title
          }

        Audit event: knowledge.search
        """
        if top_k < 1 or top_k > MAX_TOP_K:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"top_k must be between 1 and {MAX_TOP_K}.",
            )

        embedder = get_embedder()
        query_vec = await embedder.embed_one(query)
        vec_literal = _vector_to_pg(query_vec)

        # Cosine similarity: 1 - cosine_distance = cosine_similarity
        # pgvector operator <=> = cosine distance (0 = identical, 2 = opposite)
        # Embed the vector literal directly in SQL — asyncpg rejects :param::type syntax.
        sql = text(
            f"""
            SELECT
                kc.id             AS chunk_id,
                kc.document_id    AS document_id,
                kd.title          AS document_title,
                kc.content        AS content,
                1 - (kc.embedding <=> '{vec_literal}'::vector) AS similarity_score,
                (kc.chunk_metadata->>'page')::int          AS page,
                kc.chunk_metadata->>'section'              AS section,
                kc.chunk_metadata->>'source_title'         AS source_title
            FROM knowledge_chunks kc
            JOIN knowledge_documents kd ON kd.id = kc.document_id
            WHERE kc.org_id = :org_id
              AND kd.status = 'ready'
              AND kc.embedding IS NOT NULL
            ORDER BY kc.embedding <=> '{vec_literal}'::vector
            LIMIT :top_k
            """
        )

        result = await self._db.execute(
            sql,
            {
                "org_id": current_user.org_id,
                "top_k": top_k,
            },
        )
        rows = result.mappings().all()

        hits = [dict(row) for row in rows]

        # Audit: search event
        await self._audit.log(
            org_id=current_user.org_id,
            event_type="knowledge.search",
            resource_type="knowledge_chunk",
            resource_id=None,
            actor_id=current_user.id,
            actor_type=ActorType.USER,
            details={
                "query": query[:500],  # truncate for audit safety
                "top_k": top_k,
                "results_count": len(hits),
                "embedder": type(embedder).__name__,
            },
        )
        await self._db.commit()

        return hits

    # ── List documents ───────────────────────────────────────────────────────

    async def list_documents(self, current_user: User) -> list[KnowledgeDocument]:
        result = await self._db.execute(
            select(KnowledgeDocument)
            .where(KnowledgeDocument.org_id == current_user.org_id)
            .order_by(KnowledgeDocument.created_at.desc())
        )
        return list(result.scalars().all())

    # ── Get by id ────────────────────────────────────────────────────────────

    async def get_document(
        self, document_id: uuid.UUID, current_user: User
    ) -> KnowledgeDocument:
        return await self._get_document_by_id(document_id, current_user)

    async def _get_document_by_id(
        self, document_id: uuid.UUID, current_user: User
    ) -> KnowledgeDocument:
        result = await self._db.execute(
            select(KnowledgeDocument)
            .options(selectinload(KnowledgeDocument.chunks))
            .where(
                KnowledgeDocument.id == document_id,
                KnowledgeDocument.org_id == current_user.org_id,
            )
        )
        doc = result.scalar_one_or_none()
        if doc is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found.",
            )
        return doc

    # ── Delete ───────────────────────────────────────────────────────────────

    async def delete_document(
        self, document_id: uuid.UUID, current_user: User
    ) -> None:
        doc = await self._get_document_by_id(document_id, current_user)

        if doc.source_path:
            try:
                storage = get_storage_provider()
                storage.delete(doc.source_path)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not delete file %s: %s", doc.source_path, exc)

        await self._db.delete(doc)
        await self._db.commit()
