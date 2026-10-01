"""Initial schema — all OpsPilot tables

Revision ID: 001
Revises:
Create Date: 2026-09-08

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Extensions ────────────────────────────────────────────────────────────
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # ── Enums ─────────────────────────────────────────────────────────────────
    userrole = postgresql.ENUM(
        "admin", "manager", "agent", "viewer", name="userrole", create_type=False
    )
    userrole.create(op.get_bind(), checkfirst=True)

    ticketstatus = postgresql.ENUM(
        "open", "investigating", "waiting_approval", "in_progress", "resolved", "closed",
        name="ticketstatus", create_type=False,
    )
    ticketstatus.create(op.get_bind(), checkfirst=True)

    ticketpriority = postgresql.ENUM(
        "low", "medium", "high", "critical", name="ticketpriority", create_type=False
    )
    ticketpriority.create(op.get_bind(), checkfirst=True)

    ticketseverity = postgresql.ENUM(
        "s1", "s2", "s3", "s4", name="ticketseverity", create_type=False
    )
    ticketseverity.create(op.get_bind(), checkfirst=True)

    documentsourcetype = postgresql.ENUM(
        "pdf", "txt", "markdown", "url", name="documentsourcetype", create_type=False
    )
    documentsourcetype.create(op.get_bind(), checkfirst=True)

    documentstatus = postgresql.ENUM(
        "pending", "processing", "ready", "failed", name="documentstatus", create_type=False
    )
    documentstatus.create(op.get_bind(), checkfirst=True)

    risklevel = postgresql.ENUM(
        "low", "medium", "high", "blocked", name="risklevel", create_type=False
    )
    risklevel.create(op.get_bind(), checkfirst=True)

    approvalstatus = postgresql.ENUM(
        "pending", "approved", "rejected", "expired", name="approvalstatus", create_type=False
    )
    approvalstatus.create(op.get_bind(), checkfirst=True)

    actortype = postgresql.ENUM(
        "user", "system", "ai", name="actortype", create_type=False
    )
    actortype.create(op.get_bind(), checkfirst=True)

    # ── organizations ─────────────────────────────────────────────────────────
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("settings", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("uq_organizations_slug", "organizations", ["slug"], unique=True)

    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("role", userrole, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("uq_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_org_id", "users", ["org_id"])

    # ── tickets ───────────────────────────────────────────────────────────────
    op.create_table(
        "tickets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("priority", ticketpriority, nullable=False),
        sa.Column("severity", ticketseverity, nullable=True),
        sa.Column("status", ticketstatus, nullable=False),
        sa.Column("requester_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assigned_agent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("affected_service", sa.String(255), nullable=True),
        sa.Column("ai_confidence", sa.Float(), nullable=True),
        sa.Column("ai_recommendation", sa.Text(), nullable=True),
        sa.Column("ai_diagnosis", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_tickets_org_id", "tickets", ["org_id"])
    op.create_index("ix_tickets_status", "tickets", ["status"])

    # ── ticket_comments ───────────────────────────────────────────────────────
    op.create_table(
        "ticket_comments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_ai_generated", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ticket_comments_ticket_id", "ticket_comments", ["ticket_id"])

    # ── knowledge_documents ───────────────────────────────────────────────────
    op.create_table(
        "knowledge_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("source_type", documentsourcetype, nullable=False),
        sa.Column("status", documentstatus, nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_knowledge_documents_org_id", "knowledge_documents", ["org_id"])

    # ── knowledge_chunks ──────────────────────────────────────────────────────
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", postgresql.JSONB(), nullable=True),
        sa.Column("chunk_metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_knowledge_chunks_document_id", "knowledge_chunks", ["document_id"])
    op.create_index("ix_knowledge_chunks_org_id", "knowledge_chunks", ["org_id"])

    # ── ai_runs ───────────────────────────────────────────────────────────────
    op.create_table(
        "ai_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tickets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("agent_trace", postgresql.JSONB(), nullable=True),
        sa.Column("decision", sa.Text(), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("evidence", postgresql.JSONB(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("risk_level", risklevel, nullable=True),
        sa.Column("policy_result", postgresql.JSONB(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("model_used", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ai_runs_org_id", "ai_runs", ["org_id"])
    op.create_index("ix_ai_runs_ticket_id", "ai_runs", ["ticket_id"])

    # ── approval_requests ─────────────────────────────────────────────────────
    op.create_table(
        "approval_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ai_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ai_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("proposed_action", sa.String(255), nullable=False),
        sa.Column("action_args", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("risk_level", risklevel, nullable=False),
        sa.Column("status", approvalstatus, nullable=False),
        sa.Column("requested_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reviewed_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_approval_requests_org_id", "approval_requests", ["org_id"])
    op.create_index("ix_approval_requests_status", "approval_requests", ["status"])

    # ── tool_executions ───────────────────────────────────────────────────────
    op.create_table(
        "tool_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ai_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ai_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approval_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("approval_requests.id", ondelete="SET NULL"), nullable=True),
        sa.Column("tool_name", sa.String(255), nullable=False),
        sa.Column("args", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("is_simulated", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("success", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_tool_executions_org_id", "tool_executions", ["org_id"])

    # ── audit_logs ────────────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_type", actortype, nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_logs_org_id", "audit_logs", ["org_id"])
    op.create_index("ix_audit_logs_event_type", "audit_logs", ["event_type"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    # ── evaluation_runs ───────────────────────────────────────────────────────
    op.create_table(
        "evaluation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ai_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ai_runs.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("retrieval_relevance", sa.Float(), nullable=True),
        sa.Column("answer_groundedness", sa.Float(), nullable=True),
        sa.Column("classification_accuracy", sa.Float(), nullable=True),
        sa.Column("tool_success_rate", sa.Float(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("token_cost_usd", sa.Float(), nullable=True),
        sa.Column("human_override", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_evaluation_runs_org_id", "evaluation_runs", ["org_id"])


def downgrade() -> None:
    op.drop_table("evaluation_runs")
    op.drop_table("audit_logs")
    op.drop_table("tool_executions")
    op.drop_table("approval_requests")
    op.drop_table("ai_runs")
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_documents")
    op.drop_table("ticket_comments")
    op.drop_table("tickets")
    op.drop_table("users")
    op.drop_table("organizations")

    for enum_name in [
        "actortype", "approvalstatus", "risklevel", "documentstatus",
        "documentsourcetype", "ticketseverity", "ticketpriority",
        "ticketstatus", "userrole",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
