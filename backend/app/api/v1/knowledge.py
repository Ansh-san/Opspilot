"""
Knowledge Base API — Phase 3.

Endpoints:
  POST   /knowledge/documents          Upload a PDF / TXT / MD file
  GET    /knowledge/documents          List all documents for the org
  GET    /knowledge/documents/{id}     Get a single document (with chunks)
  DELETE /knowledge/documents/{id}     Delete a document and its file
  POST   /knowledge/search             Semantic search across the knowledge base
"""

import uuid

from fastapi import APIRouter, Body, Depends, File, Response, UploadFile, Request, status

from app.core.dependencies import CurrentUser, DBSession, require_agent_or_above
from app.core.rate_limiter import limiter
from app.core.config import settings
from app.schemas.knowledge import (
    KnowledgeDocumentListItem,
    KnowledgeDocumentResponse,
    SearchRequest,
    SearchResponse,
    SearchHit,
)
from app.services.knowledge_service import KnowledgeService

router = APIRouter(prefix="/knowledge", tags=["Knowledge Base"])


# ─── Upload ───────────────────────────────────────────────────────────────────

@router.post(
    "/documents",
    response_model=KnowledgeDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a knowledge document",
    dependencies=[Depends(require_agent_or_above())],
)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
async def upload_document(
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
    file: UploadFile = File(..., description="PDF, TXT, or MD file (max 10 MB)"),
) -> KnowledgeDocumentResponse:
    """
    Upload a document to the knowledge base.

    - Validates file type (PDF, TXT, MD) and size (max 10 MB).
    - Extracts text, splits into chunks, generates embeddings.
    - Returns the created document with status **READY** or **FAILED**.

    Audit events: `knowledge.document_uploaded`, `knowledge.document_processed`
    """
    svc = KnowledgeService(db)
    doc = await svc.upload_document(file=file, current_user=current_user)
    return KnowledgeDocumentResponse.model_validate(doc)


# ─── List ─────────────────────────────────────────────────────────────────────

@router.get(
    "/documents",
    response_model=list[KnowledgeDocumentListItem],
    summary="List knowledge documents",
)
async def list_documents(
    db: DBSession,
    current_user: CurrentUser,
) -> list[KnowledgeDocumentListItem]:
    """Return all documents belonging to the current user's organisation."""
    svc = KnowledgeService(db)
    docs = await svc.list_documents(current_user=current_user)
    return [KnowledgeDocumentListItem.model_validate(d) for d in docs]


# ─── Get by ID ────────────────────────────────────────────────────────────────

@router.get(
    "/documents/{document_id}",
    response_model=KnowledgeDocumentResponse,
    summary="Get a knowledge document",
)
async def get_document(
    document_id: uuid.UUID,
    db: DBSession,
    current_user: CurrentUser,
) -> KnowledgeDocumentResponse:
    """Return a single document, including all of its chunks."""
    svc = KnowledgeService(db)
    doc = await svc.get_document(document_id=document_id, current_user=current_user)
    return KnowledgeDocumentResponse.model_validate(doc)


# ─── Delete ───────────────────────────────────────────────────────────────────

@router.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a knowledge document",
    dependencies=[Depends(require_agent_or_above())],
)
async def delete_document(
    document_id: uuid.UUID,
    db: DBSession,
    current_user: CurrentUser,
) -> Response:
    """Delete a document and its associated chunks and uploaded file."""
    svc = KnowledgeService(db)
    await svc.delete_document(document_id=document_id, current_user=current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ─── Semantic search ──────────────────────────────────────────────────────────

@router.post(
    "/search",
    response_model=SearchResponse,
    summary="Semantic search across the knowledge base",
)
async def search_knowledge(
    db: DBSession,
    current_user: CurrentUser,
    body: SearchRequest = Body(...),
) -> SearchResponse:
    """
    Embed the query and perform a cosine similarity search across all READY
    documents in the current user's organisation.

    - **query**: natural-language search string (max 2000 chars)
    - **top_k**: number of results to return (1–10, default 5)

    Returns chunks ranked by cosine similarity, with document title and page metadata.

    Audit event: `knowledge.search`
    """
    svc = KnowledgeService(db)
    hits = await svc.search(
        query=body.query,
        current_user=current_user,
        top_k=body.top_k,
    )
    return SearchResponse(
        query=body.query,
        top_k=body.top_k,
        results=[SearchHit(**h) for h in hits],
    )
