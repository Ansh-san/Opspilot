"""
Embedding providers — Phase 3 RAG pipeline.

Two implementations share a common Protocol interface:

  MockEmbeddingProvider
    • Deterministic: uses a seeded SHA-256 hash of each text snippet so
      the same text always produces the same 1536-dimensional unit vector.
    • Zero latency, no API key, safe for tests and development.
    • Dimension: exactly 1536 floats — matches the pgvector column.

  OpenAIEmbeddingProvider
    • Calls OpenAI text-embedding-3-small (or any configured model).
    • Requires OPENAI_API_KEY in environment / .env.
    • Raises ImportError at construction time if openai is not installed.

Provider selection is driven by settings.LLM_PROVIDER:
  - "mock"   → MockEmbeddingProvider (default, dev-safe)
  - "openai" → OpenAIEmbeddingProvider

Usage:
    from app.ai.rag.embedder import get_embedder
    embedder = get_embedder()
    vectors = await embedder.embed_many(["text 1", "text 2"])
"""

from __future__ import annotations

import hashlib
import logging
import math
from typing import Protocol, runtime_checkable

from app.core.config import settings

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 1536  # must match vector(1536) in DB and migration 002


# ─── Protocol ────────────────────────────────────────────────────────────────

@runtime_checkable
class EmbeddingProvider(Protocol):
    async def embed_one(self, text: str) -> list[float]:
        """Return a single embedding vector of length EMBEDDING_DIM."""
        ...

    async def embed_many(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per text, in the same order."""
        ...


# ─── Mock provider ───────────────────────────────────────────────────────────

class MockEmbeddingProvider:
    """
    Deterministic mock embedder for development and testing.

    Algorithm:
      1. Compute SHA-256(text) → 32 bytes.
      2. Tile the bytes to fill 1536 dimensions (i + byte_val / 255).
      3. L2-normalise the resulting vector to unit length.

    The result is deterministic (same text → same vector), covers the full
    unit sphere so cosine similarity is meaningful, and is always exactly
    1536 dimensions.
    """

    def _hash_to_vector(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()  # 32 bytes
        # Build 1536 raw floats by tiling the digest with offset variation
        raw: list[float] = []
        for i in range(EMBEDDING_DIM):
            byte_val = digest[i % len(digest)]
            # Add index-based variation so each dimension differs
            raw.append(float(byte_val) / 255.0 + (i * 0.001))

        # L2-normalise → unit vector (cosine similarity is well-defined)
        norm = math.sqrt(sum(v * v for v in raw))
        if norm == 0:
            return [0.0] * EMBEDDING_DIM
        return [v / norm for v in raw]

    async def embed_one(self, text: str) -> list[float]:
        return self._hash_to_vector(text)

    async def embed_many(self, texts: list[str]) -> list[list[float]]:
        return [self._hash_to_vector(t) for t in texts]


# ─── OpenAI provider ─────────────────────────────────────────────────────────

class OpenAIEmbeddingProvider:
    """
    Production embedder backed by OpenAI text-embedding-3-small.

    Requires:
      - openai >= 1.0 installed (pip install openai)
      - OPENAI_API_KEY set in environment / .env
    """

    def __init__(self) -> None:
        try:
            from openai import AsyncOpenAI  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "openai package is not installed. "
                "Add 'openai' to requirements.txt or set LLM_PROVIDER=mock."
            ) from exc

        if not settings.OPENAI_API_KEY:
            raise ValueError(
                "OPENAI_API_KEY is not set. "
                "Provide the key in .env or set LLM_PROVIDER=mock."
            )

        self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self._model = settings.EMBEDDING_MODEL
        logger.info("OpenAIEmbeddingProvider initialised (model=%s)", self._model)

    async def embed_one(self, text: str) -> list[float]:
        vectors = await self.embed_many([text])
        return vectors[0]

    async def embed_many(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = await self._client.embeddings.create(
            model=self._model,
            input=texts,
        )
        # Preserve input order (OpenAI returns them sorted by index)
        ordered = sorted(response.data, key=lambda d: d.index)
        vectors = [item.embedding for item in ordered]

        # Validate dimensions
        for i, vec in enumerate(vectors):
            if len(vec) != EMBEDDING_DIM:
                raise ValueError(
                    f"OpenAI returned {len(vec)}-dim vector for text[{i}]; "
                    f"expected {EMBEDDING_DIM}."
                )
        return vectors


# ─── Factory ─────────────────────────────────────────────────────────────────

def get_embedder() -> EmbeddingProvider:
    """
    Return the configured embedding provider.

    Controlled by settings.LLM_PROVIDER:
      "mock"   → MockEmbeddingProvider (deterministic, no API key needed)
      "openai" → OpenAIEmbeddingProvider (requires OPENAI_API_KEY)
    """
    provider = settings.LLM_PROVIDER.lower()
    if provider == "openai":
        logger.info("Using OpenAIEmbeddingProvider")
        return OpenAIEmbeddingProvider()
    # Default: mock (safe for dev/test)
    if provider != "mock":
        logger.warning(
            "Unknown LLM_PROVIDER '%s'; falling back to MockEmbeddingProvider.", provider
        )
    logger.info("Using MockEmbeddingProvider (deterministic, no API key required)")
    return MockEmbeddingProvider()
