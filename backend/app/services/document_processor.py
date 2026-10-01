"""
Document processor service — Phase 3 Knowledge Base.

Supports three source types:
  • PDF     — uses pypdf to extract text per-page
  • TXT     — plain UTF-8 read
  • Markdown — plain text (stripping raw markdown syntax is optional / future)

Each processor returns a list of RawPage objects, which are then handed to the
chunker.  Keeping extraction and chunking separate makes unit-testing simple and
allows plugging in a different chunking strategy without touching this file.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

logger = logging.getLogger(__name__)


# ─── Domain object ───────────────────────────────────────────────────────────

@dataclass
class RawPage:
    """A single page (or logical section) of extracted text."""
    page_number: int          # 1-based
    text: str
    metadata: dict = field(default_factory=dict)


# ─── Processor protocol ──────────────────────────────────────────────────────

class DocumentProcessorProtocol(Protocol):
    def extract(self, content: bytes, file_name: str) -> list[RawPage]:
        ...


# ─── PDF Processor ───────────────────────────────────────────────────────────

class PDFProcessor:
    """Extract text from each page of a PDF using pypdf."""

    def extract(self, content: bytes, file_name: str) -> list[RawPage]:
        import io
        try:
            import pypdf  # lazy import — not needed for TXT/MD paths
        except ImportError as exc:
            raise RuntimeError("pypdf is not installed — add it to requirements.txt") from exc

        pages: list[RawPage] = []
        reader = pypdf.PdfReader(io.BytesIO(content))

        for page_num, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text() or ""
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not extract text from page %d: %s", page_num, exc)
                text = ""

            if text.strip():
                pages.append(
                    RawPage(
                        page_number=page_num,
                        text=text,
                        metadata={"page": page_num, "total_pages": len(reader.pages)},
                    )
                )

        logger.info("PDF '%s': extracted %d non-empty pages", file_name, len(pages))
        return pages


# ─── TXT Processor ───────────────────────────────────────────────────────────

class TextProcessor:
    """Read a plain-text file as a single logical page."""

    def extract(self, content: bytes, file_name: str) -> list[RawPage]:
        text = content.decode("utf-8", errors="replace")
        logger.info("TXT '%s': read %d chars", file_name, len(text))
        return [RawPage(page_number=1, text=text, metadata={"page": 1})]


# ─── Markdown Processor ──────────────────────────────────────────────────────

class MarkdownProcessor:
    """
    Read a Markdown file as a single logical page.

    Phase 3 keeps this simple: raw markdown is stored so the chunker can
    split on heading boundaries.  A future iteration could strip markup.
    """

    def extract(self, content: bytes, file_name: str) -> list[RawPage]:
        text = content.decode("utf-8", errors="replace")
        logger.info("MD '%s': read %d chars", file_name, len(text))
        return [RawPage(page_number=1, text=text, metadata={"page": 1})]


# ─── Factory ─────────────────────────────────────────────────────────────────

_PROCESSORS: dict[str, DocumentProcessorProtocol] = {
    ".pdf": PDFProcessor(),
    ".txt": TextProcessor(),
    ".md": MarkdownProcessor(),
}


def get_processor(file_name: str) -> DocumentProcessorProtocol:
    """Factory to return the right processor based on file extension."""
    suffix = Path(file_name).suffix.lower()
    if suffix == ".pdf":
        return PDFProcessor()
    if suffix == ".txt":
        return TextProcessor()
    if suffix == ".md":
        return MarkdownProcessor()
    
    raise ValueError(f"No processor found for extension: {suffix}")
