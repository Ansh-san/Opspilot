"""
Phase 4 — LangGraph Agent State definition.

Design decisions and traps addressed:
  1. List reducer trap: retrieved_documents and errors use Annotated[list, add]
     so LangGraph appends values rather than overwriting at each node.
  2. All fields are typed so mypy can catch type errors in node implementations.
  3. classification, diagnosis, recommendation hold typed Pydantic instances
     (never raw dicts) so downstream nodes can access attributes safely.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from typing_extensions import TypedDict

# LangGraph's built-in list reducer — appends instead of overwriting
from langgraph.graph.message import add_messages  # noqa: F401 (re-export friendly)

from app.ai.agent.schemas import (
    TicketClassification,
    TicketDiagnosis,
    TicketRecommendation,
)


def _append(existing: list, new: list) -> list:
    """Simple append reducer for LangGraph annotated list fields."""
    return existing + new


class AgentState(TypedDict):
    """
    The single source of truth flowing through every LangGraph node.

    Mutability contract
    -------------------
    • Scalar fields (ticket_id, org_id, …) are overwritten by the node that
      sets them — this is safe because only one node writes each scalar.
    • List fields (retrieved_documents, errors) use `Annotated[list, _append]`
      so that each node *appends* its results rather than overwriting the list.
      This prevents the silent state mutation bug where a second node wipes out
      the first node's results.
    """

    # ─── Inputs (set before graph.ainvoke()) ─────────────────────────────────
    ticket_id: uuid.UUID
    org_id: uuid.UUID
    ticket_data: dict[str, Any]      # Raw ticket fields from the DB

    # ─── Intermediate results (set by nodes) ─────────────────────────────────
    classification: TicketClassification | None
    # Annotated list — each RAG retrieval step appends its chunks
    retrieved_documents: Annotated[list[dict[str, Any]], _append]

    diagnosis: TicketDiagnosis | None
    recommendation: TicketRecommendation | None
    action_proposal: dict[str, Any] | None

    # ─── Aggregate signals (set by finalize node) ─────────────────────────────
    confidence: float | None          # Final overall confidence across all nodes
    risk_level: str | None            # Mirrors recommendation.risk_level

    # ─── Observability ────────────────────────────────────────────────────────
    errors: Annotated[list[str], _append]   # Each node appends its own errors
    token_usage: dict[str, int] | None      # Total tokens consumed (for cost tracking)
    latency_ms: int | None                  # End-to-end wall-clock ms
    evaluation_results: list[dict[str, Any]] | None
