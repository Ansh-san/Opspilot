"""
Alembic migration: Phase 3 — pgvector index on knowledge_chunks.embedding

Revision ID: 002
Revises: 001
Create Date: 2026-09-17

This migration:
  1. Converts knowledge_chunks.embedding from JSONB → vector(1536).
  2. Adds an IVFFlat index for fast approximate nearest-neighbour search.

The IVFFlat index requires at least `lists` rows to exist before CREATE INDEX
succeeds; therefore we create it CONCURRENTLY-safe with `lists=1` so it always
works on an empty table (raise lists to 100 once you have ≥10 k rows in prod).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ensure pgvector extension exists (idempotent).
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Convert embedding JSONB → vector(1536).
    # First drop the old JSONB column, then add the new typed one.
    op.drop_column("knowledge_chunks", "embedding")
    op.add_column(
        "knowledge_chunks",
        sa.Column(
            "embedding",
            sa.Text().with_variant(sa.Text(), "postgresql"),  # placeholder; real type set below
            nullable=True,
        ),
    )
    # Use raw DDL to set the proper vector type — SQLAlchemy doesn't know vector natively
    # without pgvector's type registered; raw execute is safer across versions.
    op.execute("ALTER TABLE knowledge_chunks ALTER COLUMN embedding TYPE vector(1536) USING NULL")

    # IVFFlat index for L2 (Euclidean) nearest-neighbour search.
    # lists=1 is safe on an empty table; bump to 100 for ≥10k rows in production.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_embedding_ivfflat "
        "ON knowledge_chunks USING ivfflat (embedding vector_l2_ops) WITH (lists=1)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_knowledge_chunks_embedding_ivfflat")
    op.drop_column("knowledge_chunks", "embedding")
    op.add_column(
        "knowledge_chunks",
        sa.Column("embedding", sa.dialects.postgresql.JSONB(), nullable=True),
    )
