"""Add source_path to knowledge_documents

Revision ID: 003
Revises: 002
Create Date: 2026-09-17

The ORM model always had source_path but the initial migration omitted it.
This migration adds the nullable column.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "knowledge_documents",
        sa.Column("source_path", sa.String(1000), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("knowledge_documents", "source_path")
