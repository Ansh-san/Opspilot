"""
Phase 4 — Pydantic schemas for agent structured output.

These schemas are used by:
  • with_structured_output() to enforce typed LLM responses (no raw json.loads)
  • MockLLMProvider to produce deterministic, schema-valid JSON in dev/test mode
  • The agent state to carry typed intermediate results through the graph

Every schema is intentionally flat so the LLM has minimal surface area for error.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# ─── Classification ───────────────────────────────────────────────────────────

class TicketClassification(BaseModel):
    """Structured output for the classify_ticket node."""

    category: str = Field(
        description=(
            "The technical category of the ticket. "
            "E.g. 'database', 'network', 'authentication', 'infrastructure', 'application'."
        )
    )
    priority: Literal["low", "medium", "high", "critical"] = Field(
        description="Assessed priority level of the ticket."
    )
    severity: Literal["s1", "s2", "s3", "s4"] = Field(
        description="Severity: s1=critical outage, s2=major, s3=minor, s4=informational."
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Classification confidence score between 0.0 and 1.0.",
    )
    reasoning: str = Field(
        description="One-sentence explanation of how the category and priority were determined."
    )


# ─── Diagnosis ────────────────────────────────────────────────────────────────

class TicketDiagnosis(BaseModel):
    """Structured output for the generate_diagnosis node."""

    root_cause: str = Field(
        description="The probable root cause of the issue described in the ticket."
    )
    affected_components: list[str] = Field(
        description="List of system components or services likely affected."
    )
    impact_summary: str = Field(
        description="One or two sentences describing the business or user impact."
    )
    evidence: list[str] = Field(
        description=(
            "List of specific evidence strings that support this diagnosis, "
            "sourced from the ticket description or retrieved knowledge chunks."
        )
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Diagnosis confidence score between 0.0 and 1.0.",
    )


# ─── Recommendation ──────────────────────────────────────────────────────────

class TicketRecommendation(BaseModel):
    """Structured output for the generate_recommendation node."""

    action: str = Field(
        description="The primary recommended action to resolve the issue."
    )
    steps: list[str] = Field(
        description="Ordered list of concrete remediation steps."
    )
    estimated_resolution_time: str = Field(
        description="Estimated time to resolve, e.g. '15 minutes', '2-4 hours'."
    )
    risk_level: Literal["low", "medium", "high", "blocked"] = Field(
        description=(
            "Risk level of applying the recommendation. "
            "'blocked' means human approval is required before proceeding."
        )
    )
    requires_approval: bool = Field(
        description="Whether this action requires explicit human approval before execution."
    )
    runbook_references: list[str] = Field(
        default_factory=list,
        description="List of referenced knowledge document titles or runbook names.",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Recommendation confidence score between 0.0 and 1.0.",
    )


# ─── Action Proposal ─────────────────────────────────────────────────────────

class TicketActionProposal(BaseModel):
    """Structured output for the propose_action node (Phase 5)."""

    proposed_action: str = Field(
        description="The exact name of the tool/action to execute (e.g. 'restart_production_service', 'get_service_health'). If no action is appropriate, return 'none'."
    )
    action_arguments: dict[str, Any] = Field(
        default_factory=dict,
        description="A JSON dictionary of arguments strictly matching the proposed action's schema."
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Proposal confidence score between 0.0 and 1.0.",
    )
