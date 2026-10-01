"""
Chunker service — Phase 3 Knowledge Base.

Converts a list of RawPage objects (from document_processor.py) into
structured KnowledgeChunk-ready dicts using LangChain's
RecursiveCharacterTextSplitter.

Chunk metadata contract (every chunk carries):
  {
    "document_id": str(uuid),
    "chunk_index": int,           # 0-based
    "page": int,                  # source page number (1-based)
    "section": str | None,        # future: extracted heading; None for now
    "source_title": str,          # document title for RAG context
  }
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.services.document_processor import RawPage

logger = logging.getLogger(__name__)

# ─── Splitter config ─────────────────────────────────────────────────────────
_CHUNK_SIZE = 1000
_CHUNK_OVERLAP = 200

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=_CHUNK_SIZE,
    chunk_overlap=_CHUNK_OVERLAP,
    length_function=len,
    is_separator_regex=False,
)


# ─── Output type ─────────────────────────────────────────────────────────────

@dataclass
class ChunkResult:
    """Ready-to-persist chunk produced by the chunker."""
    chunk_index: int
    content: str
    chunk_metadata: dict[str, Any] = field(default_factory=dict)


# ─── Public API ──────────────────────────────────────────────────────────────

def chunk_pages(
    pages: list[RawPage],
    document_id: uuid.UUID,
    source_title: str,
) -> list[ChunkResult]:
    """
    Split a list of RawPage objects into overlapping text chunks.

    Preserves the originating page number in each chunk's metadata so
    the RAG pipeline can cite specific pages in evidence.

    Returns
    -------
    list[ChunkResult]
        All chunks in document order, 0-indexed.
    """
    if not pages:
        logger.warning("chunk_pages called with empty pages for document %s", document_id)
        return []

    results: list[ChunkResult] = []
    global_index = 0

    for raw_page in pages:
        text = raw_page.text.strip()
        if not text:
            continue

        splits = _splitter.split_text(text)

        for split_text in splits:
            if not split_text.strip():
                continue

            results.append(
                ChunkResult(
                    chunk_index=global_index,
                    content=split_text,
                    chunk_metadata={
                        "document_id": str(document_id),
                        "chunk_index": global_index,
                        "page": raw_page.page_number,
                        "section": None,            # populated by heading-detection in Phase 4
                        "source_title": source_title,
                    },
                )
            )
            global_index += 1

    logger.info(
        "Chunked document %s into %d chunks from %d pages",
        document_id,
        len(results),
        len(pages),
    )
    return results
